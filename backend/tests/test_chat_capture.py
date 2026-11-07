"""合成会话与隔离数据库保护混合记录的范围、幂等、证据边界、撤权、迁移与失败补偿。"""

from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient
from ocr_manager import storage
from ocr_manager.chat_capture_adapter import ChatCaptureUnavailable, sync_chat_capture
from ocr_manager.chat_capture_contracts import ChatBindingChange, ChatEventLink
from ocr_manager.chat_capture_store import (
    CaptureMessage,
    bind_source,
    change_binding,
    inbox,
    ingest_messages,
    link_event,
)
from ocr_manager.chat_capture_text import safe_excerpt
from ocr_manager.config import Settings
from ocr_manager.improvements import get_improvement
from ocr_manager.storage import Store
from schema_fixtures import remove_chat_capture_schema


def _fixture(settings: Settings) -> tuple[Store, int]:
    store = Store(settings.data_dir / "app.db")
    store.migrate()
    return store, bind_source(store, "synthetic-thread", settings.data_dir, 1000)


def _message(
    text: str = "确认排队报错",
    identity: str = "synthetic-message",
    source_ms: int = 2000,
    role: str = "user",
) -> CaptureMessage:
    return CaptureMessage.model_validate(
        {
            "turn_id": "synthetic-turn",
            "message_id": identity,
            "role": role,
            "text": text,
            "source_ms": source_ms,
        }
    )


def test_automatic_issue_replay_and_edit_preserve_facts(settings: Settings) -> None:
    """自动受理和来源同事务；重放零重复，更正不覆盖人工结论或二次建档。"""

    store, binding = _fixture(settings)
    assert ingest_messages(store, binding, 1, [_message()]) == 1
    assert ingest_messages(store, binding, 1, [_message()]) == 0
    event = inbox(store).items[0]
    assert event.improvement_id is not None
    original = get_improvement(store, event.improvement_id)
    assert original.status == "open"
    assert original.code_state == "unchanged"
    assert original.verification_state == "not_run"
    assert original.deployment_state == "unknown"
    assert ingest_messages(store, binding, 1, [_message("更正：还是报错")]) == 1
    changed = inbox(store).items[0]
    assert changed.improvement_id == event.improvement_id
    assert get_improvement(store, event.improvement_id) == original
    with store.connection() as db:
        assert db.execute("SELECT count(*) FROM project_improvements").fetchone()[0] == 1


def test_uncertain_progress_and_assistant_are_not_dropped_or_verified(settings: Settings) -> None:
    """非明确故障保留候选；助手保证不作为事实，也不持久化助手正文。"""

    store, binding = _fixture(settings)
    ingest_messages(
        store,
        binding,
        1,
        [
            _message("帮我对比方案", "question"),
            _message("继续", "continue"),
            _message("已经部署完成 synthetic-private-content", "assistant", role="assistant"),
            _message("", "attachment"),
            _message("旧消息报错", "old", source_ms=999),
        ],
    )
    result = inbox(store)
    assert result.total == 4 and result.pending == 3
    assert not any(event.improvement_id for event in result.items)
    assert all("synthetic-private-content" not in event.excerpt for event in result.items)
    assert {event.classification for event in result.items} == {"pending", "progress"}


@pytest.mark.parametrize(
    "text,hidden",
    [
        ("报错 api_key=synthetic-sensitive-value", "synthetic-sensitive-value"),
        ('报错 {"api_key":"synthetic-sensitive-value"}', "synthetic-sensitive-value"),
        ("报错 Bearer synthetic-sensitive-value", "synthetic-sensitive-value"),
        ("报错 https://host.test/?token=synthetic-sensitive-value", "host.test"),
        ("报错 ```synthetic-sensitive-code```", "synthetic-sensitive-code"),
        ("报错 /Users/synthetic/private.json", "/Users/synthetic"),
        ("资料失败\n## My request:\n现在只是咨询", "资料失败"),
        ("<system-reminder>报错 synthetic-sensitive</system-reminder>咨询", "synthetic-sensitive"),
        ("引用\n> 报错 synthetic-sensitive\n现在咨询", "synthetic-sensitive"),
    ],
)
def test_redaction_and_quoted_instruction_boundary(text: str, hidden: str) -> None:
    """附件、引用、路径、地址和合成凭据不进入可显示摘要。"""

    assert hidden not in safe_excerpt(text)
    assert len(safe_excerpt(text)) <= 800


