"""通过本机 Codex app-server 读取已绑定会话的用户消息；不扫描缓存、不读取未绑定线程。"""

from __future__ import annotations

import json
import os
import selectors
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Any

from ocr_manager.chat_capture_store import CaptureMessage, ingest_messages
from ocr_manager.storage import Store

SCAN_TIMEOUT_SECONDS = 20.0


class ChatCaptureUnavailable(RuntimeError):
    """会话协议不可用、鉴权失败或响应无法验证；本轮不推进游标。"""


def _rpc(
    process: subprocess.Popen[bytes],
    selector: selectors.BaseSelector,
    buffer: bytearray,
    request_id: int,
    method: str,
    params: dict[str, Any],
    scan_deadline: float,
) -> dict[str, Any]:
    """发送一个有界 JSON-RPC 请求；响应超时或错误统一转为稳定错误。"""

    assert process.stdin is not None
    process.stdin.write(
        (
            json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
            + "\n"
        ).encode()
    )
    process.stdin.flush()
    deadline = min(time.monotonic() + 15, scan_deadline)
    while time.monotonic() < deadline:
        if b"\n" not in buffer:
            if not selector.select(max(0.0, deadline - time.monotonic())):
                break
            assert process.stdout is not None
            chunk = os.read(process.stdout.fileno(), 65536)
            if not chunk:
                break
            buffer.extend(chunk)
            if len(buffer) > 5 * 1024 * 1024:
                raise ChatCaptureUnavailable("会话响应超过安全上限")
            continue
        line, _, remaining = buffer.partition(b"\n")
        buffer[:] = remaining
        try:
            response = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(response, dict):
            raise ChatCaptureUnavailable("会话协议响应不是对象")
        if response.get("id") != request_id:
            continue
        if "error" in response:
            raise ChatCaptureUnavailable("会话协议返回错误")
        result = response.get("result")
        if not isinstance(result, dict):
            raise ChatCaptureUnavailable("会话响应格式无效")
        return result
    raise ChatCaptureUnavailable("会话响应超时")


def _text(item: dict[str, Any]) -> str:
    """仅提取用户文本片段；图片、文件、提及和未知载荷不转成指令。"""

    values = item.get("content")
    if not isinstance(values, list):
        return ""
    pieces: list[str] = []
    for value in values:
        if (
            isinstance(value, dict)
            and value.get("type") == "text"
            and isinstance(value.get("text"), str)
        ):
            pieces.append(value["text"])
    return "\n".join(pieces)


