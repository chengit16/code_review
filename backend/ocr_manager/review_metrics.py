"""按项目、状态与输入规模汇总近七天持久化评审事实；样本缺失保持未知。"""

from __future__ import annotations

import math
import sqlite3
from typing import Any

from ocr_manager.review_observability import enrich_jobs


def _percentile(values: list[float], proportion: float) -> float | None:
    return sorted(values)[max(0, math.ceil(len(values) * proportion) - 1)] if values else None


def performance_metrics(db: sqlite3.Connection) -> list[dict[str, Any]]:
    """批量读取最近七天任务；跳过任务不计入成功模型执行分位数。"""

    # 1. 只读取时间、规模和安全用量投影，不加载发现或代码正文。
    jobs = [dict(row) for row in db.execute("""SELECT id,repository_id,status,attempts,created_at,
        started_at,finished_at,reason_code,error,
        CASE WHEN json_valid(scope_json) THEN
          json_remove(scope_json,'$.newline_only_paths') END AS scope_json FROM review_jobs
        WHERE created_at>=datetime('now','-7 days') ORDER BY id""")]
    # 2. 分块避免超出旧 SQLite 的绑定参数限制，不按每个任务分别查询尝试。
    for offset in range(0, len(jobs), 500):
        enrich_jobs(db, jobs[offset:offset + 500])
    groups: dict[tuple[int, str, str], list[dict[str, Any]]] = {}
    for job in jobs:
        size = (job.get("scope_analysis") or {}).get("original_count")
        bucket = ("unknown" if size is None else "0-50" if size <= 50
                  else "51-200" if size <= 200 else "201+")
        groups.setdefault((job["repository_id"], job["effective_status"], bucket), []).append(job)
    # 3. 每个状态独立统计样本数，未知不填零，跳过不混入成功执行分位数。
    result = []
    for (repository_id, status, size), items in sorted(groups.items()):
        execution = [float(item["timing"]["cumulative_execution_seconds"]) for item in items
                     if item["status"] == "complete" and item["timing"]["execution_complete"]
                     and item["timing"]["cumulative_execution_seconds"] is not None]
        queue = [float(item["timing"]["first_queue_seconds"]) for item in items
                 if item["attempts"] and item["timing"]["first_queue_seconds"] is not None]
        timeout_count = sum(item["reason"]["code"] == "timeout" for item in items)
        result.append({"repository_id": repository_id, "status": status, "size_bucket": size,
                       "count": len(items), "execution_samples": len(execution),
                       "execution_p50_seconds": _percentile(execution, .5),
                       "execution_p95_seconds": _percentile(execution, .95),
                       "queue_samples": len(queue), "queue_p50_seconds": _percentile(queue, .5),
                       "queue_p95_seconds": _percentile(queue, .95),
                       "timeout_count": timeout_count,
                       "timeout_rate": timeout_count / len(items),
                       "retry_count": sum(max(0, item["attempts"] - 1) for item in items),
                       "unknown_usage_count": sum(not item["cumulative_usage"]["usage_complete"]
                                                  for item in items),
                       "known_tokens": sum((item["cumulative_usage"]["known_tokens"] or {})
                                           .get("total_tokens", 0) for item in items)})
    return result
