"""查询任务分页和构造脱敏报告；不运行 Git 或读取原始 OCR 工件。"""

from __future__ import annotations

import json
from typing import Any

from ocr_manager.model_pricing import estimate_cost
from ocr_manager.review_effective import status_sql
from ocr_manager.review_observability import enrich_jobs
from ocr_manager.storage import Store


def task_view_clause(view: str | None) -> str | None:
    """快捷视图与首页共用口径；同一输入被后续完整评审覆盖后不再算未恢复异常。"""

    if view == "active":
        return ("j.status IN ('queued','running') OR EXISTS (SELECT 1 FROM "
                "review_recoveries b WHERE b.job_id=j.id AND b.status IN ('queued','running'))")
    if view == "notification_failed":
        return ("EXISTS (SELECT 1 FROM notification_deliveries d "
                "WHERE d.job_id=j.id AND d.status='failed') OR EXISTS (SELECT 1 FROM "
                "review_recovery_deliveries s WHERE s.job_id=j.id AND s.source_attempt=j.attempts "
                "AND j.status='partial' AND s.status='failed')")
    if view == "attention":
        return f"""{status_sql()} IN ('failed','partial') AND NOT EXISTS (
            SELECT 1 FROM review_jobs n WHERE n.repository_id=j.repository_id
            AND n.mr_iid=j.mr_iid AND n.commit_sha=j.commit_sha
            AND COALESCE(n.base_sha,'')=COALESCE(j.base_sha,'')
            AND n.id>j.id AND {status_sql('n')}='complete')"""
    return None


def _job_filters(filters: dict[str, Any]) -> tuple[list[str], list[Any]]:
    """列表和详情导航共享筛选语义，字段名固定，用户值始终参数化。"""

    clauses: list[str] = []
    values: list[Any] = []
    view = task_view_clause(filters.get("view"))
    if view:
        clauses.append(f"({view})")
    for field in ("repository_id", "status", "target_branch", "mr_iid"):
        if filters.get(field) is not None:
            clauses.append(f"{status_sql() if field == 'status' else f'j.{field}'}=?")
            values.append(filters[field])
    if filters.get("sha"):
        clauses.append("j.commit_sha LIKE ?")
        values.append(f"{filters['sha']}%")
    for field, operator in (("since", ">="), ("until", "<=")):
        if filters.get(field):
            clauses.append(f"j.created_at {operator} ?")
            values.append(filters[field])
    return clauses, values


def search_jobs(store: Store, filters: dict[str, Any], page: int, page_size: int) -> dict[str, Any]:
    """使用参数化 SQL 检索全量历史，以 ID 降序稳定分页。"""

    clauses, values = _job_filters(filters)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with store.connection() as db:
        # 数量和数据在同一读事务内，避免 Worker 更新时出现自相矛盾的分页结果。
        db.execute("BEGIN")
        total = db.execute(f"SELECT COUNT(*) FROM review_jobs j{where}", values).fetchone()[0]
        rows = db.execute(
            f"""SELECT j.id, j.repository_id, j.event_id, j.mr_iid, j.commit_sha, j.commit_author,
            j.ordinal, j.target_branch, j.status, j.error, j.attempts,
            j.failure_stage, j.started_at, j.created_at, j.finished_at,
            j.usage_json, j.config_snapshot,
            CASE WHEN json_valid(j.scope_json) THEN
              json_remove(j.scope_json,'$.newline_only_paths') END AS scope_json,
            j.reason_code, j.next_run_at,
            CASE WHEN json_valid(j.result_json) THEN
              json_extract(j.result_json,'$.failure_analysis.summary') END AS failure_summary,
            r.name AS repository_name,
            (SELECT COUNT(*) FROM review_issue_occurrences o WHERE o.job_id=j.id
              AND o.attempt_number=j.attempts AND o.recovery_id IS NULL) AS finding_count,
            (SELECT o.severity FROM review_issue_occurrences o WHERE o.job_id=j.id
              AND o.attempt_number=j.attempts AND o.recovery_id IS NULL ORDER BY CASE o.severity
              WHEN 'critical' THEN 4 WHEN 'high' THEN 3 WHEN 'medium' THEN 2
              WHEN 'low' THEN 1 ELSE 0 END DESC LIMIT 1) AS highest_severity,
            (SELECT d.status FROM notification_deliveries d WHERE d.job_id=j.id)
              AS delivery_status FROM review_jobs j
            JOIN repositories r ON r.id=j.repository_id{where}
            ORDER BY j.id DESC LIMIT ? OFFSET ?""",
            [*values, page_size, (page - 1) * page_size],
        )
        items: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            raw_usage = item.pop("usage_json")
            raw_snapshot = item.pop("config_snapshot")
            usage = json.loads(raw_usage) if raw_usage else None
            snapshot = json.loads(raw_snapshot) if raw_snapshot else None
            item["usage"] = usage
            item["estimated_cost"] = estimate_cost(usage, snapshot)
            items.append(item)
        enrich_jobs(db, items)
        return {"items": items, "total": total, "page": page, "page_size": page_size}


