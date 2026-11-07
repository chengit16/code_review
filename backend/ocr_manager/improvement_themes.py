"""管理改进主题、阶段、问题关联与历史；不替用户判定优化成效。"""

from __future__ import annotations

import json
import sqlite3
from typing import TYPE_CHECKING

from ocr_manager.improvement_archive_contracts import ArchiveFilter
from ocr_manager.improvement_theme_contracts import (
    ImprovementThemeContent,
    ImprovementThemeCreate,
    ImprovementThemeHistory,
    ImprovementThemePage,
    ImprovementThemeRecord,
    ImprovementThemeRevision,
    ImprovementThemeStatus,
    ImprovementThemeUpdate,
)

if TYPE_CHECKING:
    from ocr_manager.storage import Store

FIELDS = tuple(name for name in ImprovementThemeContent.model_fields if name != "phases")
COLUMNS = ",".join(f'"{name}"' for name in FIELDS)
PUBLIC_COLUMNS = ("id,version,created_at,updated_at,archived_at,archived_by,archive_reason,"
                  f"{COLUMNS}")


def _phases(db: sqlite3.Connection, theme_id: int) -> list[dict[str, object]]:
    return [dict(row) for row in db.execute("""SELECT title,goal,status,solution,code_state,
        verification_state,validation_evidence,deployment_state,deployment_evidence,next_steps
        FROM improvement_theme_phases WHERE theme_id=? ORDER BY ordinal""", (theme_id,))]


def _links(db: sqlite3.Connection, theme_id: int) -> list[int]:
    return [int(row[0]) for row in db.execute("""SELECT improvement_id FROM improvement_theme_links
        WHERE theme_id=? ORDER BY improvement_id""", (theme_id,))]


def _record(db: sqlite3.Connection, theme_id: int) -> ImprovementThemeRecord:
    row = db.execute(f"SELECT {PUBLIC_COLUMNS} FROM improvement_themes WHERE id=?",
                     (theme_id,)).fetchone()
    if row is None:
        raise LookupError("优化主题不存在")
    return ImprovementThemeRecord.model_validate({**dict(row), "phases": _phases(db, theme_id),
                                                  "improvement_ids": _links(db, theme_id)})


def _snapshot(content: ImprovementThemeContent) -> str:
    return content.model_dump_json()


def _revision(db: sqlite3.Connection, theme_id: int, version: int, actor: str, note: str,
              content: ImprovementThemeContent, improvement_ids: list[int]) -> None:
    db.execute("""INSERT INTO improvement_theme_revisions
        (theme_id,version,actor,note,snapshot_json,improvement_ids_json,action)
        VALUES(?,?,?,?,?,?,?)""",
        (theme_id, version, actor, note, _snapshot(content),
         json.dumps(improvement_ids, separators=(",", ":")),
         "create" if version == 1 else "update"))


def _validate_links(db: sqlite3.Connection, improvement_ids: list[int]) -> None:
    if len(set(improvement_ids)) != len(improvement_ids):
        raise ValueError("同一问题不能在主题关联列表中重复")
    if any(record_id <= 0 for record_id in improvement_ids):
        raise ValueError("问题编号无效")
    if not improvement_ids:
        return
    placeholders = ",".join("?" for _ in improvement_ids)
    count = db.execute(f"SELECT COUNT(*) FROM project_improvements WHERE id IN ({placeholders})",
                       improvement_ids).fetchone()[0]
    if count != len(improvement_ids):
        raise ValueError("关联的问题记录不存在")


