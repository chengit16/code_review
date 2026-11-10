"""离线维护专用：按任务创建时间清理旧评审及无保留来源的问题，不迁移、不调用外部服务。

调用方须暂停同库全部写进程、保存成对备份并隔离演练；跨日问题拒绝自动处理。
此模块没有 HTTP 入口或自动启动入口，工件隔离及进程恢复由维护调用方负责。
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CleanupPlan:
    """受保护维护快照；时间使用规范 UTC，摘要只用于拒绝预览后的数据变化。"""

    cutoff: str
    job_ids: tuple[int, ...]
    issue_ids: tuple[int, ...]
    signature: str


def _digest(db: sqlite3.Connection, table: str, predicate: str = "1") -> str:
    rows = [json.dumps(tuple(row), ensure_ascii=True, default=lambda item: bytes(item).hex())
            for row in db.execute(f'SELECT * FROM "{table}" WHERE {predicate}')]
    return hashlib.sha256("\n".join(sorted(rows)).encode()).hexdigest()


def _tables(db: sqlite3.Connection) -> list[str]:
    return [str(row[0]) for row in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]


def _validate(db: sqlite3.Connection, cutoff: str) -> None:
    if datetime.strptime(cutoff, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S") != cutoff:
        raise ValueError("清理边界必须是规范 UTC 时间")
    if db.execute("PRAGMA user_version").fetchone()[0] != 52:
        raise ValueError("仅支持已核对的 schema 52，不自动迁移")
    if db.execute("PRAGMA foreign_key_check").fetchall():
        raise ValueError("现有外键不完整，拒绝清理")
    active = {
        "review_jobs": "status IN ('queued','running')",
        "review_attempts": "status IN ('queued','running')",
        "merge_events": "status IN ('queued','running')",
        "review_recoveries": "status IN ('queued','running')",
        "notification_deliveries": "status IN ('pending','sending')",
        "review_recovery_deliveries": "status IN ('pending','sending')",
        "gitlab_publications": "status IN ('pending','sending')",
        "premerge_reviews": "status IN ('queued','running')",
        "mr_backfills": "status IN ('queued','running')",
        "rule_previews": "status IN ('queued','running')",
        "repository_discoveries": "status IN ('queued','running')",
        "connection_checks": "status IN ('queued','running')",
        "alert_deliveries": "status IN ('pending','sending')",
        "worker_execution_slots": "state='running'",
    }
    for table, predicate in active.items():
        if db.execute(f'SELECT 1 FROM "{table}" WHERE {predicate} LIMIT 1').fetchone():
            raise ValueError(f"{table} 存在在途或待处理记录，拒绝清理")
    backfill = db.execute("SELECT completed FROM review_issue_backfill WHERE id=1").fetchone()
    if backfill is None or backfill[0] != 1:
        raise ValueError("历史回填未完成，拒绝清理")


def plan_cleanup(db: sqlite3.Connection, cutoff: str) -> CleanupPlan:
    """只读预览；拒绝跨日复用、保留问题指向旧合并目标及来源时间异常。"""

    _validate(db, cutoff)
    if db.execute("""SELECT 1 FROM review_issues i WHERE i.first_seen_at<? AND EXISTS (
        SELECT 1 FROM review_issue_occurrences o JOIN review_jobs j ON j.id=o.job_id
        WHERE o.issue_id=i.id AND j.created_at>=?) LIMIT 1""", (cutoff, cutoff)).fetchone():
        raise ValueError("存在跨日问题，需单独确认重建口径，不自动改写今天数据")
    if db.execute("""SELECT 1 FROM review_issue_occurrences o JOIN review_jobs j ON j.id=o.job_id
        WHERE j.created_at>=? AND o.created_at<? LIMIT 1""", (cutoff, cutoff)).fetchone():
        raise ValueError("保留任务的来源早于清理边界，拒绝自动处理")
    jobs = tuple(int(row[0]) for row in db.execute(
        "SELECT id FROM review_jobs WHERE created_at<? ORDER BY id", (cutoff,)))
    issues = tuple(int(row[0]) for row in db.execute("""SELECT i.id FROM review_issues i
        WHERE NOT EXISTS (SELECT 1 FROM review_issue_occurrences o
          JOIN review_jobs j ON j.id=o.job_id WHERE o.issue_id=i.id AND j.created_at>=?)
        AND (i.first_seen_at<? OR EXISTS (SELECT 1 FROM review_issue_occurrences o
          JOIN review_jobs j ON j.id=o.job_id WHERE o.issue_id=i.id AND j.created_at<?))
        ORDER BY i.id""", (cutoff, cutoff, cutoff)))
    old_issues = set(issues)
    for identifier, target in db.execute(
        "SELECT id,merged_into_id FROM review_issues WHERE merged_into_id IS NOT NULL"
    ):
        if identifier not in old_issues and target in old_issues:
            raise ValueError("保留问题依赖旧合并目标，拒绝自动删除")
    # 全库摘要留在内存；不输出正文、凭据或私有配置，任一写入使旧预览失效。
    signature = hashlib.sha256(json.dumps(
        [(table, _digest(db, table)) for table in _tables(db)],
        ensure_ascii=True,
    ).encode()).hexdigest()
    return CleanupPlan(cutoff, jobs, issues, signature)


def _expected(db: sqlite3.Connection, plan: CleanupPlan) -> dict[str, str]:
    db.execute("CREATE TEMP TABLE cleanup_jobs(id INTEGER PRIMARY KEY)")
    db.execute("CREATE TEMP TABLE cleanup_issues(id INTEGER PRIMARY KEY)")
    db.executemany("INSERT INTO cleanup_jobs VALUES(?)", [(item,) for item in plan.job_ids])
    db.executemany("INSERT INTO cleanup_issues VALUES(?)", [(item,) for item in plan.issue_ids])
    db.execute("""CREATE TEMP TABLE cleanup_findings AS SELECT finding_id
        FROM review_issue_occurrences WHERE job_id IN (SELECT id FROM cleanup_jobs)
        OR issue_id IN (SELECT id FROM cleanup_issues)""")
    db.execute("""CREATE TEMP TABLE cleanup_recoveries AS SELECT id FROM review_recoveries
        WHERE job_id IN (SELECT id FROM cleanup_jobs)""")
    by_job = "job_id NOT IN (SELECT id FROM cleanup_jobs)"
    filters = dict.fromkeys((
        "review_jobs", "notification_deliveries", "review_attempts", "review_feedback",
        "gitlab_publications", "review_stage_timings", "review_recoveries",
        "review_recovery_aggregates", "review_effective_conclusions",
        "review_recovery_deliveries", "review_historical_diagnostics",
        "review_recovery_authorizations",
    ), by_job)
    filters.update({
        "review_jobs": "id NOT IN (SELECT id FROM cleanup_jobs)",
        "review_issues": "id NOT IN (SELECT id FROM cleanup_issues)",
        "review_issue_events": "issue_id NOT IN (SELECT id FROM cleanup_issues)",
        "review_issue_occurrences": f"{by_job} AND issue_id NOT IN (SELECT id FROM cleanup_issues)",
        "review_finding_feedback": "finding_id NOT IN (SELECT finding_id FROM cleanup_findings)",
        "review_recovery_budget_evidence": "recovery_id NOT IN (SELECT id FROM cleanup_recoveries)",
    })
    return {table: _digest(db, table, filters.get(table, "1")) for table in _tables(db)}


def apply_cleanup(db: sqlite3.Connection, plan: CleanupPlan) -> dict[str, int]:
    """独立事务执行已核对预览；所有保留行逐表摘要相等且外键完整才提交。

    调用方须已完成成对备份/演练且独占维护窗口；任何未知级联影响均回滚。
    不重置序列、不删除合并事件、不移除工件、不迁移数据库。
    """

    if db.in_transaction:
        raise ValueError("清理必须使用独立事务连接")
    db.execute("PRAGMA foreign_keys=ON")
    try:
        # 1. 事务内复核完整预览，防止暂停前后的并发写入改变范围。
        db.execute("BEGIN IMMEDIATE")
        if plan_cleanup(db, plan.cutoff) != plan:
            raise ValueError("预览后数据库发生变化，须重新备份并演练")
        expected = _expected(db, plan)
        # 2. 无级联的子表显式删除，其余只依赖已核对的外键；事件与身份序列不变。
        for table in ("review_feedback", "notification_deliveries", "review_attempts"):
            db.execute(f'DELETE FROM "{table}" WHERE job_id IN (SELECT id FROM cleanup_jobs)')
        db.execute("DELETE FROM review_jobs WHERE id IN (SELECT id FROM cleanup_jobs)")
        db.execute("DELETE FROM review_issues WHERE id IN (SELECT id FROM cleanup_issues)")
        # 3. 对全部保留行和其他表核对，不以总数量相等替代内容未变。
        if any(_digest(db, table) != digest for table, digest in expected.items()):
            raise ValueError("保留数据发生非预期变化，已拒绝提交")
        if db.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("清理后外键检查失败")
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("清理后完整性检查失败")
        for table in ("cleanup_jobs", "cleanup_issues", "cleanup_findings", "cleanup_recoveries"):
            db.execute(f'DROP TABLE "{table}"')
        db.commit()
    except BaseException:
        db.rollback()
        raise
    return {"deleted_jobs": len(plan.job_ids), "deleted_issues": len(plan.issue_ids),
            "preserved_tables": len(expected)}
