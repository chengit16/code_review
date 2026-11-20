"""按冻结方案装配模型上下文，保存可核对的补查证据。"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import time
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

import httpx
from cryptography.fernet import InvalidToken

from ocr_manager.agent_capabilities import (
    check_mcp,
    discovered_tools,
    get_scheme,
    get_skills,
    tool_signature,
)
from ocr_manager.agent_capability_contracts import CapabilityRun, FileLookup, McpLookup
from ocr_manager.agent_mcp import McpClient
from ocr_manager.cancellation import check_cancellation
from ocr_manager.config import Settings
from ocr_manager.range_preflight import read_git_objects
from ocr_manager.review_prototype.graph import ModelPageFailure
from ocr_manager.review_prototype.input import DiffPage
from ocr_manager.secrets import SecretBox
from ocr_manager.storage import Store

MAX_EXCERPT = 1800


def _read_file(root: Path, head: str, lookup: FileLookup, deadline: float) -> dict[str, Any]:
    entry = read_git_objects(root, ["--literal-pathspecs", "ls-tree",
                                   "--format=%(objectmode) %(objectname)", head, "--", lookup.path],
                             deadline, 256).decode("ascii").split()
    if len(entry) != 2 or entry[0] not in {"100644", "100755"}:
        raise ValueError("补查路径不是普通文件")
    raw = read_git_objects(root, ["cat-file", "blob", entry[1]], deadline, 48 * 1024)
    if b"\x00" in raw:
        raise ValueError("补查路径不是文本文件")
    lines = raw.decode().splitlines()
    excerpt = "\n".join(lines[lookup.start_line - 1:lookup.start_line - 1 + lookup.lines])
    if not excerpt:
        raise ValueError("补查范围没有文本")
    return {"path": lookup.path, "commit": head, "line": lookup.start_line,
            "excerpt": excerpt[:MAX_EXCERPT], "sha256": hashlib.sha256(raw).hexdigest()}


class CapabilityRuntime:
    """同一文件的装配可重用；一轮相同规范查询最多发送一次。"""

    def __init__(self, store: Store, settings: Settings, run: sqlite3.Row, frozen: CapabilityRun,
                 deadline: float | None) -> None:
        self.store, self.settings, self.run = store, settings, run
        self.frozen, self.deadline = frozen, deadline
        with store.connection() as db:
            scheme = get_scheme(db, frozen.scheme_id)
            if scheme.state == "disabled" or (not frozen.trial and scheme.state != "published"):
                raise ValueError("评审方案已停用")
            self.skills = get_skills(db, scheme.document)
        self.document = scheme.document
        self.root = settings.data_dir / "repositories" / str(run["repository_id"])
        self.prepared: dict[str, object] | None = None
        self.refs: set[int] = set()

    def _event(self, step: str, path: str, source: str,
               status: str, evidence: dict[str, Any] | None = None) -> int:
        with self.store.connection() as db:
            row = db.execute("""INSERT INTO agent_capability_events
                (run_id,step,path,source,status,evidence) VALUES (?,?,?,?,?,?)
                ON CONFLICT(run_id,step,path,source) DO UPDATE SET
                    status=excluded.status,evidence=excluded.evidence RETURNING id""",
                (self.run["id"], step, path, source, status,
                 json.dumps(evidence, ensure_ascii=False) if evidence else None)).fetchone()
            return int(row[0])

    def _existing(self, step: str, path: str, source: str) -> sqlite3.Row | None:
        with self.store.connection() as db:
            row: sqlite3.Row | None = db.execute("""SELECT id,status,evidence
                FROM agent_capability_events WHERE run_id=? AND step=? AND path=? AND source=?""",
                (self.run["id"], step, path, source)).fetchone()
            return row

    def _files(self, path: str) -> list[dict[str, Any]]:
        evidence = []
        for index, lookup in enumerate(self.document.files, 1):
            source = f"{lookup.path} · 第 {lookup.start_line} 行 · #{index}"
            if not fnmatchcase(path, lookup.pattern):
                self._event("read_file", path, source, "skipped")
                continue
            cached = self._existing("read_file", path, source)
            if cached:
                if cached["status"] == "complete":
                    evidence.append({"ref": cached["id"], **json.loads(cached["evidence"])})
                continue
            check_cancellation()
            try:
                deadline = min(self.deadline or float("inf"), time.monotonic() + 3)
                value = _read_file(self.root, self.run["head_sha"], lookup, deadline)
            except (OSError, ValueError, subprocess.SubprocessError):
                self._event("read_file", path, source, "failed")
                continue
            ident = self._event("read_file", path, source, "complete", value)
            evidence.append({"ref": ident, **value})
        return evidence

    def _lookup(self, lookup: McpLookup, service: sqlite3.Row) -> dict[str, Any]:
        token = (SecretBox(self.settings.master_key).decrypt(service["token_ciphertext"])
                 if service["token_ciphertext"] else "")
        duration = min(float(service["timeout_seconds"]),
                       (self.deadline or float("inf")) - time.monotonic())
        with httpx.Client(trust_env=False) as client:
            mcp = McpClient(client, service["endpoint"], token, duration)
            try:
                mcp.initialize()
                tool = mcp.tools().get(lookup.tool)
                if tool is None or tool_signature(tool) != self.frozen.mcp_signature:
                    raise ValueError("MCP 工具契约已变化")
                with self.store.connection() as db:
                    check_mcp(db, lookup, self.run["repository_id"])
                result = mcp.request("tools/call", {
                    "name": lookup.tool, "arguments": {lookup.argument: lookup.query},
                })
            finally:
                mcp.close()
        if result.get("isError"):
            raise ValueError("规范查询失败")
        data = result.get("structuredContent")
        if not isinstance(data, dict):
            data = {}
        content = result.get("content", [])
        if not isinstance(content, list):
            raise ValueError("MCP 证据格式无效")
        text = "\n".join(item["text"] for item in content if isinstance(item, dict)
                         and item.get("type") == "text" and isinstance(item.get("text"), str))
        if not text and data:
            text = json.dumps(data, ensure_ascii=False)
        if not text.strip():
            raise ValueError("MCP 未返回可核对文本")
        document = str(data.get("document_id") or data.get("uri") or lookup.tool)
        version = str(data.get("version") or "")
        if token:
            text, document, version = (
                value.replace(token, "[凭据已隐藏]") for value in (text, document, version)
            )
        return {"document": document[:240], "version": version[:100],
                "sha256": hashlib.sha256(text.encode()).hexdigest(),
                "excerpt": text[:MAX_EXCERPT]}

    def _mcp(self, path: str, lookup: McpLookup) -> dict[str, Any] | None:
        source = self.frozen.mcp or lookup.tool
        if not fnmatchcase(path, lookup.pattern):
            self._event("mcp", path, source, "skipped")
            return None
        try:
            with self.store.connection() as db:
                service = check_mcp(db, lookup, self.run["repository_id"])
                tool = discovered_tools(db, lookup.service_id)[lookup.tool]
                if tool_signature(tool) != self.frozen.mcp_signature:
                    raise ValueError("MCP 工具契约已变化")
        except (LookupError, ValueError):
            self._mcp_failure(path, source, lookup, "授权已撤销或服务已停用")
            return None
        cached = self._existing("mcp", "", source)
        if cached and cached["status"] == "complete":
            value = json.loads(cached["evidence"])
            ident = self._event("mcp", path, source, "used", value)
            return {"ref": ident, **value}
        if cached:
            self._mcp_failure(path, source, lookup, "查询失败或上次调用未确认")
            return None
        self._event("mcp", "", source, "started")
        try:
            value = self._lookup(lookup, service)
        except (httpx.HTTPError, OSError, InvalidToken, ValueError, LookupError):
            self._event("mcp", "", source, "failed")
            self._mcp_failure(path, source, lookup, "服务失败、超时或契约已更新")
            return None
        self._event("mcp", "", source, "complete", value)
        ident = self._event("mcp", path, source, "used", value)
        return {"ref": ident, **value}

    def _mcp_failure(self, path: str, source: str, lookup: McpLookup,
                     reason: str) -> None:
        self._event("mcp", path, source, "failed", {"message": reason})
        if lookup.failure == "stop":
            raise ModelPageFailure("capability_unavailable")

    def prepare(self, page: DiffPage) -> None:
        """按方案声明的顺序运行已登记步骤，并保留页内引用集合。"""

        self.refs = set()
        self.prepared = {}
        for step in self.document.steps:
            check_cancellation()
            if step == "skills":
                matched = []
                for skill in self.skills:
                    match = fnmatchcase(page.path, skill.pattern)
                    version = f"{skill.name} #{skill.id}"
                    ident = self._event("skill", page.path, version,
                                        "matched" if match else "skipped")
                    if match:
                        matched.append({"ref": ident, "name": version, "instructions": skill.body})
                        self.refs.add(ident)
                self.prepared["skills"] = matched
            elif step == "read_file":
                sources = self._files(page.path)
                self.prepared["related_files"] = sources
                self.refs.update(item["ref"] for item in sources)
            elif self.document.mcp:
                result = self._mcp(page.path, self.document.mcp)
                if result:
                    self.prepared["reference_document"] = result
                    self.refs.add(result["ref"])
