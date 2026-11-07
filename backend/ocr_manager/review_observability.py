"""计算逐次执行、排队和已知成本；只使用 SQLite 安全事实，不读取原始工件。"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import UTC, datetime
from decimal import Decimal, DecimalException
from typing import Any

from ocr_manager.model_pricing import estimate_cost

REASONS = {
    "empty_diff": "固定范围没有文件差异，未调用模型",
    "excluded_by_rules": "变更文件均被 OCR 规则排除，未调用模型",
    "newline_filtered": "候选文件经纯换行策略排除后为空，未调用模型；不代表原始全范围已由模型评审",
    "scope_filter": "纯换行过滤或覆盖一致性校验失败，不能确认评审结论",
    "skipped_unknown": "没有可审查文件，历史排除原因不完整",
    "scope_limit": "可审查文件超过项目上限，未调用模型；请拆分范围或调整项目限额",
    "timeout": "评审预算耗尽，不自动整批重试",
    "provider_http": "模型或评审依赖请求失败，请检查 HTTP 状态及连接配置",
    "cancelled": "用户已停止评审，不能视为完整无问题",
    "partial": "仅部分覆盖完成，不能视为完整无问题",
    "complete": "OCR 已完成选中范围，仍需留意排除和豁免",
    "queued": "等待 Worker，可能包含重试退避",
    "running": "正在执行，尚无最终结论",
    "failed": "评审失败，请查看诊断与历史尝试",
    "interrupted": "Worker 中断，结果未确认，请查看恢复记录",
    "validation": "输入、配置或结果校验失败，请核对固定范围与受控工件",
    "network": "评审依赖网络连接失败，请检查重试决定",
    "result_format": "OCR 结果格式无效，不能确认评审结论",
    "preview": "OCR 范围预览失败，未进入正式评审",
    "configuration": "OCR 配置失败，请检查模型与端点",
}


def reason_code(status: str, result: dict[str, Any] | None, error: str | None) -> str:
    """优先使用可信诊断和预览；旧记录只提供保守兜底，不猜测纯换行跳过。"""

    result = result or {}
    diagnostic = result.get("diagnostic")
    if status == "failed" and isinstance(diagnostic, dict):
        return str(diagnostic.get("category") or "failed")
    if status == "failed" and error and error.startswith("["):
        category = error[1:].split("]", 1)[0]
        if category in {"scope_limit", "timeout", "provider_http", "validation", "result_format",
                        "preview", "configuration", "network", "unknown", "ocr_failed",
                        "scope_filter"}:
            return category
    if status == "skipped":
        filtering = result.get("input_filter")
        if isinstance(filtering, dict) and filtering.get("excluded_count", 0) > 0:
            return "newline_filtered"
        preview = result.get("preview")
        if isinstance(preview, dict) and isinstance(preview.get("files"), list):
            return "empty_diff" if not preview["files"] else "excluded_by_rules"
        return "skipped_unknown"
    return status if status in REASONS else "failed"


def _time(raw: Any) -> datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    except ValueError:
        return None


def _seconds(start: Any, end: Any) -> float | None:
    left, right = _time(start), _time(end)
    return round((right - left).total_seconds(), 3) if left and right and right >= left else None


def execution_summary(job: dict[str, Any], attempts: list[dict[str, Any]],
                      now: datetime | None = None) -> dict[str, Any]:
    """明确历史缺口；累计只加已结束尝试及当前运行尝试，排队不延长执行时长。"""

    # 1. 同一时刻计算全部时间口径；尝试编号不连续或时间缺失则披露部分历史。
    clock = (now or datetime.now(UTC)).isoformat()
    ordered = sorted(attempts, key=lambda item: item["attempt_number"])
    intervals = [None if item.get("reason_code") in {"interrupted", "interrupted_cancelled"}
                 or (item.get("error") or "").startswith("Worker 中断") else
                 _seconds(item.get("started_at"), item.get("finished_at")) for item in ordered]
    running = job["status"] == "running"
    if running:
        intervals.append(_seconds(job.get("started_at"), clock))
    known = [value for value in intervals if value is not None]
    expected = int(job.get("attempts") or 0)
    not_started = expected == 0 and job["status"] == "queued"
    numbers_complete = [item["attempt_number"] for item in ordered] == list(
        range(1, expected + 1 - int(running)))
    complete = numbers_complete and len(known) == expected and (expected > 0 or not_started)
    first = ordered[0].get("started_at") if ordered else job.get("started_at")
    if (ordered and ordered[0]["attempt_number"] != 1) or (not ordered and expected > 1):
        first = None
    first_wait = _seconds(job.get("created_at"), first) if expected else _seconds(
        job.get("created_at"), clock if job["status"] == "queued" else job.get("finished_at"))
    latest = (_seconds(job.get("started_at"), clock) if running else
              intervals[-1] if intervals else None)
    # 2. 只使用已保存的调度时间拆分退避和就绪等待，不拿总历时冒充执行时间。
    backoffs: list[float] = []
    waits: list[float] = []
    schedule_complete = True
    for index, attempt in enumerate(ordered):
        ready = attempt.get("retry_ready_at")
        next_start = (ordered[index + 1].get("started_at") if index + 1 < len(ordered)
                      else job.get("started_at") if running else None)
        if ready:
            until = clock if job["status"] == "queued" and index == len(ordered) - 1 else ready
            ready_time, until_time = _time(ready), _time(until)
            end = min(ready_time, until_time) if ready_time and until_time else None
            delay = _seconds(attempt.get("finished_at"), end.isoformat() if end else None)
            wait = _seconds(ready, next_start or (clock if job["status"] == "queued" else ready))
            if delay is not None:
                backoffs.append(delay)
            else:
                schedule_complete = False
            if wait is not None:
                waits.append(wait)
            elif not (job["status"] == "queued" and ready_time and
                      (clock_time := _time(clock)) and clock_time < ready_time):
                schedule_complete = False
        elif index + 1 < len(ordered) or running or job["status"] == "queued":
            schedule_complete = False
    total = _seconds(job.get("created_at"), clock if job["status"] in {"queued", "running"}
                     else job.get("finished_at"))
    return {"first_queue_seconds": first_wait, "latest_execution_seconds": latest,
            "cumulative_execution_seconds": round(sum(known), 3) if known else 0 if not_started
            else None, "execution_complete": complete, "known_attempts": len(known),
            "total_attempts": expected, "total_elapsed_seconds": total,
            "retry_backoff_seconds": round(sum(backoffs), 3) if schedule_complete else None,
            "retry_ready_wait_seconds": round(sum(waits), 3) if schedule_complete else None,
            "schedule_complete": schedule_complete, "calculated_at": clock}


def usage_summary(job: dict[str, Any], attempts: list[dict[str, Any]]) -> dict[str, Any]:
    """逐次使用历史单价求和；未知用量与币种分别披露，不把未知计费当作零。"""

    totals: dict[str, int] = {}
    costs: dict[str, Decimal] = {}
    known = priced = 0
    # 1. 累加可验证的用量；只有总 Token 时仍保留已知下限，但不伪造输入输出。
    for attempt in attempts:
        result = json.loads(attempt["result_json"]) if attempt.get("result_json") else {}
        usage = result.get("usage")
        if not isinstance(usage, dict):
            if attempt["status"] == "skipped":
                known += 1
            continue
        values = {key: value for key in ("input_tokens", "output_tokens", "total_tokens")
                  if type(value := usage.get(key)) is int and value >= 0}
        for key in ("input_tokens", "output_tokens"):
            if key in values:
                totals[key] = totals.get(key, 0) + values[key]
        total = values.get("total_tokens")
        if total is None and "input_tokens" in values and "output_tokens" in values:
            total = values["input_tokens"] + values["output_tokens"]
        if total is not None:
            totals["total_tokens"] = totals.get("total_tokens", 0) + total
        if not all(key in values for key in ("input_tokens", "output_tokens")):
            continue
        known += 1
        # 2. 只按该次历史单价估算；极端草稿单价导致累计溢出时也保留未知边界。
        snapshot = (json.loads(attempt["config_snapshot"])
                    if attempt.get("config_snapshot") else None)
        cost = estimate_cost(usage, snapshot)
        if cost:
            currency = cost["currency"]
            try:
                costs[currency] = costs.get(currency, Decimal(0)) + Decimal(cost["total"])
            except DecimalException:
                continue
            priced += 1
    # 3. 当前运行中的尝试也计入分母，未产出可信用量时累计必须标记不完整。
    expected = int(job.get("attempts") or 0)
    return {"known_usage_attempts": known, "total_attempts": expected,
            "usage_complete": known == expected, "priced_attempts": priced,
            "known_tokens": totals if "total_tokens" in totals else None,
            "known_costs": [{"currency": currency, "total": str(value)}
                            for currency, value in sorted(costs.items())],
            "cost_complete": expected > 0 and priced == expected}


def enrich_jobs(db: sqlite3.Connection, jobs: list[dict[str, Any]],
                *, include_scope_paths: bool = False) -> None:
    """批量读取逐次证据，无逐行工件访问或 N+1 查询；列表不返回原始结果集合。"""

    if not jobs:
        return
    from ocr_manager.review_conclusions import attach_conclusions
    from ocr_manager.review_effective import attach_effective
    from ocr_manager.review_historical_diagnostics import attach_historical_diagnostics
    from ocr_manager.review_total_usage import attach_total_usage

    attach_conclusions(db, jobs)
    attach_historical_diagnostics(db, jobs)
    placeholders = ",".join("?" for _ in jobs)
    rows = db.execute(f"""SELECT job_id,attempt_number,status,started_at,finished_at,
        reason_code,error,scheduled_at,retry_ready_at,
        CASE WHEN json_valid(config_snapshot) THEN
          json_object('pricing',json_extract(config_snapshot,'$.pricing')) END AS config_snapshot,
        CASE WHEN json_valid(result_json) THEN
          json_object('usage',json_extract(result_json,'$.usage')) END AS result_json
        FROM review_attempts WHERE job_id IN ({placeholders}) ORDER BY attempt_number""",
        [job["id"] for job in jobs]).fetchall()
    groups: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(row["job_id"], []).append(dict(row))
    for job in jobs:
        attempts = groups.get(job["id"], [])
        result = job.get("result") or {}
        analysis = result.get("failure_analysis")
        job["failure_analysis"] = analysis if include_scope_paths else None
        job["failure_summary"] = (analysis.get("summary") if isinstance(analysis, dict)
                                  else job.get("failure_summary"))
        code = job.get("reason_code") or reason_code(job["status"], result, job.get("error"))
        job["reason"] = {"code": code, "message": REASONS.get(code, "评审异常，请查看安全诊断摘要")}
        if code == "provider_http" and (
            match := re.search(r"HTTP ([45]\d{2})", job.get("error") or "")
        ):
            job["reason"]["message"] += f"（HTTP {match.group(1)}）"
        job["timing"] = execution_summary(job, attempts)
        job["cumulative_usage"] = usage_summary(job, attempts)
        raw_scope = job.pop("scope_json", None)
        job["scope_analysis"] = json.loads(raw_scope) if raw_scope else None
        if job["scope_analysis"] and not include_scope_paths:
            job["scope_analysis"].pop("newline_only_paths", None)
            job["scope_analysis"].pop("filter_requested_paths", None)
    attach_total_usage(db, jobs, groups)
    attach_effective(db, jobs, detail=include_scope_paths)