def read_user_messages(thread_id: str, project_root: str, since_ms: int) -> list[CaptureMessage]:
    """读取线程分页中的用户消息，并校验线程工作目录与当前项目一致。"""

    command = os.environ.get("CODEX_APP_SERVER_COMMAND") or shutil.which("codex")
    if not command:
        command = (
            "/Applications/ChatGPT.app/Contents/Resources/codex-cli/"
            "CodexCLI.app/Contents/MacOS/codex"
        )
    process = subprocess.Popen(
        [command, "app-server", "--stdio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=0,
    )
    buffer = bytearray()
    scan_deadline = time.monotonic() + SCAN_TIMEOUT_SECONDS
    selector = selectors.DefaultSelector()
    assert process.stdout is not None
    selector.register(process.stdout, selectors.EVENT_READ)
    try:
        initialized = _rpc(
            process,
            selector,
            buffer,
            1,
            "initialize",
            {"clientInfo": {"name": "open-code-review-chat-capture", "version": "0.1"}},
            scan_deadline,
        )
        if not initialized:
            raise ChatCaptureUnavailable("会话初始化失败")
        assert process.stdin is not None
        process.stdin.write(b'{"jsonrpc":"2.0","method":"initialized"}\n')
        process.stdin.flush()
        thread = _rpc(
            process,
            selector,
            buffer,
            2,
            "thread/read",
            {"threadId": thread_id, "includeTurns": False},
            scan_deadline,
        ).get("thread")
        if (
            not isinstance(thread, dict)
            or thread.get("id") != thread_id
            or thread.get("cwd") != str(Path(project_root).resolve())
        ):
            raise ChatCaptureUnavailable("会话项目范围不匹配")
        cursor: str | None = None
        seen_cursors: set[str] = set()
        result: list[CaptureMessage] = []
        # 用户消息在回合摘要中可见，无需读取工具输出、推理或正文工件；从新到旧覆盖授权范围。
        for page_number in range(100):
            if time.monotonic() > scan_deadline:
                raise ChatCaptureUnavailable("会话扫描超过单轮截止时间")
            params: dict[str, Any] = {
                "threadId": thread_id,
                "limit": 25,
                "sortDirection": "desc",
                "itemsView": "summary",
            }
            if cursor:
                params["cursor"] = cursor
            page = _rpc(
                process,
                selector,
                buffer,
                page_number + 3,
                "thread/turns/list",
                params,
                scan_deadline,
            )
            data = page.get("data")
            if not isinstance(data, list):
                raise ChatCaptureUnavailable("会话消息格式无效")
            reached_boundary = False
            for turn in data:
                if (
                    not isinstance(turn, dict)
                    or not isinstance(turn.get("items"), list)
                    or not isinstance(turn.get("id"), str)
                ):
                    raise ChatCaptureUnavailable("会话回合格式无效")
                for item in turn["items"]:
                    if not isinstance(item, dict) or item.get("type") != "userMessage":
                        continue
                    if not isinstance(item.get("id"), str) or not item["id"]:
                        raise ChatCaptureUnavailable("用户消息缺少标识")
                    started = item.get("startedAtMs")
                    if not isinstance(started, int):
                        raise ChatCaptureUnavailable("用户消息缺少可核对时间")
                    if started < since_ms:
                        reached_boundary = True
                        continue
                    result.append(
                        CaptureMessage(
                            turn_id=str(turn.get("id", "unknown")),
                            message_id=str(item.get("id", "")),
                            role="user",
                            text=_text(item),
                            source_ms=started,
                        )
                    )
            cursor = page.get("nextCursor")
            if cursor is not None and not isinstance(cursor, str):
                raise ChatCaptureUnavailable("会话分页游标格式无效")
            if reached_boundary or not isinstance(cursor, str) or not cursor:
                break
            if cursor in seen_cursors:
                raise ChatCaptureUnavailable("会话分页游标重复")
            seen_cursors.add(cursor)
        else:
            raise ChatCaptureUnavailable("授权范围超过单轮扫描上限，需拆分补偿")
        return list(reversed(result))
    finally:
        selector.close()
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        for stream in (process.stdin, process.stdout):
            if stream is not None:
                stream.close()


def sync_chat_capture(store: Store, project_root: Path) -> dict[str, int | str]:
    """逐绑定读取并幂等摄取；失败仅更新稳定错误码，保留上次成功范围。"""

    with store.connection() as db:
        bindings = [
            dict(row)
            for row in db.execute("SELECT * FROM chat_source_bindings WHERE enabled=1 ORDER BY id")
        ]
    scanned = inserted = 0
    errors: list[str] = []
    for binding in bindings:
        try:
            if binding["project_root"] != str(project_root.resolve()):
                raise ChatCaptureUnavailable("绑定不属于当前服务项目")
            messages = read_user_messages(
                binding["thread_id"], binding["project_root"], binding["since_ms"]
            )
            count = ingest_messages(store, binding["id"], binding["version"], messages)
            scanned += len(messages)
            inserted += count
        except (ChatCaptureUnavailable, OSError, ValueError, TypeError):
            errors.append(str(binding["id"]))
            with store.connection() as db:
                db.execute(
                    """UPDATE chat_source_bindings SET last_checked_at=CURRENT_TIMESTAMP,
                    last_error_code='source_unavailable' WHERE id=?""",
                    (binding["id"],),
                )
        except sqlite3.Error:
            errors.append(str(binding["id"]))
            with store.connection() as db:
                db.execute(
                    """UPDATE chat_source_bindings SET last_checked_at=CURRENT_TIMESTAMP,
                    last_error_code='storage_unavailable' WHERE id=?""",
                    (binding["id"],),
                )
    return {
        "bindings": len(bindings),
        "scanned": scanned,
        "inserted": inserted,
        "error_bindings": ",".join(errors),
    }