def job_neighbors(store: Store, job_id: int, filters: dict[str, Any]) -> dict[str, int | None]:
    """查找降序列表中相邻任务，跨分页和编号空洞；当前任务消失时拒绝导航。"""

    clauses, values = _job_filters(filters)
    with store.connection() as db:
        # 同一快照核对任务与邻项；状态已离开筛选时仍以当前编号作为导航锚点。
        db.execute("BEGIN")
        if db.execute("SELECT id FROM review_jobs WHERE id=?", (job_id,)).fetchone() is None:
            raise LookupError("任务不存在")
        neighbors: dict[str, int | None] = {}
        for direction, operator, order in (("previous_id", ">", "ASC"), ("next_id", "<", "DESC")):
            where = " AND ".join([*clauses, f"j.id {operator} ?"])
            row = db.execute(
                f"SELECT j.id FROM review_jobs j WHERE {where} ORDER BY j.id {order} LIMIT 1",
                [*values, job_id],
            ).fetchone()
            neighbors[direction] = row["id"] if row else None
        return neighbors


def set_job_stage(store: Store, job_id: int, stage: str) -> None:
    """阶段先持久化，进程中断后仍能定位最后执行步骤。"""

    with store.connection() as db:
        job = db.execute("SELECT attempts,status,failure_stage FROM review_jobs WHERE id=?",
                         (job_id,)).fetchone()
        if not job or job["status"] != "running":
            return
        current = db.execute("SELECT stage FROM review_stage_timings WHERE job_id=? "
                             "AND finished_at IS NULL", (job_id,)).fetchone()
        if current is None or current["stage"] != stage:
            db.execute("UPDATE review_stage_timings SET finished_at=CURRENT_TIMESTAMP "
                       "WHERE job_id=? AND finished_at IS NULL", (job_id,))
            db.execute("INSERT INTO review_stage_timings(job_id,attempt_number,stage) "
                       "VALUES(?,?,?)",
                       (job_id, job["attempts"], stage))
        db.execute("UPDATE review_jobs SET failure_stage=? WHERE id=?", (stage, job_id))


def report_projection(job: dict[str, Any]) -> dict[str, Any]:
    """固定字段导出，覆盖项只导出数量，避免嵌套模型推理或工件路径泄漏。"""

    result = job.get("result") or {}
    manifest = result.get("manifest") or {}
    coverage = manifest.get("coverage") or {}
    preview = result.get("preview") or {}
    snapshot = public_snapshot(job.get("config_snapshot"))
    report: dict[str, Any] = {
        "job": {key: job.get(key) for key in (
            "id", "repository_id", "mr_iid", "commit_sha", "target_branch", "status",
            "failure_stage", "error", "attempts", "created_at", "finished_at",
        )},
        "comments": result.get("comments", []),
        "effective_status": job.get("effective_status", job.get("status")),
        "effective_conclusion": job.get("effective_document"),
        "initial_cumulative_usage": job.get("initial_cumulative_usage"),
        "conclusions": job.get("conclusions"),
        "timing": job.get("timing"),
        "reason": job.get("reason"),
        "scope_analysis": job.get("scope_analysis"),
        "cumulative_usage": job.get("cumulative_usage"),
        "diagnostic": result.get("diagnostic"),
        "retry_summary": result.get("retry_summary"),
        "failure_analysis": result.get("failure_analysis"),
        "stage_timings": [{key: stage.get(key) for key in (
            "attempt_number", "stage", "started_at", "finished_at")}
            for stage in job.get("stage_timings", [])],
        "usage": result.get("usage"),
        "estimated_cost": estimate_cost(result.get("usage"), snapshot),
        "coverage": {key: len(coverage.get(key) or []) for key in (
            "selected", "completed", "reused", "failed", "waived",
        )},
        "files": [{key: item.get(key) for key in ("path", "will_review", "exclude_reason")}
                  for item in preview.get("files", []) if isinstance(item, dict)],
        "changed_files": json.loads(job["changed_files"]) if job.get("changed_files") else [],
        "attempts": [{key: item.get(key) for key in (
            "attempt_number", "status", "error", "failure_stage", "started_at", "finished_at",
            "scheduled_at", "retry_ready_at", "reason_code",
        )} for item in job["attempt_history"]],
        "delivery": job.get("delivery"),
        "configuration": snapshot,
    }
    effective = job.get("effective_document")
    if effective:
        report["initial_review"] = {"status": job["status"], **{key: report[key] for key in (
            "comments", "coverage", "reason", "diagnostic", "retry_summary", "failure_analysis",
            "usage", "estimated_cost")}}
        report["reason"] = {"code": job["effective_status"], "message": (
            "当前有效覆盖已完成；初审故障证据单独保留" if job["effective_status"] == "complete"
            else "补审后仍有失败覆盖；初审故障证据单独保留")}
        report["diagnostic"] = report["retry_summary"] = report["failure_analysis"] = None
        report["usage_scope"] = "initial_attempt"
        report["version_execution_usage"] = effective["execution_usage"]
        report["comments"] = effective["findings"]
        report["coverage"] = effective["version"]["coverage"]
        report["job"]["status"] = job["effective_status"]
    return report


def public_snapshot(raw: str | dict[str, Any] | None) -> dict[str, Any] | None:
    """快照仅展示配置事实，OCR 可执行文件的本机路径不进入报告。"""

    snapshot = json.loads(raw) if isinstance(raw, str) else raw
    if not snapshot:
        return None
    return snapshot | {"command": {key: value for key, value in snapshot["command"].items()
                                   if key != "path"}}
