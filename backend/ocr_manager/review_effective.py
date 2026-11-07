"""统一有效结论选择及提升；短事务内校验 SQLite 证据并建立补充投递，不调用外部服务。"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from ocr_manager.review_conclusions import read_conclusion

# 全量重审刚排队即隐藏旧版本；候选损坏或失去验证指针时保守保留初审状态。
EFFECTIVE = """SELECT e.* FROM review_effective_conclusions e
 JOIN review_jobs j ON j.id=e.job_id AND j.attempts=e.source_attempt
 JOIN review_recovery_aggregates a ON a.job_id=e.job_id
 AND a.source_attempt=e.source_attempt AND a.revision=e.revision AND a.recovery_id=e.recovery_id
 JOIN review_recoveries b ON b.id=e.recovery_id AND b.status IN ('complete','partial')
 WHERE j.status='partial' AND j.cancel_requested=0 AND NOT EXISTS (
 SELECT 1 FROM review_recovery_aggregates n WHERE n.job_id=e.job_id
 AND n.source_attempt=e.source_attempt AND n.revision>e.revision)"""


def status_sql(alias: str = "j") -> str:
    """仅由内部固定别名生成表达式；筛选、列表、首页及运维使用同一有效版本。"""

    return (f"COALESCE((SELECT json_extract(e.document_json,'$.version.terminal_state') "
            f"FROM ({EFFECTIVE}) e WHERE e.job_id={alias}.id),{alias}.status)")


def promote(db: sqlite3.Connection, job_id: int) -> None:
    """调用方持有终态写事务；完整来源校验通过才提升，并同事务创建唯一补充投递。"""

    document = read_conclusion(db, job_id)
    if document.version.revision == 0:
        raise ValueError("有效补审结论缺少候选版本")
    document.consumer_integration_ready = True
    document.role = "effective"
    severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    highest = max((item.severity for item in document.findings),
                  key=lambda value: severity_order.get(value or "", 0), default=None)
    values = (job_id, document.version.source_attempt, document.version.revision,
              document.version.recovery_id, document.model_dump_json())
    db.execute("""INSERT INTO review_effective_conclusions
        (job_id,source_attempt,revision,recovery_id,document_json,highest_severity)
        VALUES(?,?,?,?,?,?) ON CONFLICT(job_id) DO UPDATE SET
        source_attempt=excluded.source_attempt,revision=excluded.revision,
        recovery_id=excluded.recovery_id,document_json=excluded.document_json,
        highest_severity=excluded.highest_severity""", (*values, highest))
    db.execute("""INSERT INTO review_recovery_deliveries
        (job_id,source_attempt,revision,recovery_id,document_json) VALUES(?,?,?,?,?)""", values)


def attach_effective(db: sqlite3.Connection, jobs: list[dict[str, Any]], *,
                     detail: bool = False) -> None:
    """批量读取白名单投影；列表不加载发现正文，详情按稳定身份关联反馈和问题。"""

    for offset in range(0, len(jobs), 500):
        chunk = jobs[offset:offset + 500]
        marks = ",".join("?" for _ in chunk)
        projection = "e.document_json" if detail else "NULL AS document_json"
        rows = db.execute(f"""SELECT e.job_id,e.highest_severity,{projection},
            json_extract(e.document_json,'$.version') AS version FROM ({EFFECTIVE}) e
            WHERE e.job_id IN ({marks})""", [job["id"] for job in chunk]).fetchall()
        selected = {row["job_id"]: dict(row) for row in rows}
        for job in chunk:
            job["effective_status"] = job["status"]
            job["effective_conclusion"] = None
            row = selected.get(job["id"])
            if row is None:
                continue
            version = json.loads(row["version"])
            job["effective_status"] = version["terminal_state"]
            job["effective_conclusion"] = version
            if job.get("conclusions"):
                job["conclusions"]["consumer_integration_ready"] = True
                job["conclusions"]["effective"] = version
            job["finding_count"] = version["finding_count"]
            job["highest_severity"] = row["highest_severity"]
            if detail:
                # 详情再次完整校验，防止异常证据被当作无发现或成功；列表使用写时验证投影。
                document = read_conclusion(db, job["id"], source_attempt=version["source_attempt"],
                                           revision=version["revision"])
                document.consumer_integration_ready = True
                document.role = "effective"
                job["effective_document"] = document.model_dump()
                identities = {item.finding_id for item in document.findings}
                job["finding_feedback"] = {item["finding_id"]: item["verdict"] for item in
                    db.execute("""SELECT f.* FROM review_finding_feedback f
                    JOIN review_issue_occurrences o ON o.finding_id=f.finding_id
                    WHERE o.job_id=? AND o.attempt_number=?""",
                    (job["id"], version["source_attempt"])) if item["finding_id"] in identities}
                job["finding_issues"] = {item["finding_id"]: {
                    "id": item["issue_id"], "status": item["status"]} for item in db.execute("""
                    SELECT o.finding_id,o.issue_id,i.status FROM review_issue_occurrences o
                    JOIN review_issues i ON i.id=o.issue_id
                    WHERE o.job_id=? AND o.attempt_number=?""",
                    (job["id"], version["source_attempt"])) if item["finding_id"] in identities}
