"""按同一评审时间窗口衡量发现、发布与人工处理，避免混用分母。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, HTTPException, Query

if TYPE_CHECKING:
    from ocr_manager.storage import Store


EFFECTIVENESS_MIGRATION = """
ALTER TABLE review_issue_occurrences ADD COLUMN severity TEXT;
ALTER TABLE review_issue_occurrences ADD COLUMN category TEXT;
UPDATE review_issue_occurrences SET
  severity=(SELECT severity FROM review_issues WHERE id=issue_id),
  category=(SELECT category FROM review_issues WHERE id=issue_id);
CREATE INDEX idx_issue_occurrences_time ON review_issue_occurrences(created_at,issue_id);
CREATE INDEX idx_review_issues_first_seen ON review_issues(first_seen_at,repository_id);
"""


def effectiveness_snapshot(store: Store, repository_id: int | None,
                           days: int) -> dict[str, Any]:
    """发布日期以发现产生时的任务为准；处理状态仍显示当前人工结论。"""

    start_day = datetime.now(UTC).date() - timedelta(days=days - 1)
    since = f"{start_day.isoformat()} 00:00:00"
    scope = "(? IS NULL OR repository_id=?)"
    args = (repository_id, repository_id)
    with store.connection() as db:
        if repository_id is not None and not db.execute(
            "SELECT 1 FROM repositories WHERE id=?", (repository_id,)
        ).fetchone():
            raise HTTPException(404, "项目不存在")
        reviews = db.execute(f"""SELECT COUNT(*) AS finished,
            SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS failed
            FROM review_jobs WHERE {scope} AND finished_at>=? AND status IN
            ('complete','partial','failed','skipped')""", (*args, since)).fetchone()
        generated = db.execute("""SELECT COUNT(*) AS findings,
            SUM(CASE WHEN p.status='sent' THEN 1 ELSE 0 END) AS published
            FROM review_issue_occurrences o
            JOIN review_issues i ON i.id=o.issue_id
            LEFT JOIN gitlab_publications p ON p.job_id=o.job_id
              AND p.attempt_number=o.attempt_number AND p.comment_index=o.comment_index
            WHERE (? IS NULL OR i.repository_id=?) AND o.created_at>=?""",
            (*args, since)).fetchone()
        issues = db.execute(f"""SELECT COUNT(*) AS created,
            SUM(CASE WHEN status='open' THEN 1 ELSE 0 END) AS still_open
            FROM review_issues WHERE {scope} AND first_seen_at>=?""",
            (*args, since)).fetchone()
        fixed = db.execute(f"""SELECT COUNT(*) FROM review_issues WHERE {scope}
            AND status='fixed' AND closed_at>=?""", (*args, since)).fetchone()[0]
        ignored = db.execute(f"""SELECT COUNT(*) FROM review_issues WHERE {scope}
            AND status='ignored' AND closed_at>=?""", (*args, since)).fetchone()[0]
        open_now = db.execute(f"""SELECT COUNT(*) FROM review_issues WHERE {scope}
            AND status='open'""", args).fetchone()[0]
        feedback = db.execute("""SELECT COUNT(*) AS marked,
            SUM(CASE WHEN f.verdict='false_positive' THEN 1 ELSE 0 END) AS false_positive
            FROM review_feedback f JOIN review_jobs j ON j.id=f.job_id
            WHERE (? IS NULL OR j.repository_id=?) AND j.finished_at>=?""",
            (*args, since)).fetchone()
        categories = [dict(row) for row in db.execute("""SELECT
            COALESCE(NULLIF(o.category,''),'未分类') AS category,
            COUNT(*) AS generated, COUNT(DISTINCT o.issue_id) AS issues,
            COUNT(DISTINCT CASE WHEN i.status='open' THEN i.id END) AS open_issues
            FROM review_issue_occurrences o JOIN review_issues i ON i.id=o.issue_id
            WHERE (? IS NULL OR i.repository_id=?) AND o.created_at>=?
            GROUP BY COALESCE(NULLIF(o.category,''),'未分类')
            ORDER BY generated DESC,category LIMIT 20""", (*args, since))]
        new_by_day = {row["day"]: row["count"] for row in db.execute(f"""SELECT
            date(first_seen_at) AS day,COUNT(*) AS count FROM review_issues
            WHERE {scope} AND first_seen_at>=?
            GROUP BY date(first_seen_at)""", (*args, since))}
        fixed_by_day = {row["day"]: row["count"] for row in db.execute(f"""SELECT
            date(closed_at) AS day,COUNT(*) AS count FROM review_issues
            WHERE {scope} AND status='fixed' AND closed_at>=?
            GROUP BY date(closed_at)""", (*args, since))}
        projects = [dict(row) for row in db.execute("""SELECT r.id,r.name,
            (SELECT COUNT(*) FROM review_issues i WHERE i.repository_id=r.id
              AND i.status='open') AS open_issues,
            (SELECT COUNT(*) FROM review_issues i WHERE i.repository_id=r.id
              AND i.first_seen_at>=?) AS new_issues,
            (SELECT COUNT(*) FROM review_issues i WHERE i.repository_id=r.id
              AND i.status='fixed' AND i.closed_at>=?) AS fixed_issues,
            (SELECT COUNT(*) FROM review_issue_occurrences o JOIN review_issues i
              ON i.id=o.issue_id WHERE i.repository_id=r.id AND o.created_at>=?)
              AS generated,
            (SELECT COUNT(*) FROM review_issue_occurrences o JOIN review_issues i
              ON i.id=o.issue_id JOIN gitlab_publications p ON p.job_id=o.job_id
              AND p.attempt_number=o.attempt_number AND p.comment_index=o.comment_index
              WHERE i.repository_id=r.id AND o.created_at>=? AND p.status='sent')
              AS published
            FROM repositories r WHERE (? IS NULL OR r.id=?) ORDER BY r.name,r.id""",
            (since, since, since, since, *args))]
    trend = [{"day": (start_day + timedelta(days=offset)).isoformat(),
              "new": new_by_day.get((start_day + timedelta(days=offset)).isoformat(), 0),
              "fixed": fixed_by_day.get((start_day + timedelta(days=offset)).isoformat(), 0)}
             for offset in range(days)]
    return {"days": days, "repository_id": repository_id,
            "summary": {"reviews": reviews["finished"], "failed_reviews": reviews["failed"] or 0,
                        "generated": generated["findings"],
                        "published": generated["published"] or 0,
                        "new_issues": issues["created"],
                        "new_still_open": issues["still_open"] or 0,
                        "fixed": fixed, "ignored": ignored, "open_now": open_now,
                        "feedback_marked": feedback["marked"],
                        "false_positive": feedback["false_positive"] or 0},
            "trend": trend, "categories": categories, "projects": projects}


def register_effectiveness(app: FastAPI, store: Store, admin: Any) -> None:
    """管理台只查询 SQLite 中的已保存事实，不在统计请求中调用模型。"""

    @app.get("/api/review-effectiveness", dependencies=[admin])
    def effectiveness(repository_id: int | None = Query(None, gt=0),
                      days: int = Query(30)) -> dict[str, Any]:
        """按项目和最近天数统计，样本量判断留给界面明确展示。"""

        if days not in {7, 30, 90}:
            raise HTTPException(422, "统计时间仅支持 7、30 或 90 天")
        return effectiveness_snapshot(store, repository_id, days)
