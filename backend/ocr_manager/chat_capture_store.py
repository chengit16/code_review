"""会话摄取和正式待核实记录的短事务；只写本功能及问题台账，不执行评审或升级状态。"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Literal
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, Field

from ocr_manager.chat_capture_contracts import (
    ChatBinding,
    ChatBindingChange,
    ChatEvent,
    ChatEventLink,
    ChatInbox,
)
from ocr_manager.chat_capture_text import classify_excerpt, safe_excerpt
from ocr_manager.improvement_contracts import ImprovementContent
from ocr_manager.improvements import COLUMNS, FIELDS, _revision

if TYPE_CHECKING:
    import sqlite3

    from ocr_manager.storage import Store


class CaptureMessage(BaseModel):
    """适配器只提交用户或已完成助手消息；原文只在内存中供本地脱敏，不落库。"""

    turn_id: str = Field(min_length=1, max_length=200)
    message_id: str = Field(min_length=1, max_length=200)
    role: Literal["user", "assistant"]
    text: str
    source_ms: int = Field(ge=0)


def bind_source(store: Store, thread_id: str, project_root: Path, since_ms: int) -> int:
    """CLI 核实会话元数据后显式绑定；重复绑定不扩大起始范围或重新启用已撤销授权。"""

    root = str(project_root.resolve(strict=True))
    if not thread_id or len(thread_id) > 200 or since_ms < 0:
        raise ValueError("会话或起始位置无效")
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "INSERT OR IGNORE INTO chat_source_bindings(thread_id,project_root,since_ms) "
            "VALUES(?,?,?)",
            (thread_id, root, since_ms),
        )
        row = db.execute(
            "SELECT * FROM chat_source_bindings WHERE thread_id=?", (thread_id,)
        ).fetchone()
        if row["project_root"] != root:
            raise ValueError("会话已绑定其他项目")
        return int(row["id"])


def ingest_messages(
    store: Store, binding_id: int, expected_version: int, messages: list[CaptureMessage]
) -> int:
    """脱敏事件、自动受理及来源链接同事务；授权被撤销时即使已读取也不提交。"""

    inserted = 0
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        binding = db.execute(
            "SELECT * FROM chat_source_bindings WHERE id=?", (binding_id,)
        ).fetchone()
        if binding is None or not binding["enabled"] or binding["version"] != expected_version:
            raise ValueError("采集授权已变更")
        # 1. 排除起始范围外内容；相同消息的不同脱敏版本追加，不覆盖旧关联或正式记录。
        for message in messages:
            if message.source_ms < binding["since_ms"]:
                continue
            excerpt = (
                safe_excerpt(message.text)
                if message.role == "user"
                else "助手已提交阶段答复，需结合台账证据核对；不自动认定验证或部署完成。"
            )
            classification = classify_excerpt(excerpt) if message.role == "user" else "progress"
            fingerprint = hashlib.sha256(excerpt.encode()).hexdigest()
            cursor = db.execute(
                """INSERT OR IGNORE INTO chat_capture_events
                (binding_id,turn_id,message_id,fingerprint,role,classification,excerpt,source_ms)
                VALUES(?,?,?,?,?,?,?,?)""",
                (
                    binding_id,
                    message.turn_id,
                    message.message_id,
                    fingerprint,
                    message.role,
                    classification,
                    excerpt,
                    message.source_ms,
                ),
            )
            if not cursor.rowcount:
                continue
            assert cursor.lastrowid is not None
            event_id = cursor.lastrowid
            inserted += 1
            previous = db.execute(
                """SELECT improvement_id FROM chat_capture_events
                WHERE binding_id=? AND message_id=? AND id<>? ORDER BY id DESC LIMIT 1""",
                (binding_id, message.message_id, event_id),
            ).fetchone()
            # 2. 编辑消息不二次建档；保留来源更正待核实，不自动覆盖用户已编辑的正式事实。
            if previous:
                if previous["improvement_id"]:
                    _link(
                        db, event_id, previous["improvement_id"], "system:chat-capture", "来源更正"
                    )
            elif classification == "issue":
                record_id = _promote(db, event_id)
                _link(db, event_id, record_id, "system:chat-capture", "自动受理，未核实")
        db.execute(
            """UPDATE chat_source_bindings SET last_checked_at=CURRENT_TIMESTAMP,
            last_success_at=CURRENT_TIMESTAMP,last_error_code='',last_scan_count=?,
            last_message_ms=COALESCE((SELECT max(source_ms) FROM chat_capture_events
            WHERE binding_id=?),last_message_ms) WHERE id=? AND version=?""",
            (len(messages), binding_id, binding_id, expected_version),
        )
        return inserted


def _promote(db: sqlite3.Connection, event_id: int) -> int:
    event = db.execute("SELECT * FROM chat_capture_events WHERE id=?", (event_id,)).fetchone()
    key = str(uuid5(NAMESPACE_URL, f"open-code-review:chat-event:{event_id}"))
    existing = db.execute(
        "SELECT id FROM project_improvements WHERE client_key=?", (key,)
    ).fetchone()
    if existing:
        return int(existing["id"])
    content = ImprovementContent(
        title="聊天待核实｜" + event["excerpt"][:70],
        description="用户聊天线索（自动受理，尚未核实）：\n" + event["excerpt"],
        analysis="本地规则仅识别线索；不代表故障已确认。请关联既有问题或补充实际证据。",
        category="other",
        status="open",
        verification_state="not_run",
        deployment_state="unknown",
        references=f"聊天收件箱 #{event_id}；绑定 #{event['binding_id']}；"
        f"会话消息 {event['message_id']}；未经核实不得作为验收事实。",
    )
    values = content.model_dump()
    cursor = db.execute(
        f"INSERT INTO project_improvements(client_key,{COLUMNS}) "
        f"VALUES({','.join('?' for _ in range(len(FIELDS) + 1))})",
        (key, *(values[name] for name in FIELDS)),
    )
    assert cursor.lastrowid is not None
    _revision(db, cursor.lastrowid, 1, "system:chat-capture", "聊天自动受理，待核实", content)
    return cursor.lastrowid


def _link(
    db: sqlite3.Connection, event_id: int, record_id: int | None, actor: str, reason: str
) -> None:
    db.execute(
        "UPDATE chat_capture_events SET improvement_id=?,version=version+1 WHERE id=?",
        (record_id, event_id),
    )
    db.execute(
        "INSERT INTO chat_capture_links(event_id,improvement_id,actor,reason) VALUES(?,?,?,?)",
        (event_id, record_id, actor, reason),
    )


def link_event(store: Store, event_id: int, payload: ChatEventLink, actor: str) -> ChatEvent:
    """按版本关联、解除或提升线索；关联可逆且有历史，不改目标问题的状态和摘要。"""

    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        event = db.execute("SELECT * FROM chat_capture_events WHERE id=?", (event_id,)).fetchone()
        if event is None:
            raise LookupError("聊天线索不存在")
        if event["version"] != payload.expected_version:
            raise ValueError("线索已更新，请刷新后核对；未覆盖当前关联")
        if payload.promote and payload.improvement_id is not None:
            raise ValueError("建档与关联不能同时提交")
        record_id = _promote(db, event_id) if payload.promote else payload.improvement_id
        if (
            record_id is not None
            and not db.execute(
                "SELECT 1 FROM project_improvements WHERE id=? AND archived_at IS NULL",
                (record_id,),
            ).fetchone()
        ):
            raise ValueError("目标问题不存在或已归档")
        _link(db, event_id, record_id, actor, "人工建档" if payload.promote else "人工更正关联")
        return ChatEvent.model_validate(
            dict(db.execute("SELECT * FROM chat_capture_events WHERE id=?", (event_id,)).fetchone())
        )


def change_binding(store: Store, binding_id: int, payload: ChatBindingChange) -> None:
    """暂停或恢复显式绑定；版本变化作为在途摄取的提交栅栏。"""

    with store.connection() as db:
        changed = db.execute(
            """UPDATE chat_source_bindings SET enabled=?,version=version+1
            WHERE id=? AND version=?""",
            (payload.enabled, binding_id, payload.expected_version),
        ).rowcount
        if not changed:
            raise ValueError("授权已变更，请刷新后核对")


def inbox(store: Store, page: int = 1, page_size: int = 25,
          classification: str | None = None) -> ChatInbox:
    """一致读取脱敏分页及运行事实；未运行或失败不伪装为空收件箱。"""

    with store.connection() as db:
        db.execute("BEGIN")
        bindings = [
            ChatBinding.model_validate(dict(row))
            for row in db.execute("SELECT * FROM chat_source_bindings ORDER BY id")
        ]
        where = "WHERE (? IS NULL OR classification=?)"
        args = (classification, classification)
        total = db.execute(f"SELECT count(*) FROM chat_capture_events {where}", args).fetchone()[0]
        pending = db.execute(
            "SELECT count(*) FROM chat_capture_events WHERE improvement_id IS NULL AND role='user'"
        ).fetchone()[0]
        rows = db.execute(
            f"SELECT * FROM chat_capture_events {where} ORDER BY id DESC LIMIT ? OFFSET ?",
            (*args, page_size, (page - 1) * page_size),
        ).fetchall()
    return ChatInbox(
        bindings=bindings,
        items=[ChatEvent.model_validate(dict(r)) for r in rows],
        pending=pending,
        total=total,
        page=page,
        page_size=page_size,
    )
