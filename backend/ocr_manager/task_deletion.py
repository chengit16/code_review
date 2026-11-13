"""管理员删除终态评审及其统计来源；短事务内检查并发、清理关联并审计。

不调用外部服务、不删除合并事件或工件，也不撤回已经发出的通知。
共享问题保留其余来源；存在无法安全移除的人工合并关系时拒绝整个操作。
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from ocr_manager.artifact_lock import artifact_lock
from ocr_manager.storage import Store


class DeleteTaskRequest(BaseModel):
    """确认框看到的任务版本；重审或后台状态变化后必须重新确认。"""

    model_config = ConfigDict(extra="forbid")
    expected_status: Literal["complete", "partial", "failed", "skipped", "cancelled"]
    expected_attempts: int = Field(ge=0, strict=True)
    expected_finished_at: str | None = Field(max_length=40)


class DeleteTaskResult(BaseModel):
    """已提交的清理数量；不将外部通知描述为已撤回。"""

    status: Literal["deleted"] = "deleted"
    job_id: int
    deleted_findings: int
    deleted_issues: int


def delete_task(
    store: Store, job_id: int, expected: DeleteTaskRequest, *,
    actor_id: int | None, actor_name: str, correlation_id: str,
) -> DeleteTaskResult:
    """调用方提供已授权身份；串行化领取、重审与删除，任一步失败全部回滚。

    不存在时抛出 LookupError；版本冲突、在途任务及人工合并依赖抛出 ValueError。
    事件去重事实和独立任务序列保留，不能因删除复用工件身份。
    """

    with artifact_lock(store.path.parent, job_id) as acquired, store.connection() as db:
        if not acquired:
            raise ValueError("任务仍有工件操作或后台处理，请稍后刷新重试")
        # 1. 写锁内核对确认快照及所有执行/投递来源，防止 Worker 晚到写回。
        db.execute("BEGIN IMMEDIATE")
        job = db.execute("SELECT * FROM review_jobs WHERE id=?", (job_id,)).fetchone()
        if job is None:
            raise LookupError("任务不存在或已删除")
        if (job["status"] != expected.expected_status
            or job["attempts"] != expected.expected_attempts
            or job["finished_at"] != expected.expected_finished_at):
            raise ValueError("任务状态或尝试版本已变化，请刷新后重新确认删除")
        active = db.execute("""SELECT 1 FROM review_recoveries
            WHERE job_id=? AND status IN ('queued','running') UNION ALL
            SELECT 1 FROM review_attempts WHERE job_id=? AND status='running' UNION ALL
            SELECT 1 FROM notification_deliveries WHERE job_id=?
              AND status IN ('pending','sending') UNION ALL
            SELECT 1 FROM review_recovery_deliveries WHERE job_id=?
              AND status IN ('pending','sending') UNION ALL
            SELECT 1 FROM gitlab_publications WHERE job_id=?
              AND status IN ('pending','sending') LIMIT 1""", (job_id,) * 5).fetchone()
        if active:
            raise ValueError("任务仍有补审、执行或通知待处理，请等待结束后删除")
        if db.execute("""SELECT 1 FROM worker_execution_slots
            WHERE state='running' AND task_kind='review' AND task_id=?""",
                      (job_id,)).fetchone():
            raise ValueError("后台执行尚未退出，请稍后刷新重试")
        issues = db.execute("""SELECT DISTINCT issue_id FROM review_issue_occurrences
            WHERE job_id=?""", (job_id,)).fetchall()
        findings = db.execute("SELECT COUNT(*) FROM review_issue_occurrences WHERE job_id=?",
                              (job_id,)).fetchone()[0]
        # 2. 显式清理无级联的旧表；其他关联依赖已声明的外键，事件及工件保持原状。
        for table in ("review_feedback", "notification_deliveries", "review_attempts"):
            db.execute(f"DELETE FROM {table} WHERE job_id=?", (job_id,))
        db.execute("DELETE FROM review_jobs WHERE id=?", (job_id,))
        removed = 0
        for issue in issues:
            issue_id = issue["issue_id"]
            remaining = db.execute("""SELECT COUNT(*),MIN(created_at),MAX(created_at)
                FROM review_issue_occurrences WHERE issue_id=?""", (issue_id,)).fetchone()
            if remaining[0]:
                db.execute("""UPDATE review_issues SET first_seen_at=?,last_seen_at=?
                    WHERE id=?""", (remaining[1], remaining[2], issue_id))
            else:
                if db.execute("SELECT 1 FROM review_issues WHERE merged_into_id=?",
                              (issue_id,)).fetchone():
                    raise ValueError("关联问题存在人工合并依赖，请先核对问题后再删除")
                db.execute("DELETE FROM review_issues WHERE id=?", (issue_id,))
                removed += 1
        # 3. 成功审计与删除同事务；审计失败不能留下已删除但无操作人记录的数据。
        db.execute("""INSERT INTO audit_log
            (action,object_type,object_id,outcome,actor_id,actor_name,correlation_id)
            VALUES('delete_review_job','review_job',?,'success',?,?,?)""",
            (job_id, actor_id, actor_name, correlation_id))
    return DeleteTaskResult(job_id=job_id, deleted_findings=findings, deleted_issues=removed)


def register_task_deletion(app: FastAPI, store: Store, admin: Any) -> None:
    """继承服务端管理员鉴权；请求只操作 SQLite，不执行外部副作用。"""

    @app.delete("/api/jobs/{job_id}", dependencies=[admin], response_model=DeleteTaskResult)
    def remove(job_id: int, payload: DeleteTaskRequest, request: Request) -> DeleteTaskResult:
        """只删除已确认的终态版本，拒绝在途和过期目标。"""

        identity = request.state.identity
        try:
            return delete_task(store, job_id, payload, actor_id=identity["id"],
                               actor_name=identity["username"],
                               correlation_id=request.state.request_id)
        except LookupError as error:
            raise HTTPException(404, str(error)) from error
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
