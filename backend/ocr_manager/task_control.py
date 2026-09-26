"""持久化任务停止请求和批量命令；API 不向 Worker 进程直接发送信号。"""

from __future__ import annotations

from typing import Any

from cryptography.fernet import InvalidToken
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ocr_manager.config import Settings
from ocr_manager.storage import Store


class BatchIds(BaseModel):
    """最多处理 100 个目标；逐条冲突不回滚已成功的命令。"""

    model_config = ConfigDict(extra="forbid")
    ids: list[int] = Field(min_length=1, max_length=100)


def cancellation_requested(store: Store, job_id: int) -> bool:
    """删除项目也视为停止，防止无归属任务继续消耗模型额度。"""

    with store.connection() as db:
        row = db.execute(
            "SELECT cancel_requested FROM review_jobs WHERE id=?", (job_id,)
        ).fetchone()
        return row is None or bool(row[0])


def cancel_job(store: Store, job_id: int) -> str | None:
    """串行化领取与取消；运行任务只能由 Worker 确认终止后进入终态。"""

    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        job = db.execute("SELECT status FROM review_jobs WHERE id=?", (job_id,)).fetchone()
        if job is None or job[0] not in {"queued", "running"}:
            return None
        status = "cancelled" if job[0] == "queued" else "running"
        db.execute("""UPDATE review_jobs SET status=?, cancel_requested=1,
                   finished_at=CASE WHEN ?='cancelled' THEN CURRENT_TIMESTAMP ELSE NULL END,
                   error='用户请求停止评审' WHERE id=?""", (status, status, job_id))
        return "cancelled" if status == "cancelled" else "stopping"


def register_task_control(app: FastAPI, store: Store, settings: Settings, admin: Any) -> None:
    """继承管理授权，批量请求仅建立持久化工作，不调用外部服务。"""

    @app.post("/api/jobs/{job_id}/cancel", dependencies=[admin])
    def cancel(job_id: int) -> dict[str, str]:
        """任务已结束时拒绝停止；成功只表示停止请求已持久化。"""

        status = cancel_job(store, job_id)
        if status is None:
            raise HTTPException(409, "任务已结束或不存在")
        return {"status": status}

    @app.post("/api/jobs/batch-retry", dependencies=[admin])
    def batch_retry(payload: BatchIds) -> list[dict[str, Any]]:
        """每条记录按当前配置重审，失败项保留可读原因。"""

        from ocr_manager.worker import config_hash

        result = []
        for job_id in dict.fromkeys(payload.ids):
            job = store.get_job(job_id)
            if job is None or job_id <= 0:
                result.append({"id": job_id, "status": "rejected", "error": "任务不存在"})
                continue
            try:
                snapshot = config_hash(store, settings, job["rule_digest"], job["repository_id"])
                queued = store.retry_job(job_id, snapshot)
                result.append({"id": job_id, "job_id": queued,
                               "status": "queued" if queued else "rejected"})
            except (ValueError, InvalidToken):
                result.append({"id": job_id, "status": "rejected", "error": "评审配置不可用"})
        return result

    @app.post("/api/repositories/{repository_id}/mrs/batch-enqueue", dependencies=[admin])
    def batch_enqueue(repository_id: int, payload: BatchIds) -> list[dict[str, Any]]:
        """补触发仍由 Worker 核验合并事实；重复 MR 保持幂等。"""

        repository = store.get_repository(repository_id)
        if not repository or not repository["enabled"]:
            raise HTTPException(409, "仓库不存在或已暂停")
        return [{"id": iid, "status": "queued" if iid > 0 and
                 store.enqueue_mr(repository_id, iid) else "rejected"}
                for iid in dict.fromkeys(payload.ids)]
