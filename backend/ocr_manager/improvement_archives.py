"""归档用例仅写 SQLite；版本、元数据和完整历史在同一短事务内提交，无级联副作用。"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, Literal, overload

from ocr_manager.improvement_archive_contracts import ArchiveChange
from ocr_manager.improvement_contracts import ImprovementRecord
from ocr_manager.improvement_theme_contracts import ImprovementThemeRecord
from ocr_manager.improvement_themes import _record as theme_record
from ocr_manager.improvements import _record as improvement_record

if TYPE_CHECKING:
    from ocr_manager.storage import Store

ArchiveResource = Literal["record", "theme"]


@overload
def change_archive(store: Store, resource: Literal["record"], object_id: int,
                   payload: ArchiveChange, actor: str) -> ImprovementRecord: ...


@overload
def change_archive(store: Store, resource: Literal["theme"], object_id: int,
                   payload: ArchiveChange, actor: str) -> ImprovementThemeRecord: ...


def change_archive(store: Store, resource: ArchiveResource, object_id: int,
                   payload: ArchiveChange, actor: str,
                   ) -> ImprovementRecord | ImprovementThemeRecord:
    """同版本仅允许一次状态转换；保留内容及关联，失败整体回滚，调用方须重新读取。"""

    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        return change_archive_in_transaction(db, resource, object_id, payload, actor)


def change_archive_in_transaction(
    db: sqlite3.Connection, resource: ArchiveResource, object_id: int,
    payload: ArchiveChange, actor: str,
) -> ImprovementRecord | ImprovementThemeRecord:
    """调用方必须持有短写事务；自动策略需在同一事务复核条件后调用，不嵌套连接。"""

    table, revisions, foreign_key = {
        "record": ("project_improvements", "project_improvement_revisions", "improvement_id"),
        "theme": ("improvement_themes", "improvement_theme_revisions", "theme_id"),
    }[resource]
    # 1. 与内容编辑共用版本和写锁，禁止旧草稿覆盖归档或恢复后的事实。
    previous = db.execute(f"SELECT * FROM {table} WHERE id=?", (object_id,)).fetchone()
    if previous is None:
        raise LookupError("问题记录或优化主题不存在")
    if previous["version"] != payload.expected_version:
        raise ValueError("版本已更新；操作未执行，请刷新详情并核对后重试")
    if (previous["archived_at"] is not None) == payload.archived:
        raise ValueError("已经处于目标归档状态；操作未重复执行，请刷新详情")
    # 2. 历史内容从当前版本复制，不能让归档命令悄悄修改处理结论或关系。
    action = "archive" if payload.archived else "restore"
    db.execute(f"""UPDATE {table} SET version=version+1,
        updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now'),
        archived_at=CASE WHEN ? THEN strftime('%Y-%m-%dT%H:%M:%fZ','now') END,
        archived_by=?,archive_reason=? WHERE id=?""",
        (payload.archived, actor if payload.archived else "",
         payload.reason if payload.archived else "", object_id))
    extra = ",improvement_ids_json" if resource == "theme" else ""
    selected_extra = ",r.improvement_ids_json" if extra else ""
    db.execute(f"""INSERT INTO {revisions}
        ({foreign_key},version,actor,note,snapshot_json,action,
         archived_at,archived_by,archive_reason{extra})
        SELECT e.id,e.version,?,?,r.snapshot_json,?,
            e.archived_at,e.archived_by,e.archive_reason{selected_extra}
        FROM {table} e JOIN {revisions} r ON r.{foreign_key}=e.id AND r.version=?
        WHERE e.id=?""", (actor, payload.reason, action, previous["version"], object_id))
    # 3. 缺少原始快照时拒绝提交，防止留下不可追溯的版本缺口。
    if db.execute("SELECT changes()").fetchone()[0] != 1:
        raise ValueError("当前版本历史缺失，归档操作已回滚，请先修复数据")
    return (theme_record(db, object_id) if resource == "theme"
            else improvement_record(db, object_id))
