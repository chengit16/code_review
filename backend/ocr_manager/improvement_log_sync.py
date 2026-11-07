"""按来源编号和追加游标同步台账到 SQLite；不覆盖页面修改、不重放外部业务任务。"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, Field

from ocr_manager.improvement_contracts import ImprovementContent
from ocr_manager.improvement_log_parser import LogEntry, entry_content, read_log
from ocr_manager.improvements import COLUMNS, FIELDS, _record, _revision

if TYPE_CHECKING:
    from ocr_manager.storage import Store

_ACTOR = "system:project-log-sync"


class LogSyncResult(BaseModel):
    """本次真正提交的数量；冲突来源不写入，不把跳过或失败当成同步成功。"""

    created: int = 0
    updated: int = 0
    unchanged: int = 0
    conflicts: list[str] = Field(default_factory=list)


def _apply_source(db: sqlite3.Connection, source_id: str,
                  entries: list[LogEntry]) -> tuple[int, int]:
    old = db.execute("SELECT * FROM improvement_log_imports WHERE source_id=?",
                     (source_id,)).fetchone()
    digests = [entry.digest for entry in entries]
    previous = None
    record_id: int | None = None
    applied = 0
    if old:
        known = json.loads(old["entry_digests_json"])
        if not isinstance(known, list) or digests[:len(known)] != known:
            raise ValueError("已同步历史被修改或删除")
        applied = len(known)
        if len(digests) == applied:
            return 0, 0
        record_id = int(old["improvement_id"])
        current = _record(db, record_id)
        if current.version != old["applied_version"] or current.archived_at is not None:
            raise ValueError("页面已修改或归档，须人工核对来源")
        # 以数据库当前完整内容为基线，不能靠最后一段不完整文字重建旧摘要。
        previous = ImprovementContent.model_validate({
            name: getattr(current, name) for name in FIELDS})
    created = updated = 0
    version = int(old["applied_version"]) if old else 0
    for index, entry in enumerate(entries[applied:], start=applied + 1):
        content = entry_content(entry, previous)
        values = content.model_dump()
        version += 1
        if record_id is None:
            key = str(uuid5(NAMESPACE_URL, f"open-code-review:project-log:{source_id}"))
            cursor = db.execute(f"""INSERT INTO project_improvements(client_key,{COLUMNS})
                VALUES({','.join('?' for _ in range(len(FIELDS) + 1))})""",
                (key, *(values[name] for name in FIELDS)))
            assert cursor.lastrowid is not None
            record_id = cursor.lastrowid
            created += 1
        else:
            assignments = ",".join(f'"{name}"=?' for name in FIELDS)
            db.execute(f"""UPDATE project_improvements SET {assignments},version=?,
                updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?""",
                (*(values[name] for name in FIELDS), version, record_id))
            updated += 1
        _revision(db, record_id, version, _ACTOR,
                  f"台账同步 {source_id} 第 {index} 条：{entry.title}", content)
        previous = content
    db.execute("""INSERT INTO improvement_log_imports
        (source_id,improvement_id,applied_version,entry_digests_json) VALUES(?,?,?,?)
        ON CONFLICT(source_id) DO UPDATE SET applied_version=excluded.applied_version,
        entry_digests_json=excluded.entry_digests_json,
        imported_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')""",
        (source_id, record_id, version, json.dumps(digests)))
    return created, updated


def sync_project_log(store: Store, path: Path) -> LogSyncResult:
    """先读稳定文件，再以短事务和来源保存点提交；历史变更或人工编辑仅阻止对应来源。"""

    # 1. 文件读取发生在 SQLite 写锁之外，来源没有明确状态时不升级验收结论。
    groups = read_log(path)
    result = LogSyncResult()
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        # 2. 每个来源的当前内容、历史与游标原子提交，冲突不阻止其他独立事项。
        for source_id, entries in groups.items():
            db.execute("SAVEPOINT project_log_source")
            try:
                created, updated = _apply_source(db, source_id, entries)
            except (ValueError, sqlite3.IntegrityError):
                db.execute("ROLLBACK TO project_log_source")
                result.conflicts.append(source_id)
            else:
                result.created += created
                result.updated += updated
                result.unchanged += int(created == updated == 0)
            finally:
                db.execute("RELEASE project_log_source")
        # 3. 来源从文件中删除也视为冲突，绝不级联删除页面或旧历史。
        known_ids = {str(row[0]) for row in db.execute(
            "SELECT source_id FROM improvement_log_imports")}
        result.conflicts.extend(sorted(known_ids - groups.keys()))
    return result
