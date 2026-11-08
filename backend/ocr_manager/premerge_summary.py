"""合并前列表的安全结果摘要；只读持久化结果，不推断问题处置或触发外部调用。"""

from __future__ import annotations

import json
from typing import Any


def premerge_summary(text: str | None) -> dict[str, Any]:
    """缺少逐项覆盖证明时保留未知；只返回数量和范围，不返回模型正文。"""

    unknown: dict[str, Any] = {"result_available": False, "findings_count": None,
        "highest_severity": None, "coverage": "unknown", "excluded_count": None,
        "waived_count": None}
    try:
        raw = json.loads(text or "null")
    except (ValueError, TypeError):
        return unknown
    if not isinstance(raw, dict) or not isinstance(raw.get("comments"), list):
        return unknown
    comments = raw["comments"]
    if any(not isinstance(item, dict) or not isinstance(item.get("path"), str)
           or not isinstance(item.get("content"), str) for item in comments):
        return unknown
    ranks = ("critical", "high", "medium", "low")
    highest = next((level for level in ranks
                    if any(item.get("severity") == level for item in comments)), None)
    manifest = raw.get("manifest")
    coverage = manifest.get("coverage") if isinstance(manifest, dict) else None
    state = "unknown"
    waived: int | None = None
    if isinstance(coverage, dict):
        selected, completed, reused = (coverage.get(key) for key in
                                       ("selected", "completed", "reused"))
        groups = (selected, completed, reused)
        valid = all(isinstance(group, list) and all(
            isinstance(item, dict) and isinstance(item.get("item_id"), str)
            and bool(item["item_id"]) for item in group) for group in groups)
        failed, exemptions = coverage.get("failed"), coverage.get("waived")
        if isinstance(exemptions, list):
            waived = len(exemptions)
        if (valid and isinstance(manifest, dict) and isinstance(selected, list)
                and isinstance(completed, list) and isinstance(reused, list)
                and isinstance(failed, list) and isinstance(exemptions, list)):
            selected_ids = [item["item_id"] for item in selected]
            finished_ids = [item["item_id"] for item in [*completed, *reused]]
            complete = (manifest.get("terminal_state") == "complete"
                        and len(selected_ids) == len(set(selected_ids))
                        and len(finished_ids) == len(set(finished_ids))
                        and set(selected_ids) == set(finished_ids)
                        and not failed and not exemptions)
            state = "complete" if complete else "partial"
    filters = raw.get("input_filter")
    excluded = filters.get("excluded_count") if isinstance(filters, dict) else None
    if not isinstance(excluded, int) or isinstance(excluded, bool) or excluded < 0:
        excluded = None
    return {"result_available": True, "findings_count": len(comments),
            "highest_severity": highest, "coverage": state,
            "excluded_count": excluded, "waived_count": waived}
