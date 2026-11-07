"""从已校验 OCR 结果提取有界失败证据；纯投影，不读工件、不写库、不触发重试。"""

from __future__ import annotations

from collections import Counter
from re import fullmatch
from typing import Any, Literal

from ocr_manager.review_diagnostic_contracts import (
    DiagnosticSignal,
    FailureAnalysis,
    FailureGroup,
    RequestEvidence,
)

MAX_ITEMS = 5000
MAX_GROUPS = 1000
MAX_REQUESTS = 1000
MAX_ATTEMPTS = 64
MAX_DETAILS = 50
ReportState = Literal["available", "missing", "unsupported", "malformed", "limited"]
LABELS = {
    "coverage_timeout": "覆盖项记录超时，具体触发层级需结合请求核对",
    "coverage_budget": "覆盖项记录预算耗尽",
    "http_504": "上游请求返回 HTTP 504，具体网关层级未知",
    "http_other": "上游请求返回其他 HTTP 错误",
    "context_timeout": "请求记录 context 超时，具体触发源未知",
    "search_limit": "工具搜索达到匹配上限",
    "missing_dependency": "工具读取的依赖路径在目标版本不存在",
}


def _number(value: Any) -> int | None:
    return value if type(value) is int and 0 <= value <= 10**12 else None


def _paths(items: list[Any]) -> set[str]:
    return {item["path"] for item in items if isinstance(item, dict)
            and isinstance(item.get("path"), str) and 0 < len(item["path"]) <= 4096}


def _groups(raw: Any, selected: set[str], failed: set[str]) -> tuple[
        list[FailureGroup], dict[str, str], bool]:
    if not isinstance(raw, list) or not raw or len(raw) > MAX_GROUPS:
        return [], {}, False
    result: list[FailureGroup] = []
    aliases: dict[str, list[str]] = {}
    seen: set[str] = set()
    for index, group in enumerate(raw):
        paths = group.get("files") if isinstance(group, dict) else None
        if (not isinstance(paths, list) or not paths or len(paths) > MAX_ITEMS
                or any(not isinstance(path, str) or path not in selected for path in paths)
                or len(set(paths)) != len(paths) or seen.intersection(paths)):
            return [], {}, False
        seen.update(paths)
        group_id = f"group-{index + 1}"
        # OCR 使用逗号串描述整组；只匹配完整已知序列，绝不拆分可能含逗号的路径。
        for alias in {",".join(paths), ",".join(sorted(paths))}:
            aliases.setdefault(alias, []).append(group_id)
        count = len(failed.intersection(paths))
        if count:
            result.append(FailureGroup(group_id=group_id, paths=paths, failed_count=count))
    mapping = {key: values[0] for key, values in aliases.items() if len(set(values)) == 1}
    return result, mapping, failed <= seen


def _request(raw: Any, aliases: dict[str, str], signals: Counter[str]) -> RequestEvidence | None:
    if not isinstance(raw, dict) or raw.get("outcome") != "failed":
        return None
    attempts = raw.get("attempts")
    if (not isinstance(attempts, list) or not 0 < len(attempts) <= MAX_ATTEMPTS
            or any(not isinstance(attempt, dict) for attempt in attempts)):
        return None
    statuses: set[int] = set()
    errors: set[str] = set()
    phases: set[str] = set()
    durations: list[int] = []
    backoffs: list[int] = []
    for attempt in attempts:
        status = _number(attempt.get("status_code"))
        if status is not None and 400 <= status <= 599:
            statuses.add(status)
            signals["http_504" if status == 504 else "http_other"] += 1
        error = attempt.get("error_class")
        phase = attempt.get("failure_phase")
        if isinstance(error, str) and error in {"timeout", "network", "transport", "provider"}:
            errors.add(error)
        if isinstance(phase, str) and phase in {"context", "http", "transport"}:
            phases.add(phase)
        if error == "timeout" and phase == "context":
            signals["context_timeout"] += 1
        if (duration := _number(attempt.get("duration_to_headers_ms"))) is not None:
            durations.append(duration)
        if (backoff := _number(attempt.get("observed_backoff_ms"))) is not None:
            backoffs.append(backoff)
    task = raw.get("task_type")
    path = raw.get("file_path")
    logical_id = raw.get("logical_request_id")
    return RequestEvidence(
        logical_request_id=logical_id if isinstance(logical_id, str) and
        fullmatch(r"[a-f0-9]{64}", logical_id) else None,
        group_id=aliases.get(path) if isinstance(path, str) else None,
        task_type=task if task in ("plan_task", "main_task") else "unknown",
        request_no=_number(raw.get("request_no")), attempts=len(attempts),
        http_statuses=sorted(statuses), error_classes=sorted(errors), failure_phases=sorted(phases),
        duration_to_headers_ms=durations, observed_backoff_ms=backoffs)


