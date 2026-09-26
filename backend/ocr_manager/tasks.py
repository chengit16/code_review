"""查询任务分页和构造脱敏报告；不运行 Git 或读取原始 OCR 工件。"""

from __future__ import annotations

import json
from typing import Any

from ocr_manager.model_pricing import estimate_cost
from ocr_manager.storage import Store


def _job_filters(filters: dict[str, Any]) -> tuple[list[str], list[Any]]:
    """列表和详情导航共享筛选语义，字段名固定，用户值始终参数化。"""

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
        db.execute("UPDATE review_jobs SET failure_stage=? WHERE id=? AND status='running'",
                   (stage, job_id))


def report_projection(job: dict[str, Any]) -> dict[str, Any]:
    """固定字段导出，覆盖项只导出数量，避免嵌套模型推理或工件路径泄漏。"""

    result = job.get("result") or {}
    manifest = result.get("manifest") or {}
    coverage = manifest.get("coverage") or {}
    preview = result.get("preview") or {}
    snapshot = public_snapshot(job.get("config_snapshot"))
    return {
        "job": {key: job.get(key) for key in (
            "id", "repository_id", "mr_iid", "commit_sha", "target_branch", "status",
            "failure_stage", "error", "attempts", "created_at", "finished_at",
        )},
        "comments": result.get("comments", []),
        "usage": result.get("usage"),
        "estimated_cost": estimate_cost(result.get("usage"), snapshot),
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
        "configuration": snapshot,
    }


def public_snapshot(raw: str | dict[str, Any] | None) -> dict[str, Any] | None:
    """快照仅展示配置事实，OCR 可执行文件的本机路径不进入报告。"""

    snapshot = json.loads(raw) if isinstance(raw, str) else raw
    if not snapshot:
        return None
    return snapshot | {"command": {key: value for key, value in snapshot["command"].items()
                                   if key != "path"}}
