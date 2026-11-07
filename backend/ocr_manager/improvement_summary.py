"""聚合平台台账和优化历程；只读 SQLite，不加载长文本历史或推断部署事实。"""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING, get_args
from zoneinfo import ZoneInfo

from ocr_manager.improvement_contracts import (
    DeploymentState,
    ImprovementCategory,
    ImprovementKind,
    ImprovementStatus,
    VerificationState,
)
from ocr_manager.improvement_summary_contracts import (
    ImprovementActivityDay,
    ImprovementAttentionGroup,
    ImprovementAttentionItem,
    ImprovementDistribution,
    ImprovementRecordSummary,
    ImprovementSummary,
    ImprovementThemeSummary,
)
from ocr_manager.improvement_theme_contracts import PhaseStatus, ThemeStatus

if TYPE_CHECKING:
    from ocr_manager.storage import Store

_ZONE = ZoneInfo("Asia/Shanghai")
_CODE_STATES = ("unchanged", "modified", "not_applicable")
_RECORDS = "project_improvements"
_THEMES = "improvement_themes"
_PHASES = """(SELECT p.*,t.category FROM improvement_theme_phases p
    JOIN improvement_themes t ON t.id=p.theme_id)"""


def _local_day(timestamp: str) -> str:
    # 使用同一时区规则处理窗口与分桶，历史夏令时不能用固定加八小时近似。
    return datetime.fromisoformat(timestamp).astimezone(_ZONE).date().isoformat()


def _counts(
    db: sqlite3.Connection,
    source: str,
    field: str,
    keys: tuple[str, ...],
    category: ImprovementCategory | None,
) -> dict[str, int]:
    # 表、字段和枚举均由本模块固定选择，外部分类只通过参数绑定传入。
    counts = dict.fromkeys(keys, 0)
    for row in db.execute(
        f"""SELECT {field},COUNT(*) n FROM {source}
            WHERE (? IS NULL OR category=?) GROUP BY {field}""",
        (category, category),
    ):
        counts[row[field]] = int(row["n"])
    return counts


def _distribution(
    db: sqlite3.Connection,
    source: str,
    statuses: tuple[str, ...],
    category: ImprovementCategory | None,
) -> ImprovementDistribution:
    states = _counts(db, source, "status", statuses, category)
    return ImprovementDistribution(
        total=sum(states.values()),
        by_status=states,
        by_category=_counts(db, source, "category", get_args(ImprovementCategory), category),
        by_code_state=_counts(db, source, "code_state", _CODE_STATES, category),
        by_verification_state=_counts(
            db, source, "verification_state", get_args(VerificationState), category
        ),
        by_deployment_state=_counts(
            db, source, "deployment_state", get_args(DeploymentState), category
        ),
    )


def _attention(
    db: sqlite3.Connection, source: str, predicate: str, category: ImprovementCategory | None
) -> ImprovementAttentionGroup:
    where = f"WHERE (? IS NULL OR category=?) AND ({predicate})"
    params = (category, category)
    total = db.execute(f"SELECT COUNT(*) FROM {source} {where}", params).fetchone()[0]
    rows = db.execute(
        f"""SELECT id,title,status,updated_at,archived_at FROM {source} {where}
        ORDER BY updated_at,id LIMIT 10""",
        params,
    )
    return ImprovementAttentionGroup(
        total=total, items=[ImprovementAttentionItem.model_validate(dict(row)) for row in rows]
    )


