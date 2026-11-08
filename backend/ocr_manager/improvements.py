"""提供平台问题台账的短事务用例；不执行 Git、模型、部署或自动读取会话。"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from ocr_manager.improvement_archive_contracts import ArchiveFilter
from ocr_manager.improvement_contracts import (
    ImprovementCategory,
    ImprovementContent,
    ImprovementCreate,
    ImprovementHistory,
    ImprovementKind,
    ImprovementPage,
    ImprovementRecord,
    ImprovementRevision,
    ImprovementStatus,
    ImprovementUpdate,
)

if TYPE_CHECKING:
    from ocr_manager.storage import Store

FIELDS = tuple(ImprovementContent.model_fields)
COLUMNS = ",".join(f'"{name}"' for name in FIELDS)
PUBLIC_COLUMNS = ("id,version,created_at,updated_at,archived_at,archived_by,archive_reason,"
                  f"{COLUMNS}")


def _record(db: sqlite3.Connection, record_id: int) -> ImprovementRecord:
    row = db.execute(f"SELECT {PUBLIC_COLUMNS} FROM project_improvements WHERE id=?",
                     (record_id,)).fetchone()
    if row is None:
        raise LookupError("问题与改进记录不存在")
    return ImprovementRecord.model_validate(dict(row))


def _revision(db: sqlite3.Connection, record_id: int, version: int,
              actor: str, note: str, content: ImprovementContent) -> None:
    db.execute("""INSERT INTO project_improvement_revisions
        (improvement_id,version,actor,note,snapshot_json,action) VALUES(?,?,?,?,?,?)""",
        (record_id, version, actor, note, content.model_dump_json(),
         "create" if version == 1 else "update"))


def create_improvement(store: Store, payload: ImprovementCreate, actor: str) -> ImprovementRecord:
    """记录与初始快照同事务保存；相同创建键仅接受与初始内容一致的重试。"""

    content = ImprovementContent.model_validate(payload.model_dump(exclude={"client_key"}))
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        existing = db.execute("SELECT id FROM project_improvements WHERE client_key=?",
                              (str(payload.client_key),)).fetchone()
        if existing:
            initial = db.execute("""SELECT snapshot_json FROM project_improvement_revisions
                WHERE improvement_id=? AND version=1""", (existing["id"],)).fetchone()
            if initial is None or ImprovementContent.model_validate_json(initial[0]) != content:
                raise ValueError("创建标识已被不同内容使用，请核对已创建记录后重新建档")
            return _record(db, existing["id"])
        values = content.model_dump()
        cursor = db.execute(f"""INSERT INTO project_improvements(client_key,{COLUMNS})
            VALUES({','.join('?' for _ in range(len(FIELDS) + 1))})""",
            (str(payload.client_key), *(values[name] for name in FIELDS)))
        assert cursor.lastrowid is not None
        record_id = cursor.lastrowid
        _revision(db, record_id, 1, actor, "建立记录", content)
        return _record(db, record_id)


def update_improvement(store: Store, record_id: int,
                       payload: ImprovementUpdate, actor: str) -> ImprovementRecord:
    """版本冲突整体拒绝；当前摘要和追加快照原子提交，旧历史保持不变。"""

    content = ImprovementContent.model_validate(
        payload.model_dump(exclude={"expected_version", "progress_note"}))
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        previous = _record(db, record_id)
        if previous.archived_at is not None:
            raise ValueError("已归档内容不可编辑，请先恢复后再追加进展")
        if previous.version != payload.expected_version:
            raise ValueError("记录已被更新；草稿未保存，请查看最新详情后重新核对")
        values = content.model_dump()
        assignments = ",".join(f'"{name}"=?' for name in FIELDS)
        db.execute(f"""UPDATE project_improvements SET {assignments},version=version+1,
            updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?""",
            (*(values[name] for name in FIELDS), record_id))
        _revision(db, record_id, previous.version + 1, actor, payload.progress_note, content)
        return _record(db, record_id)


def get_improvement(store: Store, record_id: int) -> ImprovementRecord:
    """读取持久化摘要；不存在时不返回空记录。"""

    with store.connection() as db:
        return _record(db, record_id)


def list_improvements(store: Store, status: ImprovementStatus | None,
                      kind: ImprovementKind | None, category: ImprovementCategory | None,
                      q: str, page: int, page_size: int,
                      archive: ArchiveFilter = "active") -> ImprovementPage:
    """按编号倒序稳定分页，参数化检索不把用户文字作为 SQL 通配表达式。"""

    keyword = q.strip().lower()
    facet_where = """WHERE (?='all' OR (?='archived')=(archived_at IS NOT NULL))
        AND (? IS NULL OR kind=?)
        AND (? IS NULL OR category=?) AND (?='' OR instr(lower(title),?)>0
        OR instr(lower(description),?)>0 OR instr(lower(scope),?)>0
        OR instr(lower(analysis),?)>0 OR instr(lower(solution),?)>0)"""
    facet_params = (archive, archive, kind, kind, category, category,
              *(keyword for _ in range(6)))
    # 共享基础范围；只在列表行与 total 上增加当前状态，避免分面漏带其他条件。
    where = facet_where + " AND (? IS NULL OR status=?)"
    params = (*facet_params, status, status)
    with store.connection() as db:
        db.execute("BEGIN")
        counts = {row["status"]: row["count"] for row in db.execute(
            f"SELECT status,COUNT(*) AS count FROM project_improvements {facet_where} "
            "GROUP BY status",
            facet_params)}
        counts["all"] = sum(counts.values())
        total = db.execute(f"SELECT COUNT(*) FROM project_improvements {where}", params
                           ).fetchone()[0]
        rows = db.execute(f"""SELECT {PUBLIC_COLUMNS} FROM project_improvements {where}
            ORDER BY id DESC LIMIT ? OFFSET ?""", (*params, page_size, (page - 1) * page_size))
        items = [ImprovementRecord.model_validate(dict(row)) for row in rows]
    return ImprovementPage(items=items, total=total, page=page, page_size=page_size,
                           status_counts=counts)


def improvement_history(store: Store, record_id: int,
                         page: int, page_size: int) -> ImprovementHistory:
    """历史独立分页；不以当前摘要替换过去的验证和部署结论。"""

    with store.connection() as db:
        db.execute("BEGIN")
        _record(db, record_id)
        total = db.execute("""SELECT COUNT(*) FROM project_improvement_revisions
            WHERE improvement_id=?""", (record_id,)).fetchone()[0]
        rows = db.execute("""SELECT * FROM project_improvement_revisions
            WHERE improvement_id=? ORDER BY version DESC LIMIT ? OFFSET ?""",
            (record_id, page_size, (page - 1) * page_size))
        items = [ImprovementRevision(
            action=row["action"], archived_at=row["archived_at"],
            archived_by=row["archived_by"], archive_reason=row["archive_reason"],
            version=row["version"], actor=row["actor"], note=row["note"],
            created_at=row["created_at"],
            snapshot=ImprovementContent.model_validate_json(row["snapshot_json"]),
        ) for row in rows]
    return ImprovementHistory(items=items, total=total, page=page, page_size=page_size)
