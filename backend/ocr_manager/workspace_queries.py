"""工作台的只读聚合与合并前版本检索；只读取 SQLite，不调用外部系统或修改业务状态。"""

from __future__ import annotations

from typing import Any

from ocr_manager.overview_scopes import (
    EVENT_ACTIONABLE_SCOPE,
    LATEST_PREMERGE_SCOPE,
    OPEN_ISSUE_SCOPE,
    PREMERGE_ACTIONABLE_SCOPE,
)
from ocr_manager.premerge_summary import premerge_summary
from ocr_manager.review_conclusions import candidate_counts
from ocr_manager.review_effective import status_sql
from ocr_manager.storage import Store
from ocr_manager.tasks import search_jobs, task_view_clause


def overview_snapshot(store: Store) -> dict[str, Any]:
    """统计所有历史任务；未恢复异常与历史失败分开，后续完整结果只覆盖相同输入。"""

    with store.connection() as db:
        db.execute("BEGIN")
        summary = dict(db.execute(f"""SELECT COUNT(*) AS total,
            SUM(status='queued') AS queued, SUM(status='running') AS running,
            SUM({status_sql()}='complete') AS complete, SUM(status='failed') AS historical_failed
            FROM review_jobs j""").fetchone())
        summary = {key: value or 0 for key, value in summary.items()}
        summary["repositories"] = db.execute("SELECT COUNT(*) FROM repositories").fetchone()[0]
        conclusions = candidate_counts(db)
        todo = {"events_attention": db.execute(
            f"""SELECT COUNT(*) FROM merge_events e
            WHERE e.status='needs_attention' AND {EVENT_ACTIONABLE_SCOPE}"""
        ).fetchone()[0]}
        for state in ("failed", "partial"):
            todo[f"premerge_{state}"] = db.execute(
                f"""SELECT COUNT(*) FROM premerge_reviews p WHERE p.status=?
                AND {PREMERGE_ACTIONABLE_SCOPE} AND {LATEST_PREMERGE_SCOPE}""", (state,)
            ).fetchone()[0]
        severity_counts = dict.fromkeys(("critical", "high", "medium", "low", "unclassified"), 0)
        for row in db.execute(f"""SELECT CASE WHEN i.severity IN
                ('critical','high','medium','low') THEN i.severity ELSE 'unclassified' END AS level,
                COUNT(*) AS count FROM review_issues i WHERE {OPEN_ISSUE_SCOPE} GROUP BY level"""):
            severity_counts[row["level"]] = row["count"]
        issue_todo = {"open_count": sum(severity_counts.values()),
                      "severity_counts": severity_counts}
        # 与活动视图共用集合；多条活动补审仍只计一个任务，运行优先。
        activity = dict(db.execute(f"""SELECT COUNT(*) AS total,
            COALESCE(SUM(is_running),0) AS running,
            COALESCE(SUM(NOT is_running),0) AS queued FROM (
                SELECT j.status='running' OR EXISTS (SELECT 1 FROM review_recoveries b
                    WHERE b.job_id=j.id AND b.status='running') AS is_running
                FROM review_jobs j WHERE {task_view_clause('active')})""").fetchone())
        for key, view in (("attention", "attention"),
                          ("notification_failed", "notification_failed")):
            summary[key] = db.execute(
                f"SELECT COUNT(*) FROM review_jobs j WHERE {task_view_clause(view)}"
            ).fetchone()[0]
    return {"summary": summary, "todo": todo, "issue_todo": issue_todo,
            "activity": activity, "conclusion_candidates": conclusions,
            "recent": search_jobs(store, {}, 1, 8)["items"]}


def search_premerge(store: Store, repository_id: int | None, mr_iid: int | None,
                    status: str | None, latest_only: bool, page: int,
                    page_size: int, summary_only: bool = False,
                    actionable_only: bool = False) -> dict[str, Any]:
    """在同一读快照中返回计数与分页；最新版本判断先于状态筛选。"""

    clauses: list[str] = []
    args: list[Any] = []
    for field, value in (("repository_id", repository_id), ("mr_iid", mr_iid)):
        if value is not None:
            clauses.append(f"p.{field}=?")
            args.append(value)
    if latest_only:
        clauses.append(LATEST_PREMERGE_SCOPE)
    if actionable_only:
        clauses.append(PREMERGE_ACTIONABLE_SCOPE)
    facet_where = " WHERE " + " AND ".join(clauses) if clauses else ""
    facet_args = list(args)
    if status is not None:
        clauses.append("p.status=?")
        args.append(status)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with store.connection() as db:
        db.execute("BEGIN")
        counts = {row["status"]: row["count"] for row in db.execute(
            f"SELECT p.status,COUNT(*) AS count FROM premerge_reviews p{facet_where} "
            "GROUP BY p.status", facet_args)}
        counts["all"] = sum(counts.values())
        total = db.execute(f"SELECT COUNT(*) FROM premerge_reviews p{where}", args).fetchone()[0]
        rows = db.execute(f"""SELECT p.*,r.name AS repository_name
            FROM premerge_reviews p JOIN repositories r ON r.id=p.repository_id
            {where} ORDER BY p.id DESC LIMIT ? OFFSET ?""",
            [*args, page_size, (page - 1) * page_size]).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["summary"] = premerge_summary(item["result_json"])
        if summary_only:
            for field in ("result_json", "context_json", "changed_files"):
                item.pop(field, None)
        items.append(item)
    return {"items": items, "total": total, "status_counts": counts,
            "page": page, "page_size": page_size}
