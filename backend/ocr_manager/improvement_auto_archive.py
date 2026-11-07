"""保守的自动归档筛选与事务；不清除数据，不用时间替代验证或部署证据。"""

from __future__ import annotations

import sqlite3

from ocr_manager.improvement_archive_contracts import ArchiveChange
from ocr_manager.improvement_archives import ArchiveResource, change_archive_in_transaction
from ocr_manager.improvement_maintenance_contracts import MaintenanceResult


def _closed(alias: str) -> str:
    # 列名别名仅来自本模块常量；包含换行的遗留说明也必须阻止归档。
    whitespace = "' ' || char(9) || char(10) || char(13)"
    return f"""{alias}.verification_state IN ('passed','not_applicable')
        AND length(trim({alias}.validation_evidence,{whitespace}))>0
        AND {alias}.deployment_state IN ('confirmed','not_applicable')
        AND length(trim({alias}.deployment_evidence,{whitespace}))>0
        AND length(trim({alias}.solution,{whitespace}))>0
        AND length(trim({alias}.next_steps,{whitespace}))=0"""


def _queries() -> tuple[str, str]:
    aged = "archived_at IS NULL AND julianday(updated_at)<=julianday(?,?)"
    records = f"""SELECT id,version FROM project_improvements r WHERE {aged}
        AND r.status='resolved' AND {_closed('r')}"""
    themes = f"""SELECT id,version FROM improvement_themes t WHERE {aged}
        AND t.status='completed' AND length(trim(t.outcome))>0
        AND length(trim(t.next_steps,' '||char(9)||char(10)||char(13)))=0
        AND EXISTS(SELECT 1 FROM improvement_theme_phases p WHERE p.theme_id=t.id)
        AND NOT EXISTS(SELECT 1 FROM improvement_theme_phases p WHERE p.theme_id=t.id
            AND NOT(p.status='completed' AND {_closed('p')}))
        AND NOT EXISTS(SELECT 1 FROM improvement_theme_links l
            JOIN project_improvements r ON r.id=l.improvement_id
            WHERE l.theme_id=t.id AND NOT(r.status='resolved' AND {_closed('r')}))"""
    return records, themes


def candidate_counts(db: sqlite3.Connection, days: int, now: str) -> tuple[int, int]:
    """同一读取快照统计满足完整闭环条件的对象，不修改归档或时间。"""

    counts = [int(db.execute(f"SELECT count(*) FROM ({query})",
                            (now, f"-{days} days")).fetchone()[0]) for query in _queries()]
    return counts[0], counts[1]


def archive_candidates(db: sqlite3.Connection, days: int, now: str) -> MaintenanceResult:
    """调用方持有 BEGIN IMMEDIATE；筛选、复核、历史和元数据必须整体提交。"""

    result = MaintenanceResult()
    resources: tuple[ArchiveResource, ArchiveResource] = ("record", "theme")
    for resource, query in zip(resources, _queries(), strict=True):
        rows = db.execute(query + " ORDER BY id LIMIT 100", (now, f"-{days} days")).fetchall()
        for row in rows:
            change_archive_in_transaction(db, resource, int(row["id"]), ArchiveChange(
                archived=True, expected_version=int(row["version"]),
                reason=f"自动归档：已闭环、验证及部署证据齐全、无遗留，连续 {days} 天无更新"),
                "system:improvement-maintenance")
        if resource == "record":
            result.archived_records = len(rows)
        else:
            result.archived_themes = len(rows)
    return result
