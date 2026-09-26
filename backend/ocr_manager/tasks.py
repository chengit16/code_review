"""查询任务分页和构造脱敏报告；不运行 Git 或读取原始 OCR 工件。"""

from __future__ import annotations

import json
from typing import Any

from ocr_manager.storage import Store


def search_jobs(store: Store, filters: dict[str, Any], page: int, page_size: int) -> dict[str, Any]:
    """使用参数化 SQL 检索全量历史，以 ID 降序稳定分页。"""

    clauses: list[str] = []
    values: list[Any] = []
    for field in ("repository_id", "status", "target_branch", "mr_iid"):
        if filters.get(field) is not None:
            clauses.append(f"j.{field}=?")
            values.append(filters[field])
    if filters.get("sha"):
        clauses.append("j.commit_sha LIKE ?")
        values.append(f"{filters['sha']}%")
    for field, operator in (("since", ">="), ("until", "<=")):
        if filters.get(field):
            clauses.append(f"j.created_at {operator} ?")
            values.append(filters[field])
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with store.connection() as db:
        # 数量和数据在同一读事务内，避免 Worker 更新时出现自相矛盾的分页结果。
        db.execute("BEGIN")
        total = db.execute(f"SELECT COUNT(*) FROM review_jobs j{where}", values).fetchone()[0]
        rows = db.execute(
            f"""SELECT j.id, j.repository_id, j.event_id, j.mr_iid, j.commit_sha,
            j.ordinal, j.target_branch, j.status, j.error, j.attempts,
            j.failure_stage, j.started_at, j.created_at, j.finished_at,
            r.name AS repository_name FROM review_jobs j
            JOIN repositories r ON r.id=j.repository_id{where}
            ORDER BY j.id DESC LIMIT ? OFFSET ?""",
            [*values, page_size, (page - 1) * page_size],
        )
        return {"items": [dict(row) for row in rows], "total": total,
                "page": page, "page_size": page_size}


def set_job_stage(store: Store, job_id: int, stage: str) -> None:
    """阶段先持久化，进程中断后仍能定位最后执行步骤。"""

    with store.connection() as db:
        db.execute("UPDATE review_jobs SET failure_stage=? WHERE id=? AND status='running'",
                   (stage, job_id))


def report_projection(job: dict[str, Any]) -> dict[str, Any]:
    """固定字段导出，覆盖项只导出数量，避免嵌套模型推理或工件路径泄漏。"""

    result = job.get("result") or {}
    manifest = result.get("manifest") or {}
    coverage = manifest.get("coverage") or {}
    preview = result.get("preview") or {}
    return {
        "job": {key: job.get(key) for key in (
            "id", "repository_id", "mr_iid", "commit_sha", "target_branch", "status",
            "failure_stage", "error", "attempts", "created_at", "finished_at",
        )},
        "comments": result.get("comments", []),
        "coverage": {key: len(coverage.get(key) or []) for key in (
            "selected", "completed", "reused", "failed", "waived",
        )},
        "files": [{key: item.get(key) for key in ("path", "will_review", "exclude_reason")}
                  for item in preview.get("files", []) if isinstance(item, dict)],
        "changed_files": json.loads(job["changed_files"]) if job.get("changed_files") else [],
        "attempts": [{key: item.get(key) for key in (
            "attempt_number", "status", "error", "failure_stage", "finished_at",
        )} for item in job["attempt_history"]],
        "delivery": job.get("delivery"),
    }
