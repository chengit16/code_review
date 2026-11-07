"""绑定并测试限定项目会话的聊天采集；不默认绑定、不读取其他会话或执行模型。"""

from __future__ import annotations

import argparse
import sqlite3
from contextlib import closing
from pathlib import Path

from ocr_manager.chat_capture_adapter import read_user_messages
from ocr_manager.chat_capture_store import bind_source, ingest_messages
from ocr_manager.config import load_settings
from ocr_manager.storage import SCHEMA_VERSION, Store


def main() -> None:
    """显式绑定当前会话后可执行一次读取；守护式实时采集由 monitor 周期调用。"""

    parser = argparse.ArgumentParser(description="绑定并核验当前项目会话的聊天问题采集")
    parser.add_argument("--bind-thread", required=True)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--since-ms", type=int, required=True)
    parser.add_argument("--scan-once", action="store_true")
    args = parser.parse_args()
    settings = load_settings()
    database = (settings.data_dir / "app.db").resolve(strict=True)
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as db:
        if db.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
            raise ValueError("请先备份并迁移实例数据库，再显式绑定会话")
    store = Store(database)
    with store.connection() as db:
        grant = db.execute(
            "SELECT * FROM chat_source_bindings WHERE thread_id=?", (args.bind_thread,)
        ).fetchone()
    if grant is not None:
        if not grant["enabled"]:
            raise ValueError("会话授权已暂停；需先在管理员页面显式恢复")
        if (
            grant["project_root"] != str(args.project_root.resolve())
            or grant["since_ms"] != args.since_ms
        ):
            raise ValueError("已有绑定范围不一致，不允许借重复绑定扩大读取范围")
    expected_version = grant["version"] if grant is not None else 1
    # 接入验证发生在写授权之前；不存在或不匹配会话不能留下看似已授权的绑定。
    messages = read_user_messages(args.bind_thread, str(args.project_root.resolve()), args.since_ms)
    binding = bind_source(store, args.bind_thread, args.project_root, args.since_ms)
    result: dict[str, object] = {"binding_id": binding, "thread_bound": True}
    if args.scan_once:
        inserted = ingest_messages(store, binding, expected_version, messages)
        result["scan"] = {
            "bindings": 1,
            "scanned": len(messages),
            "inserted": inserted,
            "error_bindings": "",
        }
    print(result)


if __name__ == "__main__":
    main()