def test_revoke_is_commit_fence_and_binding_does_not_expand(settings: Settings) -> None:
    """在途读取后撤权仍拒绝提交；幂等绑定不重新启用、不扩大历史起点。"""

    store, binding = _fixture(settings)
    change_binding(store, binding, ChatBindingChange(enabled=False, expected_version=1))
    assert bind_source(store, "synthetic-thread", settings.data_dir, 0) == binding
    with pytest.raises(ValueError, match="授权"):
        ingest_messages(store, binding, 1, [_message()])
    state = inbox(store).bindings[0]
    assert not state.enabled and state.since_ms == 1000 and state.version == 2
    change_binding(store, binding, ChatBindingChange(enabled=True, expected_version=2))
    assert ingest_messages(store, binding, 3, [_message()]) == 1


def test_link_promote_unlink_conflict_and_audit(settings: Settings) -> None:
    """待核实建档幂等、关联可逆；版本冲突不覆盖旧关联或草稿。"""

    store, binding = _fixture(settings)
    ingest_messages(store, binding, 1, [_message("请比较方案")])
    event = inbox(store).items[0]
    promoted = link_event(
        store,
        event.id,
        ChatEventLink(expected_version=event.version, promote=True),
        "synthetic-admin",
    )
    assert promoted.improvement_id is not None
    with pytest.raises(ValueError, match="已更新"):
        link_event(
            store, event.id, ChatEventLink(expected_version=event.version), "synthetic-admin"
        )
    unlinked = link_event(
        store, event.id, ChatEventLink(expected_version=promoted.version), "admin"
    )
    assert unlinked.improvement_id is None
    again = link_event(
        store, event.id, ChatEventLink(expected_version=unlinked.version, promote=True), "admin"
    )
    assert again.improvement_id == promoted.improvement_id
    with store.connection() as db:
        assert db.execute("SELECT count(*) FROM chat_capture_links").fetchone()[0] == 3