def _activity(
    db: sqlite3.Connection, start: date, end: date, category: ImprovementCategory | None
) -> list[ImprovementActivityDay]:
    db.create_function("improvement_local_day", 1, _local_day, deterministic=True)
    lower = datetime.combine(start, time.min, _ZONE).astimezone(UTC).isoformat()
    upper = datetime.combine(end + timedelta(days=1), time.min, _ZONE).astimezone(UTC).isoformat()
    dates = [start + timedelta(days=index) for index in range((end - start).days + 1)]
    days = {day: ImprovementActivityDay(date=day) for day in dates}
    # 当前分类用于统一筛选；时间窗只用于活动，不改变当前存量统计或回放历史状态。
    for source, revisions, foreign_key, created_key, updated_key in (
        (
            _RECORDS,
            "project_improvement_revisions",
            "improvement_id",
            "records_created",
            "record_updates",
        ),
        (_THEMES, "improvement_theme_revisions", "theme_id", "themes_created", "theme_updates"),
    ):
        for table, timestamp, predicate, key in (
            (f"{source} e", "e.created_at", "1=1", created_key),
            (
                f"{revisions} r JOIN {source} e ON e.id=r.{foreign_key}",
                "r.created_at",
                "r.version>1",
                updated_key,
            ),
        ):
            rows = db.execute(
                f"""SELECT improvement_local_day({timestamp}) day,COUNT(*) n FROM {table}
                WHERE (? IS NULL OR e.category=?) AND {predicate}
                AND julianday({timestamp})>=julianday(?) AND julianday({timestamp})<julianday(?)
                GROUP BY day""",
                (category, category, lower, upper),
            )
            for row in rows:
                setattr(days[date.fromisoformat(row["day"])], key, int(row["n"]))
    return list(days.values())


def summarize_improvements(
    store: Store,
    start_date: date | None,
    end_date: date | None,
    category: ImprovementCategory | None,
) -> ImprovementSummary:
    """管理员调用的只读用例；默认近 30 个北京时间自然日，反向或超一年窗口拒绝。"""

    # 1. 先确定显式时间边界，默认含今天；不依赖服务器或浏览器的本地时区。
    now = datetime.now(UTC)
    end = end_date or now.astimezone(_ZONE).date()
    if end < date(1970, 1, 1) or end > now.astimezone(_ZONE).date():
        raise ValueError("活动日期须在 1970-01-01 至北京时间今天之间")
    start = start_date or end - timedelta(days=29)
    if start > end or (end - start).days >= 366:
        raise ValueError("活动日期范围须按先后顺序填写，且最多包含 366 个自然日")
    if start < date(1970, 1, 1):
        raise ValueError("活动日期须在 1970-01-01 至北京时间今天之间")
    with store.connection() as db:
        # 2. 共享同一只读快照，防止并发保存让总数、分组和待办互相矛盾。
        db.execute("BEGIN")
        records = _distribution(db, _RECORDS, get_args(ImprovementStatus), category)
        linked = db.execute(
            """SELECT COUNT(*) FROM project_improvements e
            WHERE (? IS NULL OR category=?) AND EXISTS(SELECT 1 FROM improvement_theme_links l
            WHERE l.improvement_id=e.id)""",
            (category, category),
        ).fetchone()[0]
        theme_status = _counts(db, _THEMES, "status", get_args(ThemeStatus), category)
        # 3. 分开聚合主题、阶段和活动；避免一对多关联导致总数乘倍。
        return ImprovementSummary(
            generated_at=now,
            start_date=start,
            end_date=end,
            category=category,
            archived_records=db.execute("""SELECT COUNT(*) FROM project_improvements
                WHERE archived_at IS NOT NULL AND (? IS NULL OR category=?)""",
                (category, category)).fetchone()[0],
            archived_themes=db.execute("""SELECT COUNT(*) FROM improvement_themes
                WHERE archived_at IS NOT NULL AND (? IS NULL OR category=?)""",
                (category, category)).fetchone()[0],
            records=ImprovementRecordSummary(
                **records.model_dump(),
                linked_records=linked,
                by_kind=_counts(db, _RECORDS, "kind", get_args(ImprovementKind), category),
            ),
            themes=ImprovementThemeSummary(
                total=sum(theme_status.values()),
                by_status=theme_status,
                by_category=_counts(
                    db, _THEMES, "category", get_args(ImprovementCategory), category
                ),
                phases=_distribution(db, _PHASES, get_args(PhaseStatus), category),
            ),
            activity=_activity(db, start, end, category),
            unresolved=_attention(db, _RECORDS, "status!='resolved'", category),
            verification_attention=_attention(
                db,
                _RECORDS,
                "verification_state IN ('failed','blocked') OR "
                "(code_state='modified' AND verification_state='not_run')",
                category,
            ),
            deployment_pending=_attention(
                db,
                _RECORDS,
                "verification_state='passed' AND deployment_state IN ('not_deployed','unknown')",
                category,
            ),
            unfinished_themes=_attention(db, _THEMES, "status!='completed'", category),
        )
