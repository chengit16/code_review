"""校验补审集合并生成候选聚合；不读工件、不写库，不冒充 OCR 原始 manifest。"""

from __future__ import annotations

import hashlib
import json
from typing import Any


class RecoveryConflict(ValueError):
    """固定错误码供 API/Worker 使用，不携带模型响应、工件路径或凭据。"""


def encoded(value: Any) -> str:
    """确定性编码仅用于内部快照和摘要；不直接把未投影内容返回 HTTP。"""

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    """关联同一份数据库安全结果，防止旧资格或迟到结果覆盖新聚合。"""

    return hashlib.sha256(encoded(value).encode()).hexdigest()


def coverage_items(result: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    """路径与 item ID 都须唯一，且终态分区精确覆盖 selected；未知结构默认拒绝。"""

    coverage = (result.get("manifest") or {}).get("coverage")
    if not isinstance(coverage, dict):
        raise RecoveryConflict("coverage_invalid")
    groups: dict[str, dict[str, dict[str, Any]]] = {}
    for name in ("selected", "completed", "reused", "failed", "waived"):
        items = coverage.get(name)
        if not isinstance(items, list) or len(items) > 5000:
            raise RecoveryConflict("coverage_invalid")
        group: dict[str, dict[str, Any]] = {}
        ids: set[str] = set()
        for item in items:
            if not isinstance(item, dict):
                raise RecoveryConflict("coverage_invalid")
            path, identifier = item.get("path"), item.get("item_id")
            if (not isinstance(path, str) or not 0 < len(path) <= 4096
                    or path.startswith("/") or "\\" in path
                    or any(part in {"", ".", ".."} for part in path.split("/"))
                    or any(ord(char) < 32 or ord(char) == 127 for char in path)
                    or not isinstance(identifier, str) or not 0 < len(identifier) <= 256
                    or path in group or identifier in ids):
                raise RecoveryConflict("coverage_invalid")
            group[path] = item
            ids.add(identifier)
        groups[name] = group
    seen: set[str] = set()
    for name in ("completed", "reused", "failed", "waived"):
        for path, item in groups[name].items():
            if (path in seen or path not in groups["selected"] or
                    item["item_id"] != groups["selected"][path]["item_id"]):
                raise RecoveryConflict("coverage_invalid")
            seen.add(path)
    if seen != groups["selected"].keys():
        raise RecoveryConflict("coverage_invalid")
    return groups


def merge_candidate(source: dict[str, Any], child: dict[str, Any],
                    approved: list[dict[str, str]], recovery_id: int,
                    source_origins: list[dict[str, Any]]) -> tuple[
                        dict[str, Any], list[dict[str, Any]]]:
    """只替换批准失败项；保留初审发现顺序与根 item ID，新增发现单独记录批次来源。"""

    # 1. 独立子集不能携带原生复用或新增豁免，不能扩张/遗漏审核集合。
    old, new = coverage_items(source), coverage_items(child)
    if (child.get("summary") or {}).get("budget_exceeded") is True:
        raise RecoveryConflict("budget_unconfirmed")
    if (child["manifest"].get("terminal_state") not in {"complete", "partial"}
            or child["manifest"]["terminal_state"] == "complete" and new["failed"]):
        raise RecoveryConflict("child_not_usable")
    approved_paths = {item["path"] for item in approved}
    if (len(approved_paths) != len(approved) or approved_paths != old["failed"].keys()
            or approved_paths != new["selected"].keys() or new["reused"] or new["waived"]
            or any(item["item_id"] != old["failed"][item["path"]]["item_id"]
                   for item in approved)):
        raise RecoveryConflict("subset_mismatch")
    # 2. 聚合使用根覆盖身份；原始 OCR 工件不改写，也不伪造其输入或 schema。
    coverage = {name: list(items.values()) for name, items in old.items()}
    coverage["completed"] += [old["selected"][path] for path in new["completed"]]
    coverage["failed"] = [old["selected"][path] | {
        "classification": item.get("classification", "unknown")}
        for path, item in new["failed"].items()]
    comments = list(source.get("comments") or [])
    origins = list(source_origins)
    known = {encoded(item): index for index, item in enumerate(comments)}
    for index, comment in enumerate(child.get("comments") or []):
        if comment.get("path") not in approved_paths:
            raise RecoveryConflict("finding_outside_subset")
        identity = encoded(comment)
        if identity not in known:
            known[identity] = len(comments)
            comments.append(comment)
            origins.append({"recovery_id": recovery_id, "comment_index": index})
        else:
            position = known[identity]
            origin = dict(origins[position])
            origin["also_seen_in"] = [*origin.get("also_seen_in", []), {
                "recovery_id": recovery_id, "comment_index": index}]
            origins[position] = origin
    if len(comments) > 10000 or len(origins) != len(comments):
        raise RecoveryConflict("findings_invalid")
    # 3. 候选只表示覆盖和发现；用量保留逐批次，不把累计用量写成新一次模型消耗。
    state = "partial" if coverage["failed"] else "complete"
    result = source | {"comments": comments, "manifest": {
        "terminal_state": state, "coverage": coverage}, "usage": None,
        "failure_analysis": None, "diagnostic": None, "retry_summary": None,
        "schema_version": "platform.recovery-candidate/v1"}
    coverage_items(result)
    return result, origins