def _requests(raw: Any, aliases: dict[str, str], signals: Counter[str]) -> tuple[
        ReportState, list[RequestEvidence]]:
    if raw is None:
        return "missing", []
    if not isinstance(raw, dict):
        return "malformed", []
    if raw.get("schema_version") != "ocr.llm-retry-report/v1":
        return "unsupported", []
    requests = raw.get("requests")
    if not isinstance(requests, list):
        return "malformed", []
    if len(requests) > MAX_REQUESTS:
        return "limited", []
    result = []
    for request in requests:
        if (not isinstance(request, dict)
                or request.get("outcome") not in ("failed", "succeeded", "success")):
            return "malformed", []
        evidence = _request(request, aliases, signals)
        if request.get("outcome") == "failed" and evidence is None:
            return "malformed", []
        if evidence:
            result.append(evidence)
    return ("limited" if len(result) > MAX_DETAILS else "available"), result[:MAX_DETAILS]


def _tool_signals(raw: Any, signals: Counter[str]) -> None:
    details = raw.get("failure_details") if isinstance(raw, dict) else None
    if not isinstance(details, list) or len(details) > MAX_REQUESTS:
        return
    for detail in details:
        if not isinstance(detail, dict):
            continue
        message = detail.get("error")
        if not isinstance(message, str) or len(message) > 8192:
            continue
        if detail.get("tool_name") == "code_search" and "match limit exceeded" in message:
            signals["search_limit"] += 1
        if (detail.get("tool_name") == "file_read" and "node_modules/" in message
                and ("does not exist in" in message or "not found" in message)):
            signals["missing_dependency"] += 1


def failure_analysis(result: dict[str, Any]) -> dict[str, Any] | None:
    """只接受已通过业务输入校验的结果；未知/超限证据保守披露，不改变终态。"""

    manifest = result.get("manifest")
    coverage = manifest.get("coverage") if isinstance(manifest, dict) else None
    if not isinstance(coverage, dict):
        return None
    sets: list[list[Any]] = []
    for key in ("selected", "completed", "reused", "failed"):
        items = coverage.get(key)
        if not isinstance(items, list) or len(items) > MAX_ITEMS:
            return None
        sets.append(items)
    selected, completed, reused, failed = sets
    # 1. 覆盖计数来自已校验 manifest，分组只能引用同一次结果的覆盖路径。
    signals: Counter[str] = Counter()
    for item in failed:
        if isinstance(item, dict) and item.get("classification") in ("timeout", "budget"):
            signals[f"coverage_{item['classification']}"] += 1
    groups, aliases, complete = _groups(result.get("groups"), _paths(selected), _paths(failed))
    # 2. 外部报告仅提取允许字段；损坏报告不保留前半段信号，避免暗示完整解析。
    request_signals: Counter[str] = Counter()
    state, requests = _requests(result.get("retry_report"), aliases, request_signals)
    if state in ("available", "limited"):
        signals.update(request_signals)
    _tool_signals(result.get("tool_calls"), signals)
    notes = ["仅记录报告提供的失败证据，不能计算全部成功请求的耗时分布。",
             "HTTP 504、context 标签及覆盖超时可同时存在，不能据此确定全部因果关系。"]
    if not complete:
        notes.append("缺少完整可信分组，失败分组总数未知。")
    if any(request.group_id is None for request in requests):
        notes.append("部分请求无法无歧义关联分组，未猜测路径。")
    if state != "available":
        notes.append("请求报告缺失、不兼容、损坏或超出展示上限，明细可能不完整。")
    if len(groups) > MAX_DETAILS:
        notes.append("失败分组明细已截断，分组总数保留。")
    # 3. 摘要不包含外部自由文本，也不把部分完成转为整批自动重试。
    summary = f"完成 {len(completed) + len(reused)}/{len(selected)} 个文件"
    if failed:
        summary += f"；{len(groups)} 个失败分组" if complete else f"；{len(failed)} 个文件未完成"
    if signals["http_504"]:
        summary += "；模型请求存在 HTTP 504"
    return FailureAnalysis(
        summary=summary, selected_count=len(selected), completed_count=len(completed) + len(reused),
        failed_count=len(failed), failed_group_count=len(groups) if complete else None,
        report_state=state, groups=groups[:MAX_DETAILS], requests=requests,
        signals=[DiagnosticSignal(code=key, message=LABELS[key], count=count)
                 for key, count in sorted(signals.items())], notes=notes,
    ).model_dump()
