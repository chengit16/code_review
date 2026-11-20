"""Worker 执行工具发现和固定提交预览；HTTP 仅登记检查。"""

from __future__ import annotations

import json
import sqlite3
import subprocess
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

import httpx
from cryptography.fernet import InvalidToken
from unidiff import UnidiffParseError

from ocr_manager.agent_capabilities import check_mcp, check_scheme, get_scheme, get_service
from ocr_manager.agent_mcp import McpClient
from ocr_manager.agent_review_store import current_source, source_range
from ocr_manager.config import Settings
from ocr_manager.review_prototype.input import freeze_input
from ocr_manager.secrets import SecretBox
from ocr_manager.storage import Store


def queue_check(db: sqlite3.Connection, kind: str, subject_id: int,
                job_id: int | None = None) -> int:
    """固定预览来源；同范围已有活动检查时复用。"""

    if job_id is not None:
        source = current_source(db, job_id)
        if source is None or source["superseded"]:
            raise ValueError("任务缺少当前 OCR 版本")
        base, head = source_range(source)
        inputs = {"repository_id": source["repository_id"], "attempt_id": source["attempt_id"],
                  "base": base, "head": head}
    else:
        inputs = {}
    payload = json.dumps(inputs)
    existing = db.execute("""SELECT id FROM agent_capability_checks WHERE kind=?
        AND subject_id=? AND job_id IS ? AND input_json=? AND status IN ('queued','running')""",
        (kind, subject_id, job_id, payload)).fetchone()
    if existing:
        return int(existing["id"])
    cursor = db.execute("""INSERT INTO agent_capability_checks(kind,subject_id,job_id,input_json)
        VALUES(?,?,?,?)""", (kind, subject_id, job_id, payload))
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def claim_check(store: Store) -> dict[str, Any] | None:
    """在 Worker 的接入槽原子领取一个检查。"""

    with store.connection() as db:
        row = db.execute("""UPDATE agent_capability_checks SET status='running' WHERE id=(
            SELECT id FROM agent_capability_checks WHERE status='queued' ORDER BY id LIMIT 1)
            RETURNING *""").fetchone()
        return dict(row) if row else None


def _discover(store: Store, settings: Settings, service_id: int) -> dict[str, object]:
    with store.connection() as db:
        service = get_service(db, service_id)
        if not service["enabled"]:
            raise ValueError("MCP 服务已停用")
    token = (SecretBox(settings.master_key).decrypt(service["token_ciphertext"])
             if service["token_ciphertext"] else "")
    with httpx.Client(trust_env=False) as client:
        mcp = McpClient(client, service["endpoint"], token, service["timeout_seconds"])
        try:
            mcp.initialize()
            return {"tools": mcp.tools()}
        finally:
            mcp.close()


def _preview(store: Store, data_dir: Path, task: dict[str, Any]) -> dict[str, object]:
    inputs = json.loads(task["input_json"])
    repository_id = inputs["repository_id"]
    with store.connection() as db:
        scheme = get_scheme(db, task["subject_id"])
        skills = check_scheme(db, scheme, trial=True)
        lookup = scheme.document.mcp
        mcp_authorized = None
        if lookup:
            try:
                check_mcp(db, lookup, repository_id)
                mcp_authorized = True
            except ValueError:
                mcp_authorized = False
        source = current_source(db, task["job_id"])
        if source is None or source["attempt_id"] != inputs["attempt_id"] or source["superseded"]:
            raise ValueError("初审版本已更新")
    snapshot = freeze_input(data_dir / "repositories" / str(repository_id), str(repository_id),
                            inputs["base"], inputs["head"], rule_digest="", context_digest="")
    paths = sorted({item.path for item in snapshot.hunks})
    return {"scheme_id": scheme.id, "job_id": task["job_id"], "attempt": source["attempts"],
            "path_count": len(paths), "mcp_authorized": mcp_authorized, "rows": [
                {"path": path, "skills": [f"{skill.name} #{skill.id}" for skill in skills
                                         if fnmatchcase(path, skill.pattern)],
                 "files": [item.path for item in scheme.document.files
                           if fnmatchcase(path, item.pattern)],
                 "mcp": lookup.tool if lookup and fnmatchcase(path, lookup.pattern) else None}
                for path in paths[:300]]}


def execute_check(store: Store, settings: Settings, task: dict[str, Any]) -> None:
    """提交检查终态，避免把服务响应正文或秘密写入错误。"""

    status = "complete"
    try:
        result = (_discover(store, settings, task["subject_id"]) if task["kind"] == "mcp"
                  else _preview(store, settings.data_dir, task))
    except (httpx.HTTPError, OSError, InvalidToken, LookupError, UnidiffParseError, ValueError,
            subprocess.SubprocessError):
        status = "failed"
        result = {"message": "MCP 服务检查失败，请核对地址、凭据与协议"
                  if task["kind"] == "mcp" else "预览失败，请核对当前初审及固定提交缓存"}
    with store.connection() as db:
        db.execute("""UPDATE agent_capability_checks SET status=?,result_json=?,
            finished_at=CURRENT_TIMESTAMP WHERE id=? AND status='running'""",
            (status, json.dumps(result, ensure_ascii=False), task["id"]))
