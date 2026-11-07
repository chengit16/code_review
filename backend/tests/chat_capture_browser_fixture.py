"""仅为独立浏览器通道创建合成聊天事实，不调用本机 Codex 或业务数据库。"""

from __future__ import annotations

from ocr_manager.chat_capture_store import CaptureMessage, bind_source, ingest_messages
from ocr_manager.config import Settings
from ocr_manager.storage import Store


def install(store: Store, settings: Settings) -> None:
    """准备一条自动受理和一条候选，重复摄取不产生重复问题。"""

    binding = bind_source(store, "synthetic-browser-thread", settings.data_dir, 1000)
    messages = [
        CaptureMessage(
            turn_id="turn", message_id="issue", role="user", text="合成按钮报错", source_ms=2000
        ),
        CaptureMessage(
            turn_id="turn", message_id="question", role="user", text="合成方案咨询", source_ms=3000
        ),
    ]
    assert ingest_messages(store, binding, 1, messages) == 2
    assert ingest_messages(store, binding, 1, messages) == 0
    with store.connection() as db:
        db.execute(
            "UPDATE chat_source_bindings SET last_success_at=CURRENT_TIMESTAMP,last_scan_count=2"
        )
