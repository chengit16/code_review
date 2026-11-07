"""用合成 OCR 报告验证错误投影、瞬态故障分类与整批重试边界，不访问外部服务。"""

from __future__ import annotations

import json
import subprocess
from typing import Any

import httpx
import pytest
from ocr_manager.ocr import classify_result
from ocr_manager.review_failures import (
    REVIEW_POLICY,
    ReviewFailure,
    attempt_limit,
    classify_review_error,
    result_failure,
    retry_delay,
)
from ocr_manager.review_results import project_review_result

SHA = "a" * 40


def failed_result(code: int = 404) -> dict[str, Any]:
    """只构造协议字段与合成敏感标记，不复制真实模型输出或凭据。"""

    item = {"item_id": "one", "path": "main.py"}
    return {"comments": None, "message": "synthetic-private-response",
            "thinking": "synthetic-private-thinking",
            "manifest": {"schema_version": "ocr.run-manifest/v1", "terminal_state": "failed",
                         "input": {"mode": "commit", "resolved_head": SHA},
                         "coverage": {"selected": [item], "completed": [], "reused": [],
                                      "failed": [item], "waived": []}},
            "summary": {"input_tokens": 50, "output_tokens": 0, "total_tokens": 50},
            "retry_report": {"schema_version": "ocr.llm-retry-report/v1", "total_requests": 1,
                             "total_retries": 2, "failed_requests": 1, "requests": [
                                 {"outcome": "failed", "file_path": "synthetic-private-path",
                                  "attempts": [{"status_code": code, "error_class": "provider",
                                                "response": "synthetic-private-response"}]}]}}


def test_failed_null_comments_preserve_original_failure() -> None:
    """空评论不能掩盖 HTTP 404，也不能把外部响应及内部请求详情写入安全结果。"""

    raw = failed_result()
    assert classify_result(raw, SHA) == "failed"
    projection = project_review_result(raw)
    assert projection["comments"] == []
    assert projection["diagnostic"] == {"category": "provider_http", "http_status": 404,
                                         "retryable": False, "retry_scheduled": False}
    assert "HTTP 404" in projection["message"]
    assert projection["retry_summary"] == {
        "total_requests": 1, "total_retries": 2, "failed_requests": 1}
    assert "synthetic-private" not in json.dumps(projection)
    assert raw["comments"] is None


@pytest.mark.parametrize("comments", [None, "unexpected", {"path": "a.py"}, [None]])
def test_malformed_comments_are_not_silent_success(comments: Any) -> None:
    """完整结果的错误评论类型不能被空列表兜底伪装为零问题。"""

    raw = failed_result()
    raw["manifest"]["terminal_state"] = "complete"
    raw["manifest"]["coverage"]["completed"] = raw["manifest"]["coverage"]["failed"]
    raw["manifest"]["coverage"]["failed"] = []
    raw["comments"] = comments
    with pytest.raises(ReviewFailure, match="评论集合"):
        classify_result(raw, SHA)


@pytest.mark.parametrize(("code", "retryable"), [(400, False), (401, False), (403, False),
                                               (404, False), (429, True), (502, True)])
def test_failed_ocr_results_have_explicit_retry_policy(code: int, retryable: bool) -> None:
    """OCR 正常退出但返回失败，也按允许的 HTTP 类别判断是否整批重试。"""

    failure = result_failure("failed", failed_result(code))
    assert failure is not None
    assert failure.http_status == code
    assert failure.retryable is retryable


def test_mixed_and_partly_completed_failures_do_not_restart_all_work() -> None:
    """混合永久错误和已有完成覆盖都不能触发整批重复计费。"""

    raw = failed_result(429)
    raw["retry_report"]["requests"].extend(failed_result(404)["retry_report"]["requests"])
    failure = result_failure("failed", raw)
    assert failure is not None and not failure.retryable
    raw = failed_result(429)
    raw["manifest"]["coverage"]["completed"] = [{"item_id": "two"}]
    failure = result_failure("failed", raw)
    assert failure is not None and not failure.retryable
    assert result_failure("partial", raw) is None


@pytest.mark.parametrize("report", [None, [], {"schema_version": "future"},
                                   {"schema_version": "ocr.llm-retry-report/v1", "requests": [
                                       {"outcome": "failed", "attempts": [
                                           {"error_class": {"unexpected": True}}]}]}])
def test_unknown_report_is_nonretryable(report: Any) -> None:
    """不支持或损坏的错误报告安全失败，不产生二次异常或猜测式重试。"""

    raw = failed_result()
    raw["retry_report"] = report
    failure = result_failure("failed", raw)
    assert failure is not None and not failure.retryable


def test_review_exception_policy_is_conservative() -> None:
    """未知运行时错误、输入错误和整体超时不重试，网络瞬断例外。"""

    for error in (RuntimeError("synthetic-private"), ValueError("synthetic-private"),
                  TimeoutError(), subprocess.TimeoutExpired(["ocr"], 30),
                  httpx.UnsupportedProtocol("synthetic-private"),
                  httpx.LocalProtocolError("synthetic-private")):
        failure = classify_review_error(error)
        assert not failure.retryable
        assert "synthetic-private" not in str(failure)
    assert classify_review_error(httpx.ConnectError("synthetic-private")).retryable


@pytest.mark.parametrize(("header", "retryable"), [("120", True), ("301", False),
                                                 ("invalid", True)])
def test_retry_after_is_bounded_without_early_retry(header: str, retryable: bool) -> None:
    """超过等待上限时转人工处理，不在服务端要求的等待结束前抢跑。"""

    response = httpx.Response(429, headers={"Retry-After": header},
                              request=httpx.Request("POST", "https://synthetic.invalid/v1"))
    failure = classify_review_error(httpx.HTTPStatusError("synthetic-private", request=
        response.request, response=response))
    assert failure.retryable is retryable
    if header == "120":
        assert retry_delay(1, failure.retry_after) == 120
    assert 20 <= retry_delay(1) <= 25
    assert retry_delay(100) == 300


def test_retry_budget_is_frozen_in_configuration_snapshot() -> None:
    """新策略两次预算，旧快照保持原三次；恢复和人工重试复用相同口径。"""

    assert attempt_limit(json.dumps({"review_policy": REVIEW_POLICY})) == 2
    assert attempt_limit(None) == 3
    assert attempt_limit("{}") == 3