def test_failed_source_retries_without_false_success_or_duplicate(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """中断与来源错误不丢弃原记录，下轮重读有唯一键保护；外部错误正文不持久化。"""

    store, _ = _fixture(settings)
    import ocr_manager.chat_capture_adapter as adapter

    def unavailable(*args: object) -> list[CaptureMessage]:
        raise ChatCaptureUnavailable("synthetic-private-error")

    monkeypatch.setattr(adapter, "read_user_messages", unavailable)
    assert sync_chat_capture(store, settings.data_dir)["error_bindings"] == "1"
    state = inbox(store).bindings[0]
    assert state.last_success_at is None and state.last_error_code == "source_unavailable"
    monkeypatch.setattr(adapter, "read_user_messages", lambda *_: [_message()])
    assert sync_chat_capture(store, settings.data_dir)["inserted"] == 1
    assert sync_chat_capture(store, settings.data_dir)["inserted"] == 0
    state = inbox(store).bindings[0]
    assert state.last_success_at and state.last_error_code == ""
    assert state.last_message_ms == 2000


def test_wrong_project_does_not_read_source(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """绑定目录不属于当前服务时，在调用会话读取器前拒绝。"""

    store, _ = _fixture(settings)
    import ocr_manager.chat_capture_adapter as adapter

    monkeypatch.setattr(adapter, "read_user_messages", lambda *_: pytest.fail("不能读取其他项目"))
    assert sync_chat_capture(store, settings.data_dir.parent)["error_bindings"] == "1"


def test_migration_rolls_back_and_does_not_bind(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """46→47 只建结构，失败整体回滚，重放不自动授权或摄取历史。"""

    store, _ = _fixture(settings)
    with store.connection() as db:
        remove_chat_capture_schema(db)
        db.execute("PRAGMA user_version=46")
    migration = storage.CHAT_CAPTURE_MIGRATION
    monkeypatch.setattr(storage, "CHAT_CAPTURE_MIGRATION", migration + "INVALID SQL;")
    with pytest.raises(sqlite3.OperationalError):
        store.migrate()
    with store.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 46
        assert not db.execute(
            "SELECT 1 FROM sqlite_master WHERE name='chat_capture_events'"
        ).fetchone()
    monkeypatch.setattr(storage, "CHAT_CAPTURE_MIGRATION", migration)
    store.migrate()
    store.migrate()
    assert inbox(store).bindings == [] and inbox(store).items == []


def test_api_no_anonymous_or_reader_access(client: TestClient, settings: Settings) -> None:
    """收件箱不能成为只读账号读取管理员聊天的旁路，HTTP 不提供新增范围入口。"""

    assert client.get("/api/chat-capture").status_code == 401
    headers = {"X-Admin-Token": "test-admin-token"}
    assert client.get("/api/chat-capture", headers=headers).status_code == 200
    assert client.post("/api/chat-capture/bindings", headers=headers, json={}).status_code in (
        404,
        405,
    )
    from test_auth import create_user, enable_users, login

    create_user(client, "capture-admin", "admin")
    create_user(client, "capture-reader", "reader")
    enable_users(client)
    session = login(client, "capture-reader")
    assert (
        client.get(
            "/api/chat-capture", headers={"Authorization": f"Bearer {session['token']}"}
        ).status_code
        == 403
    )


def test_ingest_failure_rolls_back_event_and_auto_record(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """正式记录版本写入失败时，来源和自动建档整体回滚，下轮可完整补偿。"""

    import ocr_manager.chat_capture_store as capture

    store, binding = _fixture(settings)
    original = capture._revision

    def unavailable(*args: object) -> None:
        raise sqlite3.OperationalError("synthetic database busy")

    monkeypatch.setattr(capture, "_revision", unavailable)
    with pytest.raises(sqlite3.OperationalError):
        ingest_messages(store, binding, 1, [_message()])
    assert inbox(store).total == 0
    assert inbox(store).bindings[0].last_success_at is None
    with store.connection() as db:
        assert db.execute("SELECT count(*) FROM project_improvements").fetchone()[0] == 0
    monkeypatch.setattr(capture, "_revision", original)
    assert ingest_messages(store, binding, 1, [_message()]) == 1


def test_binding_cli_rejects_missing_or_unmigrated_database_before_read(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """错误实例路径不创建空库，旧版本不读取会话；迁移与授权必须显式分开。"""

    import sys

    import ocr_manager.chat_capture as cli

    monkeypatch.setattr(cli, "load_settings", lambda: settings)
    monkeypatch.setattr(cli, "read_user_messages", lambda *_: pytest.fail("校验库前不能读会话"))
    monkeypatch.setattr(sys, "argv", ["chat_capture", "--bind-thread", "thread", "--since-ms", "1"])
    database = settings.data_dir / "app.db"
    database.unlink(missing_ok=True)
    with pytest.raises(FileNotFoundError):
        cli.main()
    assert not database.exists()
    store = Store(database)
    store.migrate()
    with store.connection() as db:
        db.execute("PRAGMA user_version=46")
    with pytest.raises(ValueError, match="迁移"):
        cli.main()


def test_binding_cli_does_not_read_paused_or_widened_source(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """重复 CLI 必须先核对已授权范围和暂停状态，不能先读取历史再由写入过滤补救。"""

    import sys

    import ocr_manager.chat_capture as cli

    store, binding = _fixture(settings)
    monkeypatch.setattr(cli, "load_settings", lambda: settings)
    monkeypatch.setattr(cli, "read_user_messages", lambda *_: pytest.fail("不能越过授权读取"))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "chat_capture",
            "--bind-thread",
            "synthetic-thread",
            "--since-ms",
            "0",
            "--project-root",
            str(settings.data_dir),
            "--scan-once",
        ],
    )
    with pytest.raises(ValueError, match="范围"):
        cli.main()
    change_binding(store, binding, ChatBindingChange(expected_version=1, enabled=False))
    with pytest.raises(ValueError, match="暂停"):
        cli.main()
