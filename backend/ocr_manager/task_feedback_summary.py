"""批量投影任务当前发现的价值反馈；只读持久化事实，不推断或修改问题处置。"""

from __future__ import annotations

import sqlite3
from typing import Any

from ocr_manager.review_quality import COUNTS, QUALITY_CTE, VALID_FINDING


def attach_feedback_summary(db: sqlite3.Connection, jobs: list[dict[str, Any]]) -> None:
    """复用首页和发现列表的主身份与反馈读取；任务无日期筛选，缺损正文不能伪装为完成。"""

    for offset in range(0, len(jobs), 500):
        chunk = jobs[offset:offset + 500]
        marks = ",".join("?" for _ in chunk)
        # 同一集合只聚合主身份；无发现与缺失文档分别判断，避免把未读取当作零。
        rows = db.execute(f"""{QUALITY_CTE}, feedback_counts AS (
            SELECT job_id,{COUNTS} FROM current_findings WHERE {VALID_FINDING}
            GROUP BY job_id
        ) SELECT j.id,COALESCE(c.total,0) AS total,
            COALESCE(c.helpful,0) AS helpful,COALESCE(c.false_positive,0) AS false_positive,
            COALESCE(c.ignored,0) AS ignored,COALESCE(c.unmarked,0) AS unmarked,
            CASE WHEN json_valid(d.document) AND
                json_type(CASE WHEN json_valid(d.document)
                    THEN d.document ELSE '{{}}' END,CASE WHEN d.promoted=1 THEN '$.findings'
                    ELSE '$.comments' END)='array' AND
                json_array_length(CASE WHEN json_valid(d.document)
                    THEN d.document ELSE '{{}}' END,CASE WHEN d.promoted=1 THEN '$.findings'
                    ELSE '$.comments' END)=COALESCE(c.total,0)
                THEN 1 ELSE 0 END AS available
            FROM review_jobs j LEFT JOIN documents d ON d.job_id=j.id
            LEFT JOIN feedback_counts c ON c.job_id=j.id WHERE j.id IN ({marks})""",
            (None, None, "1970-01-01 00:00:00", "9999-12-31 00:00:00",
             "1970-01-01 00:00:00", "9999-12-31 00:00:00",
             *[job["id"] for job in chunk])).fetchall()
        summaries = {row["id"]: dict(row) for row in rows}
        for job in chunk:
            summary = summaries[job["id"]]
            job["feedback_summary"] = {
                "available": bool(summary["available"]),
                "total": summary["total"] if summary["available"] else None,
                **{key: summary[key] for key in (
                    "helpful", "false_positive", "ignored", "unmarked")},
            }
