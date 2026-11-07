"""分类评审故障与整批重试预算；不执行外部调用，也不保存原始服务响应。"""

from __future__ import annotations

import json
import random
import subprocess
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from ocr_manager.range_preflight import input_policy

REVIEW_POLICY = {"version": 2, "max_attempts": 2, "retry_on_timeout": False}
REVIEW_POLICY_SNAPSHOT = json.dumps(
    {"review_policy": REVIEW_POLICY, "input_policy": input_policy()}, sort_keys=True)
MAX_RETRY_DELAY = 300


class ReviewFailure(RuntimeError):
    """携带可信中文摘要与允许字段的评审故障；调用方不得传入原始外部错误正文。"""

    def __init__(self, category: str, message: str, *, retryable: bool = False,
                 http_status: int | None = None, retry_after: int = 0) -> None:
        super().__init__(f"[{category}] {message}")
        self.category = category
        self.retryable = retryable
        self.http_status = http_status
        self.retry_after = retry_after

    def projection(self) -> dict[str, str | int | bool | None]:
        """仅投影稳定的类别、状态码和重试决定，不复制请求或响应内容。"""

        return {"category": self.category, "http_status": self.http_status,
                "retryable": self.retryable, "retry_scheduled": False}


def attempt_limit(snapshot: str | None) -> int:
    """第一、二版策略均限制两次；更早的无策略记录保留三次恢复预算。"""

    data = json.loads(snapshot) if snapshot else {}
    policy = data.get("review_policy") if isinstance(data, dict) else None
    return 2 if isinstance(policy, dict) and policy.get("version") in {1, 2} and (
        policy.get("max_attempts") == 2 and policy.get("retry_on_timeout") is False
    ) else 3


def retry_delay(attempt: int, retry_after: int = 0) -> int:
    """有限退避附加抖动；只接受已验证不超过上限的服务端等待时间。"""

    return min(MAX_RETRY_DELAY, max(20 * attempt * attempt + random.randint(0, 5), retry_after))


def _retry_after(response: httpx.Response) -> int:
    value = response.headers.get("Retry-After", "")
    try:
        if value.isdigit():
            return int(value)
        date = parsedate_to_datetime(value)
        if date.tzinfo is None:
            return MAX_RETRY_DELAY + 1
        return max(0, int((date - datetime.now(UTC)).total_seconds()) + 1)
    except (TypeError, ValueError, OverflowError):
        return 0


def http_failure(status: int, retry_after: int = 0) -> ReviewFailure:
    """HTTP 错误只保留状态码；超出可等待预算时停止而非提前重试。"""

    retryable = (status == 429 or status >= 500) and retry_after <= MAX_RETRY_DELAY
    advice = ("请检查模型名称、端点与访问权限" if status in {400, 401, 403, 404}
              else "上游服务暂时不可用" if retryable else "请检查上游服务后人工重试")
    return ReviewFailure("provider_http", f"模型或评审依赖请求返回 HTTP {status}，{advice}",
                         retryable=retryable, http_status=status, retry_after=retry_after)


def classify_review_error(error: Exception) -> ReviewFailure:
    """只重试明确的瞬态故障；事件与通知继续使用各自的分类，未知错误保守失败。"""

    if isinstance(error, ReviewFailure):
        return error
    if isinstance(error, httpx.HTTPStatusError):
        return http_failure(error.response.status_code, _retry_after(error.response))
    if isinstance(error, (httpx.NetworkError, httpx.TimeoutException, httpx.RemoteProtocolError)):
        return ReviewFailure("network", "评审依赖网络连接暂时失败", retryable=True)
    if isinstance(error, (subprocess.TimeoutExpired, TimeoutError)):
        return ReviewFailure("timeout", "评审或外部命令预算耗尽，不自动整批重试")
    if isinstance(error, ValueError):
        return ReviewFailure("validation", "评审输入、配置或结果校验失败，请检查受控诊断工件")
    return ReviewFailure("unknown", "评审发生未识别错误，请通过关联 ID 检查服务日志")


def result_failure(status: str, result: dict[str, Any]) -> ReviewFailure | None:
    """可信失败结果也按错误类别处理；有已完成覆盖时不自动重跑整批模型。"""

    if status != "failed":
        return None
    # 1. 只信任支持的报告版本；未知结构不推断为网络故障。
    fallback = ReviewFailure("ocr_failed", "OCR 评审失败，请查看受控诊断工件")
    report = result.get("retry_report")
    if not isinstance(report, dict) or report.get("schema_version") != "ocr.llm-retry-report/v1":
        return fallback
    requests = report.get("requests")
    if not isinstance(requests, list) or not 0 < len(requests) <= 10000:
        return fallback
    # 2. 每个失败请求取最后一次尝试，任一永久故障都优先阻断整批重试。
    failures: list[ReviewFailure] = []
    for request in requests:
        if not isinstance(request, dict):
            return fallback
        if request.get("outcome") != "failed":
            continue
        attempts = request.get("attempts")
        if not isinstance(attempts, list) or not attempts or not isinstance(attempts[-1], dict):
            failures.append(fallback)
            continue
        latest = attempts[-1]
        code = latest.get("status_code")
        if type(code) is int and 400 <= code <= 599:
            failures.append(http_failure(code))
        elif isinstance(latest.get("error_class"), str) and latest["error_class"] in {
            "network", "transport"
        }:
            failures.append(ReviewFailure("network", "OCR 模型连接暂时失败", retryable=True))
        else:
            failures.append(fallback)
    if not failures:
        return fallback
    failure = next((item for item in failures if not item.retryable), failures[0])
    # 3. 已完成或复用的覆盖意味着整批重跑会重复工作，留待人工恢复。
    manifest = result.get("manifest")
    coverage = manifest.get("coverage") if isinstance(manifest, dict) else None
    if isinstance(coverage, dict) and (coverage.get("completed") or coverage.get("reused")):
        return ReviewFailure(failure.category, f"{failure}；已有完成覆盖，不自动整批重跑",
                             http_status=failure.http_status)
    return failure


def retry_summary(result: dict[str, Any]) -> dict[str, int] | None:
    """仅保存受支持报告的计数，区分 OCR 内部重试与平台整批重试。"""

    report = result.get("retry_report")
    if not isinstance(report, dict) or report.get("schema_version") != "ocr.llm-retry-report/v1":
        return None
    return {key: value for key in ("total_requests", "total_retries", "failed_requests")
            if type(value := report.get(key)) is int and value >= 0}
