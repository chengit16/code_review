"""仅从 SQLite 读取来源仍匹配的历史诊断；不读工件、不回填原始结果或改变补审来源摘要。"""

from __future__ import annotations

import json
import sqlite3
from typing import Any


def attach_historical_diagnostics(db: sqlite3.Connection, jobs: list[dict[str, Any]]) -> None:
    """批量补齐当前详情/列表和逐次报告；原有诊断优先，来源改变时不沿用导入记录。"""

    if not jobs:
        return
    placeholders = ",".join("?" for _ in jobs)
    rows = db.execute(f"""SELECT d.*,j.attempts,j.status AS current_status,
        j.result_json AS current_result,a.result_json AS attempt_result,a.status AS attempt_status
        FROM review_historical_diagnostics d JOIN review_jobs j ON j.id=d.job_id
        LEFT JOIN review_attempts a ON a.job_id=d.job_id AND a.attempt_number=d.attempt_number
        WHERE d.job_id IN ({placeholders}) AND d.head_sha=j.commit_sha
        AND d.base_sha IS j.base_sha""", [job["id"] for job in jobs]).fetchall()
    by_job = {job["id"]: job for job in jobs}
    for row in rows:
        job = by_job[row["job_id"]]
        source_valid = (row["source_kind"] == "job" or
                        row["attempt_result"] == row["source_result_json"] and
                        row["attempt_status"] == row["source_status"])
        if not source_valid:
            continue
        analysis = json.loads(row["analysis_json"])
        for attempt in job.get("attempt_history", []):
            if (attempt["attempt_number"] == row["attempt_number"] and
                    attempt.get("result_json") == row["source_result_json"] and
                    attempt["status"] == row["source_status"]):
                attempt["historical_failure_analysis"] = analysis
        if (row["attempt_number"] != row["attempts"] or
                row["current_status"] != row["source_status"] or
                row["current_result"] != row["source_result_json"]):
            continue
        result = job.get("result")
        if isinstance(result, dict) and result.get("failure_analysis"):
            continue
        job["failure_summary"] = analysis["summary"]
        job["failure_analysis_imported_at"] = row["imported_at"]
        if isinstance(result, dict):
            # 只修改返回投影，绝不 UPDATE 初审结果；有效结论指针和摘要保持不变。
            result["failure_analysis"] = analysis

