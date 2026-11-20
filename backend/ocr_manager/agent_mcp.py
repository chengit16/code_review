"""受控的 Streamable HTTP MCP 规范检索客户端。"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import socket
import time
from typing import Any, cast
from urllib.parse import urlsplit

import httpx

from ocr_manager.cancellation import check_cancellation

PROTOCOL = "2025-06-18"
SUPPORTED = {"2025-03-26", PROTOCOL, "2025-11-25"}
MAX_BYTES = 64 * 1024


def validate_endpoint(endpoint: str) -> str:
    """拒绝 URL 凭据、查询串和非 HTTPS 传输；连接前另行校验地址。"""

    parsed = urlsplit(endpoint)
    if (parsed.scheme != "https" or parsed.port not in (None, 443)
            or parsed.hostname is None or not re.fullmatch(r"[a-z0-9.-]+", parsed.hostname)
            or parsed.username is not None or parsed.password is not None
            or "?" in endpoint or "#" in endpoint or "\\" in endpoint
            or any(ord(char) <= 32 or ord(char) == 127 for char in endpoint)):
        raise ValueError("请填写公开 HTTPS MCP 地址（443 端口，无凭据或查询串）")
    return parsed.hostname


def _public_address(host: str) -> str:
    addresses = {str(item[4][0]) for item in socket.getaddrinfo(
        host, 443, family=socket.AF_INET, type=socket.SOCK_STREAM,
    )}
    allowed = [address for address in sorted(addresses)
               if ipaddress.IPv4Address(address).is_global
               and not ipaddress.IPv4Address(address).is_multicast]
    if not allowed or len(allowed) != len(addresses):
        raise ValueError("MCP 地址未解析到公共 IPv4")
    return allowed[0]


class McpClient:
    """每次检索使用短会话，固定连接 IP，保留原主机名用于 TLS 与 Host 校验。"""

    def __init__(self, client: httpx.Client, endpoint: str, token: str, timeout: float) -> None:
        self.client = client
        self.deadline = time.monotonic() + timeout
        self.host = validate_endpoint(endpoint)
        self.endpoint = httpx.URL(endpoint).copy_with(host=_public_address(self.host))
        self.headers = {"Host": self.host, "Accept": "application/json, text/event-stream",
                        "Accept-Encoding": "identity"}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"
        self.sequence = 0

    def _parse(self, response: httpx.Response, request_id: int) -> dict[str, Any]:
        buffer = bytearray()
        streamed = response.headers.get("content-type", "").startswith("text/event-stream")
        received = 0
        for chunk in response.iter_raw():
            check_cancellation()
            received += len(chunk)
            if received > MAX_BYTES or time.monotonic() > self.deadline:
                raise ValueError("MCP 响应超出限制")
            buffer.extend(chunk)
            if streamed:
                buffer = bytearray(buffer.replace(b"\r\n", b"\n"))
                while b"\n\n" in buffer:
                    event, remainder = buffer.split(b"\n\n", 1)
                    buffer = bytearray(remainder)
                    data = b"\n".join(line[5:].lstrip() for line in event.splitlines()
                                      if line.startswith(b"data:"))
                    if data:
                        message = json.loads(data)
                        if isinstance(message, dict) and message.get("id") == request_id:
                            return cast(dict[str, Any], message)
        message = json.loads(buffer) if not streamed else None
        if not isinstance(message, dict) or message.get("id") != request_id:
            raise ValueError("MCP 响应缺少请求标识")
        return cast(dict[str, Any], message)

    def _send(self, http_method: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        check_cancellation()
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("MCP 调用超时")
        with self.client.stream(http_method, self.endpoint, headers=self.headers,
                                json=body, timeout=remaining, follow_redirects=False,
                                extensions={"sni_hostname": self.host}) as response:
            response.raise_for_status()
            if body is None or "id" not in body:
                return {}
            if body["method"] == "initialize":
                session = response.headers.get("mcp-session-id")
                if session:
                    if not re.fullmatch(r"[!-~]{1,256}", session):
                        raise ValueError("MCP 会话标识无效")
                    self.headers["MCP-Session-Id"] = session
            message = self._parse(response, body["id"])
        if (message.get("jsonrpc") != "2.0" or "error" in message
                or not isinstance(message.get("result"), dict)):
            raise ValueError("MCP 服务未返回有效结果")
        return cast(dict[str, Any], message["result"])

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """发送白名单会话操作，调用方持有检索工具授权。"""

        self.sequence += 1
        return self._send("POST", {"jsonrpc": "2.0", "id": self.sequence,
                                   "method": method, "params": params})

    def initialize(self) -> None:
        """协商工具能力并完成握手。"""

        result = self.request("initialize", {
            "protocolVersion": PROTOCOL, "capabilities": {},
            "clientInfo": {"name": "open-code-review", "version": "1"},
        })
        version = result.get("protocolVersion")
        capabilities = result.get("capabilities")
        if (not isinstance(version, str) or version not in SUPPORTED
                or not isinstance(capabilities, dict) or "tools" not in capabilities):
            raise ValueError("MCP 服务未提供兼容的工具能力")
        self.headers["MCP-Protocol-Version"] = version
        self._send("POST", {"jsonrpc": "2.0", "method": "notifications/initialized"})

    def close(self) -> None:
        """服务端颁发会话时尽力释放；关闭失败不改写已返回的证据。"""

        if "MCP-Session-Id" in self.headers:
            try:
                self._send("DELETE")
            except (httpx.HTTPError, TimeoutError, ValueError):
                pass

    def tools(self) -> dict[str, dict[str, Any]]:
        """发现显式标注只读、可用单个字符串参数调用的工具。"""

        tools: dict[str, dict[str, Any]] = {}
        params: dict[str, Any] = {}
        for _ in range(5):
            response = self.request("tools/list", params)
            entries = response.get("tools")
            if not isinstance(entries, list) or len(entries) > 100:
                raise ValueError("MCP 工具目录无效")
            for item in entries:
                if isinstance(item, dict):
                    self._add_readonly_tool(tools, item)
            cursor = response.get("nextCursor")
            if cursor is None:
                return tools
            if not isinstance(cursor, str) or len(cursor) > 500 or cursor == params.get("cursor"):
                raise ValueError("MCP 工具分页无效")
            params = {"cursor": cursor}
        raise ValueError("MCP 工具分页超限")

    def _add_readonly_tool(self, tools: dict[str, dict[str, Any]], item: dict[str, Any]) -> None:
        name, annotations, schema = (
            item.get("name"), item.get("annotations"), item.get("inputSchema"),
        )
        if (not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", name)
                or not isinstance(annotations, dict) or annotations.get("readOnlyHint") is not True
                or annotations.get("destructiveHint") is True or not isinstance(schema, dict)
                or schema.get("type") != "object"):
            return
        properties, required = schema.get("properties"), schema.get("required", [])
        if not isinstance(properties, dict) or not isinstance(required, list) or len(required) > 1:
            return
        arguments = sorted(key for key, val in properties.items()
                           if re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", key)
                           and isinstance(val, dict) and val.get("type") == "string"
                           and (not required or key == required[0]))
        if arguments:
            if name in tools:
                raise ValueError("MCP 工具名称重复")
            description = str(item.get("description", ""))
            token = self.headers.get("Authorization", "").removeprefix("Bearer ")
            if token:
                if token in name or any(token in argument for argument in arguments):
                    return
                description = description.replace(token, "[凭据已隐藏]")
            signature = hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest()
            tools[name] = {"arguments": arguments, "description": description[:240],
                           "signature": signature}