def _replace_children(db: sqlite3.Connection, theme_id: int,
                      content: ImprovementThemeContent, improvement_ids: list[int]) -> None:
    db.execute("DELETE FROM improvement_theme_phases WHERE theme_id=?", (theme_id,))
    db.executemany("""INSERT INTO improvement_theme_phases
        (theme_id,ordinal,title,goal,status,solution,code_state,verification_state,
         validation_evidence,deployment_state,deployment_evidence,next_steps)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        [(theme_id, index, phase.title, phase.goal, phase.status, phase.solution,
          phase.code_state, phase.verification_state, phase.validation_evidence,
          phase.deployment_state, phase.deployment_evidence, phase.next_steps)
         for index, phase in enumerate(content.phases)])
    db.execute("DELETE FROM improvement_theme_links WHERE theme_id=?", (theme_id,))
    db.executemany("INSERT INTO improvement_theme_links(theme_id,improvement_id) VALUES(?,?)",
                   [(theme_id, record_id) for record_id in improvement_ids])


def create_theme(store: Store, payload: ImprovementThemeCreate,
                 actor: str) -> ImprovementThemeRecord:
    """主题、阶段、问题关联和首个历史在同一事务提交；创建重试按键去重。"""

    content = ImprovementThemeContent.model_validate(payload.model_dump(exclude={
        "client_key", "improvement_ids"}))
    with store.connection() as db:
        # 1. 抢占短写事务后按创建键核对初始快照，旧请求不能覆盖后续阶段。
        db.execute("BEGIN IMMEDIATE")
        existing = db.execute("SELECT id FROM improvement_themes WHERE client_key=?",
                              (str(payload.client_key),)).fetchone()
        if existing:
            initial = db.execute("""SELECT snapshot_json,improvement_ids_json
                FROM improvement_theme_revisions WHERE theme_id=? AND version=1""",
                (existing["id"],)).fetchone()
            if initial is None or ImprovementThemeContent.model_validate_json(
                initial["snapshot_json"]
            ) != content:
                raise ValueError("创建标识已用于不同主题，请核对已有主题后重试")
            if sorted(json.loads(initial["improvement_ids_json"])) != sorted(
                payload.improvement_ids
            ):
                raise ValueError("创建标识已用于不同的问题关联，请核对已有主题后重试")
            return _record(db, existing["id"])
        # 2. 仅接受已存在的问题编号，不从文字或阶段名称推断关联。
        _validate_links(db, payload.improvement_ids)
        values = content.model_dump(exclude={"phases"})
        cursor = db.execute(f"""INSERT INTO improvement_themes(client_key,{COLUMNS})
            VALUES({','.join('?' for _ in range(len(FIELDS) + 1))})""",
            (str(payload.client_key), *(values[name] for name in FIELDS)))
        assert cursor.lastrowid is not None
        theme_id = cursor.lastrowid
        # 3. 阶段、关系和历史与主题同事务写入，任一步失败均回滚。
        _replace_children(db, theme_id, content, payload.improvement_ids)
        _revision(db, theme_id, 1, actor, "建立优化主题", content, payload.improvement_ids)
        return _record(db, theme_id)


def update_theme(store: Store, theme_id: int, payload: ImprovementThemeUpdate,
                 actor: str) -> ImprovementThemeRecord:
    """更新主题、阶段和链接时用短事务保护版本；整组失败则完整回滚。"""

    content = ImprovementThemeContent.model_validate(payload.model_dump(exclude={
        "expected_version", "progress_note", "improvement_ids"}))
    with store.connection() as db:
        # 1. 写锁覆盖版本核对，跨连接并发编辑只能有一个请求成功。
        db.execute("BEGIN IMMEDIATE")
        previous = _record(db, theme_id)
        if previous.archived_at is not None:
            raise ValueError("已归档内容不可编辑，请先恢复后再追加进展")
        if previous.version != payload.expected_version:
            raise ValueError("优化主题已更新；草稿未保存，请读取最新版本后核对")
        # 2. 先核验完整关联，再替换当前主题和有序阶段。
        _validate_links(db, payload.improvement_ids)
        values = content.model_dump(exclude={"phases"})
        assignments = ",".join(f'"{name}"=?' for name in FIELDS)
        db.execute(f"""UPDATE improvement_themes SET {assignments},version=version+1,
            updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?""",
            (*(values[name] for name in FIELDS), theme_id))
        _replace_children(db, theme_id, content, payload.improvement_ids)
        # 3. 追加当时的完整快照，不修改旧历史或关联问题本身的状态。
        _revision(db, theme_id, previous.version + 1, actor, payload.progress_note,
                  content, payload.improvement_ids)
        return _record(db, theme_id)


def get_theme(store: Store, theme_id: int) -> ImprovementThemeRecord:
    """返回主题当前摘要、阶段和显式关联的问题编号。"""

    with store.connection() as db:
        db.execute("BEGIN")
        return _record(db, theme_id)


def list_themes(store: Store, status: ImprovementThemeStatus | None,
                category: str | None, q: str, page: int,
                page_size: int, improvement_id: int | None = None,
                archive: ArchiveFilter = "active") -> ImprovementThemePage:
    """对筛选结果稳定分页，批量读取阶段和链接避免逐主题附加查询。"""

    keyword = q.strip().lower()
    where = """WHERE (?='all' OR (?='archived')=(archived_at IS NOT NULL))
        AND (? IS NULL OR status=?) AND (? IS NULL OR category=?)
        AND (? IS NULL OR EXISTS(SELECT 1 FROM improvement_theme_links link
          WHERE link.theme_id=improvement_themes.id AND link.improvement_id=?))
        AND (?='' OR instr(lower(title),?)>0 OR instr(lower(objective),?)>0
        OR instr(lower(scope),?)>0 OR instr(lower(rationale),?)>0 OR instr(lower(outcome),?)>0)"""
    params = (archive, archive, status, status, category, category, improvement_id, improvement_id,
              *(keyword for _ in range(6)))
    with store.connection() as db:
        db.execute("BEGIN")
        total = db.execute(f"SELECT COUNT(*) FROM improvement_themes {where}", params
                           ).fetchone()[0]
        rows = db.execute(f"""SELECT {PUBLIC_COLUMNS} FROM improvement_themes {where}
            ORDER BY id DESC LIMIT ? OFFSET ?""", (*params, page_size, (page - 1) * page_size)
                           ).fetchall()
        themes: list[ImprovementThemeRecord] = []
        ids = [int(row["id"]) for row in rows]
        if ids:
            placeholders = ",".join("?" for _ in ids)
            phases: dict[int, list[dict[str, object]]] = {theme_id: [] for theme_id in ids}
            for row in db.execute("""SELECT theme_id,title,goal,status,solution,code_state,
                verification_state,validation_evidence,deployment_state,deployment_evidence,
                next_steps FROM improvement_theme_phases WHERE theme_id IN (""" + placeholders +
                ") ORDER BY theme_id,ordinal", ids):
                phase = dict(row)
                theme_id = int(row["theme_id"])
                phase.pop("theme_id")
                phases[theme_id].append(phase)
            links: dict[int, list[int]] = {theme_id: [] for theme_id in ids}
            for row in db.execute("SELECT theme_id,improvement_id FROM improvement_theme_links "
                                  f"WHERE theme_id IN ({placeholders}) "
                                  "ORDER BY theme_id,improvement_id", ids):
                links[int(row["theme_id"])].append(int(row["improvement_id"]))
            themes = [ImprovementThemeRecord.model_validate({**dict(row),
                "phases": phases[int(row["id"])], "improvement_ids": links[int(row["id"])]})
                for row in rows]
    return ImprovementThemePage(items=themes, total=total, page=page, page_size=page_size)


def theme_history(store: Store, theme_id: int, page: int,
                  page_size: int) -> ImprovementThemeHistory:
    """分页读取主题历史快照，保留阶段顺序与当时关联编号。"""

    with store.connection() as db:
        db.execute("BEGIN")
        _record(db, theme_id)
        total = db.execute("SELECT COUNT(*) FROM improvement_theme_revisions WHERE theme_id=?",
                           (theme_id,)).fetchone()[0]
        rows = db.execute("""SELECT * FROM improvement_theme_revisions WHERE theme_id=?
            ORDER BY version DESC LIMIT ? OFFSET ?""",
            (theme_id, page_size, (page - 1) * page_size))
        items = [ImprovementThemeRevision(action=row["action"],
            archived_at=row["archived_at"], archived_by=row["archived_by"],
            archive_reason=row["archive_reason"], version=row["version"], actor=row["actor"],
            note=row["note"], created_at=row["created_at"],
            snapshot=ImprovementThemeContent.model_validate_json(row["snapshot_json"]),
            improvement_ids=json.loads(row["improvement_ids_json"])) for row in rows]
    return ImprovementThemeHistory(items=items, total=total, page=page, page_size=page_size)
