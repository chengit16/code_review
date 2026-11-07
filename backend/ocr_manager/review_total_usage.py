"""累计全任务初审及补审费用；包含历史和失败批次，逐次单价、未知与币种保持独立。"""

from __future__ import annotations

import sqlite3
from typing import Any

from ocr_manager.review_observability import usage_summary


def attach_total_usage(db: sqlite3.Connection, jobs: list[dict[str, Any]],
                       attempts: dict[int, list[dict[str, Any]]]) -> None:
    """批量读取补审安全用量，不加载评论；排队尚未执行不计费，运行/无结果必须计未知。"""

    marks = ",".join("?" for _ in jobs)
    groups: dict[int, list[dict[str, Any]]] = {}
    for row in db.execute(f"""SELECT job_id,status,
        CASE WHEN json_valid(result_json) THEN
          json_object('usage',json_extract(result_json,'$.usage')) END AS result_json,
        CASE WHEN json_valid(config_snapshot) THEN
          json_object('pricing',json_extract(config_snapshot,'$.pricing')) END AS config_snapshot
        FROM review_recoveries WHERE job_id IN ({marks}) AND started_at IS NOT NULL""",
        [job["id"] for job in jobs]):
        groups.setdefault(row["job_id"], []).append(dict(row))
    active = {row["job_id"]: row["id"] for row in db.execute(
        f"SELECT job_id,id FROM review_recoveries WHERE job_id IN ({marks}) "
        "AND status IN ('queued','running')", [job["id"] for job in jobs])}
    failed = dict(db.execute(f"""SELECT d.job_id,count(*) FROM review_recovery_deliveries d
        JOIN review_jobs j ON j.id=d.job_id AND j.attempts=d.source_attempt
        WHERE d.job_id IN ({marks}) AND d.status='failed' AND j.status='partial'
        GROUP BY d.job_id""", [job["id"] for job in jobs]).fetchall())
    for job in jobs:
        job["recovery_delivery_failed_count"] = failed.get(job["id"], 0)
        job["active_recovery_id"] = active.get(job["id"])
        root = attempts.get(job["id"], [])
        batches = groups.get(job["id"], [])
        job["initial_cumulative_usage"] = job["cumulative_usage"]
        job["recovery_execution_count"] = len(batches)
        job["cumulative_usage"] = usage_summary(
            {"attempts": job["attempts"] + len(batches)}, [*root, *batches])
