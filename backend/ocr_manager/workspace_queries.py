"""工作台的只读聚合与合并前版本检索；只读取 SQLite，不调用外部系统或修改业务状态。"""

from __future__ import annotations

from typing import Any

from ocr_manager.storage import Store
from ocr_manager.tasks import search_jobs, task_view_clause


def overview_snapshot(store: Store) -> dict[str, Any]:
    """统计所有历史任务；未恢复异常与历史失败分开，后续完整结果只覆盖相同输入。"""

    with store.connection() as db:
        db.execute("BEGIN")
        summary = dict(db.execute("""SELECT COUNT(*) AS total,
            SUM(status='queued') AS queued, SUM(status='running') AS running,
            SUM(status='complete') AS complete, SUM(status='failed') AS historical_failed
            FROM review_jobs""").fetchone())
        summary = {key: value or 0 for key, value in summary.items()}
        summary["repositories"] = db.execute("SELECT COUNT(*) FROM repositories").fetchone()[0]
        todo = {"events_attention": db.execute(
            """SELECT COUNT(*) FROM merge_events e JOIN repositories r ON r.id=e.repository_id
            WHERE e.status='needs_attention' AND r.enabled=1"""
        ).fetchone()[0], "premerge_failed": db.execute(
            """SELECT COUNT(*) FROM premerge_reviews p
            JOIN repositories r ON r.id=p.repository_id
            JOIN premerge_settings s ON s.repository_id=p.repository_id
            WHERE p.status='failed' AND r.enabled=1 AND s.enabled=1
            AND NOT EXISTS (SELECT 1 FROM premerge_reviews n
                WHERE n.repository_id=p.repository_id AND n.mr_iid=p.mr_iid AND n.id>p.id)"""
        ).fetchone()[0], "premerge_partial": db.execute(
            """SELECT COUNT(*) FROM premerge_reviews p
            JOIN repositories r ON r.id=p.repository_id
            JOIN premerge_settings s ON s.repository_id=p.repository_id
            WHERE p.status='partial' AND r.enabled=1 AND s.enabled=1
            AND NOT EXISTS (SELECT 1 FROM premerge_reviews n
                WHERE n.repository_id=p.repository_id AND n.mr_iid=p.mr_iid AND n.id>p.id)"""
        ).fetchone()[0]}
        for key, view in (("attention", "attention"),
                          ("notification_failed", "notification_failed")):
            summary[key] = db.execute(
                f"SELECT COUNT(*) FROM review_jobs j WHERE {task_view_clause(view)}"
            ).fetchone()[0]
    return {"summary": summary, "todo": todo, "recent": search_jobs(store, {}, 1, 8)["items"]}


def search_premerge(store: Store, repository_id: int | None, mr_iid: int | None,
                    status: str | None, latest_only: bool, page: int,
                    page_size: int) -> dict[str, Any]:
    """在同一读快照中返回计数与分页；最新版本判断先于状态筛选。"""

    clauses: list[str] = []
    args: list[Any] = []
    for field, value in (("repository_id", repository_id), ("mr_iid", mr_iid),
                         ("status", status)):
        if value is not None:
            clauses.append(f"p.{field}=?")
            args.append(value)
    if latest_only:
        clauses.append("""NOT EXISTS (SELECT 1 FROM premerge_reviews n
            WHERE n.repository_id=p.repository_id AND n.mr_iid=p.mr_iid AND n.id>p.id)""")
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with store.connection() as db:
        db.execute("BEGIN")
        total = db.execute(f"SELECT COUNT(*) FROM premerge_reviews p{where}", args).fetchone()[0]
        rows = db.execute(f"""SELECT p.*,r.name AS repository_name
            FROM premerge_reviews p JOIN repositories r ON r.id=p.repository_id
            {where} ORDER BY p.id DESC LIMIT ? OFFSET ?""",
            [*args, page_size, (page - 1) * page_size]).fetchall()
    return {"items": [dict(row) for row in rows], "total": total,
            "page": page, "page_size": page_size}
