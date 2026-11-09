"""统一任务当前发现与问题处置的只读投影；不推断修复、不改写问题或调用外部服务。"""

from __future__ import annotations

import sqlite3
from typing import Any

from ocr_manager.review_effective import EFFECTIVE

# 发现先固定到当前有效版本，再解析合并目标；缺失、循环和超长链均保留未知，不能算已关闭。
TASK_FACTS_CTE = f"""WITH RECURSIVE
effective AS ({EFFECTIVE}),
sources AS (
    SELECT j.id AS job_id,j.attempts,j.status,
        CASE WHEN json_valid(j.result_json) THEN j.result_json ELSE '{{}}' END AS result,
        CASE WHEN json_valid(j.scope_json) THEN j.scope_json ELSE '{{}}' END AS scope,
        e.document_json AS effective_document,
        COALESCE(json_extract(e.document_json,'$.version.terminal_state'),j.status)
            AS effective_status,
        (SELECT b.status FROM review_recoveries b WHERE b.job_id=j.id
            AND b.source_attempt=j.attempts AND b.status IN ('queued','running')
            ORDER BY b.id DESC LIMIT 1) AS recovery_status
    FROM review_jobs j LEFT JOIN effective e ON e.job_id=j.id
), versions AS (
    SELECT s.*,
        CASE WHEN effective_document IS NOT NULL THEN effective_document
            ELSE json_object('findings',json_extract(result,'$.comments'),
                'version',json_object('coverage',json_object(
                    'selected',json_array_length(result,'$.manifest.coverage.selected'),
                    'completed',json_array_length(result,'$.manifest.coverage.completed'),
                    'reused',json_array_length(result,'$.manifest.coverage.reused'),
                    'failed',json_array_length(result,'$.manifest.coverage.failed'),
                    'waived',json_array_length(result,'$.manifest.coverage.waived'))))
            END AS document,
        CASE WHEN effective_document IS NOT NULL THEN 1
            WHEN status IN ('complete','partial') AND json_type(result,'$.comments')='array'
            THEN 1 ELSE 0 END AS available
    FROM sources s
), current_findings AS (
    SELECT v.job_id,
        CASE WHEN v.effective_document IS NOT NULL THEN json_extract(f.value,'$.finding_id')
            ELSE 'j'||v.job_id||':a'||v.attempts||':c'||f.key END AS finding_id,
        json_extract(f.value,'$.severity') AS severity
    FROM versions v JOIN json_each(v.document,'$.findings') f WHERE v.available=1
), targets(source_id,target_id,status,merged_into_id,depth,visited) AS (
    SELECT i.id,i.id,i.status,i.merged_into_id,0,','||i.id||',' FROM review_issue_states i
    WHERE i.id IN (SELECT o.issue_id FROM current_findings f
        JOIN review_issue_occurrences o ON o.finding_id=f.finding_id)
    UNION ALL
    SELECT t.source_id,n.id,n.status,n.merged_into_id,t.depth+1,t.visited||n.id||','
    FROM targets t JOIN review_issue_states n ON n.id=t.merged_into_id
    WHERE t.status='merged' AND t.depth<32 AND instr(t.visited,','||n.id||',')=0
), leaves AS (
    SELECT t.* FROM targets t WHERE NOT EXISTS (
        SELECT 1 FROM targets n WHERE n.source_id=t.source_id AND n.depth>t.depth)
), mapped AS (
    SELECT f.job_id,f.finding_id,
        CASE WHEN t.status IN ('open','fixed','ignored','false_positive')
            THEN t.target_id END AS issue_id,
        CASE WHEN t.status IN ('open','fixed','ignored','false_positive')
            THEN t.status END AS issue_status
    FROM current_findings f LEFT JOIN review_issue_occurrences o ON o.finding_id=f.finding_id
    LEFT JOIN leaves t ON t.source_id=o.issue_id
), unique_issues AS (
    SELECT job_id,issue_id,issue_status FROM mapped
    GROUP BY job_id,CASE WHEN issue_id IS NULL THEN 'missing:'||finding_id
        ELSE 'issue:'||issue_id END
), counts AS (
    SELECT job_id,
        SUM(issue_status='open') AS open_count,
        SUM(issue_status='fixed') AS fixed_count,
        SUM(issue_status='ignored') AS ignored_count,
        SUM(issue_status='false_positive') AS false_positive_count,
        SUM(issue_status IS NULL) AS unknown_count
    FROM unique_issues GROUP BY job_id
), facts AS (
    SELECT v.job_id,v.effective_status,v.recovery_status,v.available,
        COALESCE(v.recovery_status,v.effective_status) AS list_status,
        CASE WHEN v.available=1 THEN json_array_length(v.document,'$.findings')
            END AS finding_count,
        (SELECT f.severity FROM current_findings f WHERE f.job_id=v.job_id
            ORDER BY CASE f.severity WHEN 'critical' THEN 4 WHEN 'high' THEN 3
                WHEN 'medium' THEN 2 WHEN 'low' THEN 1 ELSE 0 END DESC LIMIT 1)
            AS highest_severity,
        COALESCE(c.open_count,0) AS open_count,COALESCE(c.fixed_count,0) AS fixed_count,
        COALESCE(c.ignored_count,0) AS ignored_count,
        COALESCE(c.false_positive_count,0) AS false_positive_count,
        COALESCE(c.unknown_count,0) AS unknown_count,
        CASE WHEN v.available=1 AND COALESCE(c.unknown_count,0)=0 THEN 1 ELSE 0 END AS complete,
        CASE WHEN COALESCE(json_extract(v.scope,'$.excluded_count'),0)>0
            OR COALESCE(json_extract(v.result,'$.input_filter.excluded_count'),0)>0
            OR COALESCE(json_extract(v.result,'$.preview.excluded_count'),0)>0
            OR EXISTS (SELECT 1 FROM json_each(v.result,'$.preview.files') p
                WHERE json_extract(p.value,'$.will_review')=0)
            OR COALESCE(json_extract(v.document,'$.version.coverage.waived'),0)>0
            THEN 1 ELSE 0 END AS coverage_limited,
        CASE WHEN json_type(v.document,'$.version.coverage.selected')='integer'
            AND json_type(v.document,'$.version.coverage.completed')='integer'
            AND json_type(v.document,'$.version.coverage.reused')='integer'
            AND json_extract(v.document,'$.version.coverage.failed')=0
            AND json_extract(v.document,'$.version.coverage.waived')=0
            AND json_extract(v.document,'$.version.coverage.selected')=
                json_extract(v.document,'$.version.coverage.completed')+
                json_extract(v.document,'$.version.coverage.reused')
            THEN 1 ELSE 0 END AS coverage_complete
    FROM versions v LEFT JOIN counts c ON c.job_id=v.job_id
), task_facts AS (
    SELECT f.*,
        CASE WHEN available=1 AND complete=1 AND finding_count=0 AND effective_status='complete'
            AND coverage_complete=1 AND coverage_limited=0 THEN 1 ELSE 0 END AS no_findings,
        CASE WHEN available=1 AND complete=1 AND finding_count>0 AND open_count=0
            THEN 1 ELSE 0 END AS resolved,
        CASE WHEN (available=1 AND complete=0) OR
            (available=0 AND effective_status IN ('complete','partial'))
            THEN 1 ELSE 0 END AS unknown
    FROM facts f
)"""


