"""按同一评审时间窗口衡量发现、发布与人工处理，避免混用分母。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import FastAPI, HTTPException, Query

from ocr_manager.overview_scopes import OPEN_ISSUE_SCOPE
from ocr_manager.review_quality import (
    DispositionFilter,
    FeedbackFilter,
    quality_findings,
    quality_snapshot,
)

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
        # 全部业务指标共用一次读取快照，避免处置并发时总数与分布不一致。
        db.execute("BEGIN")
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
            JOIN review_issue_states i ON i.id=o.issue_id
            LEFT JOIN gitlab_publications p ON p.job_id=o.job_id
              AND p.attempt_number=o.attempt_number AND p.comment_index=o.comment_index
              AND o.recovery_id IS NULL
            WHERE (? IS NULL OR i.repository_id=?) AND o.created_at>=?""",
            (*args, since)).fetchone()
        issues = db.execute(f"""SELECT COUNT(*) AS created,
            SUM(CASE WHEN status='open' THEN 1 ELSE 0 END) AS still_open
            FROM review_issue_states WHERE {scope} AND first_seen_at>=?""",
            (*args, since)).fetchone()
        fixed = db.execute(f"""SELECT COUNT(*) FROM review_issue_states WHERE {scope}
            AND status='fixed' AND closed_at>=?""", (*args, since)).fetchone()[0]
        ignored = db.execute(f"""SELECT COUNT(*) FROM review_issue_states WHERE {scope}
            AND status='ignored' AND closed_at>=?""", (*args, since)).fetchone()[0]
        severity_counts = dict.fromkeys(("critical", "high", "medium", "low", "unclassified"), 0)
        for row in db.execute(f"""SELECT CASE WHEN i.severity IN
            ('critical','high','medium','low') THEN i.severity ELSE 'unclassified' END AS level,
            COUNT(*) AS count FROM review_issue_states i WHERE {OPEN_ISSUE_SCOPE}
            AND (? IS NULL OR i.repository_id=?) GROUP BY level""", args):
            severity_counts[row["level"]] = row["count"]
        open_now = sum(severity_counts.values())
        quality = quality_snapshot(db, repository_id, days)
        feedback = quality["summary"]
        status_counts = dict.fromkeys(("open", "fixed", "ignored", "false_positive", "merged"), 0)
        for row in db.execute(f"""SELECT status,COUNT(*) AS count FROM review_issue_states
            WHERE {scope} GROUP BY status""", args):
            status_counts[row["status"]] = row["count"]
        categories = [dict(row) for row in db.execute("""SELECT
            COALESCE(NULLIF(o.category,''),'未分类') AS category,
            COUNT(*) AS generated, COUNT(DISTINCT o.issue_id) AS issues,
            COUNT(DISTINCT CASE WHEN i.status='open' THEN i.id END) AS open_issues
            FROM review_issue_occurrences o JOIN review_issue_states i ON i.id=o.issue_id
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
        # 先分组再连接，不为每个项目重复扫描问题和任务。
        projects = [dict(row) for row in db.execute("""WITH issue_counts AS (
            SELECT repository_id,
            SUM(status='open') AS open_issues,
            SUM(status='open' AND severity='critical') AS critical_issues,
            SUM(status='open' AND severity='high') AS high_issues,
            SUM(first_seen_at>=?) AS new_issues,
            SUM(CASE WHEN status='fixed' AND closed_at>=? THEN 1 ELSE 0 END) AS fixed_issues
            FROM review_issue_states WHERE (? IS NULL OR repository_id=?) GROUP BY repository_id
            ), review_counts AS (
            SELECT repository_id,COUNT(*) AS reviews FROM review_jobs
            WHERE finished_at>=? AND status IN ('complete','partial','failed','skipped')
            AND (? IS NULL OR repository_id=?) GROUP BY repository_id
            ), occurrence_counts AS (
            SELECT i.repository_id,COUNT(*) AS generated,
            SUM(CASE WHEN p.status='sent' THEN 1 ELSE 0 END) AS published
            FROM review_issue_occurrences o JOIN review_issue_states i ON i.id=o.issue_id
            LEFT JOIN gitlab_publications p ON p.job_id=o.job_id
            AND p.attempt_number=o.attempt_number AND p.comment_index=o.comment_index
            AND o.recovery_id IS NULL WHERE o.created_at>=?
            AND (? IS NULL OR i.repository_id=?) GROUP BY i.repository_id
            ) SELECT r.id,r.name,COALESCE(i.open_issues,0) AS open_issues,
            COALESCE(i.critical_issues,0) AS critical_issues,
            COALESCE(i.high_issues,0) AS high_issues,
            COALESCE(i.new_issues,0) AS new_issues,
            COALESCE(i.fixed_issues,0) AS fixed_issues,
            COALESCE(j.reviews,0) AS reviews,COALESCE(o.generated,0) AS generated,
            COALESCE(o.published,0) AS published
            FROM repositories r LEFT JOIN issue_counts i ON i.repository_id=r.id
            LEFT JOIN review_counts j ON j.repository_id=r.id
            LEFT JOIN occurrence_counts o ON o.repository_id=r.id
            WHERE (? IS NULL OR r.id=?) ORDER BY open_issues DESC,r.name,r.id""",
            (since, since, *args, since, *args, since, *args, *args))]
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
                        "feedback_marked": feedback["helpful"] + feedback["false_positive"],
                        "false_positive": feedback["false_positive"] or 0},
            "current_issues": {"open_count": open_now, "severity_counts": severity_counts},
            "trend": trend, "categories": categories, "projects": projects,
            "quality": quality, "current_status_counts": status_counts}


def register_effectiveness(app: FastAPI, store: Store, admin: Any) -> None:
    """管理台只查询 SQLite 中的已保存事实，不在统计请求中调用模型。"""

    @app.get("/api/review-effectiveness", dependencies=[admin])
    def effectiveness(repository_id: int | None = Query(None, gt=0),
                      days: int = Query(30)) -> dict[str, Any]:
        """按项目和最近天数统计，样本量判断留给界面明确展示。"""

        if days not in {7, 30, 90}:
            raise HTTPException(422, "统计时间仅支持 7、30 或 90 天")
        return effectiveness_snapshot(store, repository_id, days)

    @app.get("/api/review-effectiveness/findings", dependencies=[admin])
    def findings(repository_id: int | None = Query(None, gt=0), days: int = Query(30),
                 feedback: Annotated[FeedbackFilter, Query()] = "all",
                 category: str | None = Query(None, max_length=200),
                 page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=50),
                 since: str | None = Query(None),
                 until: str | None = Query(None),
                 severity: str | None = Query(
                     None, pattern="^(critical|high|medium|low|unclassified)$"),
                 status: Annotated[DispositionFilter, Query()] = "all",
                 ) -> dict[str, Any]:
        """只读样本沿用聚合集合、权限与窗口；显式窗口避免午夜翻页偷偷改变范围。"""

        if days not in {7, 30, 90}:
            raise HTTPException(422, "统计时间仅支持 7、30 或 90 天")
        if (since is None) != (until is None):
            raise HTTPException(422, "起止时间必须同时提供")
        if since is not None and until is not None:
            try:
                start, end = (datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
                              for value in (since, until))
            except ValueError as error:
                raise HTTPException(422, "统计窗口格式无效") from error
            if (start.strftime("%Y-%m-%d %H:%M:%S") != since
                    or end.strftime("%Y-%m-%d %H:%M:%S") != until):
                raise HTTPException(422, "统计窗口格式无效")
            if not timedelta(0) < end - start <= timedelta(days=90):
                raise HTTPException(422, "统计窗口须大于零且不超过 90 天")
        with store.connection() as db:
            db.execute("BEGIN")
            return quality_findings(db, repository_id, days, feedback, category,
                                    page, page_size, since, until, severity, status)
