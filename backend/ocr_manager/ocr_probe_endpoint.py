"""本机合成模型端点，仅用于 OCR 探针；不读取凭据或业务代码，不向外发起请求。"""

from __future__ import annotations

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class SyntheticEndpoint:
    """串行探针控制故障开关；仅在本机随机端口提供有限的合成协议响应。"""

    def __init__(self, paths: tuple[str, str]) -> None:
        self.paths = paths
        self.fail = True
        self.block_beta = False
        self.beta_reached = threading.Event()
        self.release_beta = threading.Event()
        self.calls: list[dict[str, Any]] = []
        endpoint = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 2 * 1024 * 1024:
                    self.send_error(400)
                    return
                request = json.loads(self.rfile.read(length))
                status, payload = endpoint.reply(request)
                body = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    # 取消实验主动终止客户端；端点不因此打印协议正文或后台异常。
                    pass

            def log_message(self, _format: str, *args: Any) -> None:
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        """显式传给 CLI 的本机地址；不使用任何供应商默认端点。"""

        return f"http://127.0.0.1:{self.server.server_port}/v1/chat/completions"

    def start(self) -> None:
        """启动短生命周期的合成服务。"""

        self.thread.start()

    def close(self) -> None:
        """停止接收并释放本机端口。"""

        self.release_beta.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def reply(self, request: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        """仅从合成 diff 标签识别审核对象，记录元数据而非 prompt 或工具正文。"""

        messages = request.get("messages", [])
        user = "\n".join(str(item.get("content", "")) for item in messages
                         if item.get("role") == "user")
        paths = sorted(set(re.findall(r'<file path="([^"]+)"', user)))
        names = {tool["function"]["name"] for tool in request.get("tools", [])}
        status = 400 if not paths or (self.fail and self.paths[1] in paths) else 200
        self.calls.append({"paths": paths, "stage": "main" if names else "plan",
                           "status": status})
        if self.block_beta and self.paths[1] in paths:
            self.beta_reached.set()
            self.release_beta.wait(timeout=5)
        if status != 200:
            return status, {"error": {"message": "synthetic failure",
                                      "type": "invalid_request_error"}}
        message: dict[str, Any] = {"role": "assistant", "content": "Summary: synthetic review"}
        if "task_done" in names:
            has_comment = any(item.get("role") == "assistant" and any(
                call.get("function", {}).get("name") == "code_comment"
                for call in item.get("tool_calls", [])) for item in messages)
            name = "task_done" if has_comment else "code_comment"
            arguments = ({"summary": "synthetic complete"} if has_comment else {"comments": [{
                "path": paths[0], "content": "合成问题，仅验证恢复保留发现",
                "existing_code": "x=2", "category": "bug", "severity": "high"}]})
            message["tool_calls"] = [{"id": f"synthetic-{len(self.calls)}", "type": "function",
                                      "function": {"name": name,
                                                   "arguments": json.dumps(arguments)}}]
        return 200, {"id": "synthetic", "object": "chat.completion", "choices": [{
            "index": 0, "message": message,
            "finish_reason": "tool_calls" if "tool_calls" in message else "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}