def attach_task_facts(db: sqlite3.Connection, jobs: list[dict[str, Any]], *,
                      detail: bool = False) -> None:
    """同一读事务批量附加摘要；详情同时解析合并目标，确保待处理入口与数字对应。"""

    for offset in range(0, len(jobs), 500):
        chunk = jobs[offset:offset + 500]
        ids = [job["id"] for job in chunk]
        marks = ",".join("?" for _ in ids)
        # 1. 列表只取计数和范围标记，不返回发现正文或合并链。
        rows = db.execute(f"{TASK_FACTS_CTE} SELECT * FROM task_facts WHERE job_id IN ({marks})",
                          ids).fetchall()
        facts = {row["job_id"]: dict(row) for row in rows}
        for job in chunk:
            fact = facts[job["id"]]
            job["list_status"] = fact["list_status"]
            job["active_recovery_status"] = fact["recovery_status"]
            job["issue_summary"] = {key: fact[key] for key in (
                "available", "finding_count", "highest_severity", "open_count", "fixed_count",
                "ignored_count", "false_positive_count", "unknown_count", "complete",
                "no_findings", "coverage_limited",
                "coverage_complete")}
        if not detail:
            continue
        # 2. 映射仍保留原发现身份，只把问题目标解析到最终人工决策，不修改出现或反馈记录。
        mapped = db.execute(f"{TASK_FACTS_CTE} SELECT * FROM mapped WHERE job_id IN ({marks})",
                            ids).fetchall()
        for job in chunk:
            job["resolved_finding_issues"] = {
                row["finding_id"]: {"id": row["issue_id"], "status": row["issue_status"]}
                for row in mapped if row["job_id"] == job["id"] and row["issue_id"] is not None}
