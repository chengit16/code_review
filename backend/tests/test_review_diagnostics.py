"""以合成结果验证分层证据、安全边界及持久化，不复制业务工件、不访问供应商。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from ocr_manager.config import Settings
from ocr_manager.review_diagnostic_report import diagnostic_report
from ocr_manager.review_diagnostics import failure_analysis
from ocr_manager.review_failures import result_failure
from ocr_manager.review_results import project_review_result
from test_task_operations import populate


def diagnostic_result() -> dict[str, Any]:
    """合成两个分组，一个完成、一个失败；含不允许持久化的敏感标记。"""

    done = {"path": "done.py", "item_id": "one"}
    failed = {"path": "comma,name.py", "item_id": "two", "classification": "timeout"}
    return {"comments": [], "manifest": {"terminal_state": "partial", "coverage": {
        "selected": [done, failed], "completed": [done], "reused": [],
        "failed": [failed], "waived": []}},
        "groups": [{"files": ["done.py"]}, {"files": ["comma,name.py"]}],
        "retry_report": {"schema_version": "ocr.llm-retry-report/v1", "requests": [{
            "outcome": "failed", "file_path": "comma,name.py", "task_type": "plan_task",
            "logical_request_id": "a" * 64,
            "request_no": 1, "message": "synthetic-private", "attempts": [
                {"status_code": 504, "error_class": "timeout", "failure_phase": "http",
                 "duration_to_headers_ms": 60001, "response": "synthetic-private"},
                {"error_class": "timeout", "failure_phase": "context",
                 "duration_to_headers_ms": 20, "observed_backoff_ms": 400}]}]},
        "tool_calls": {"failure_details": [
            {"tool_name": "code_search", "arguments": "synthetic-private",
             "error": "match limit exceeded synthetic-private"},
            {"tool_name": "file_read",
             "error": "node_modules/example not found synthetic-private"}]}}


def test_partial_analysis_is_safe_and_does_not_schedule_retry() -> None:
    """不同层级信号共存，不把 504 误当作全部文件失败的唯一原因。"""

    raw = diagnostic_result()
    projected = project_review_result(raw)
    analysis = projected["failure_analysis"]
    assert analysis["summary"] == "完成 1/2 个文件；1 个失败分组；模型请求存在 HTTP 504"
    request = analysis["requests"][0]
    assert request["group_id"] == "group-2"
    assert request["logical_request_id"] == "a" * 64
    assert request["duration_to_headers_ms"] == [60001, 20]
    assert request["observed_backoff_ms"] == [400]
    assert {signal["code"] for signal in analysis["signals"]} == {
        "coverage_timeout", "http_504", "context_timeout", "search_limit", "missing_dependency"}
    assert projected["diagnostic"] is None and result_failure("partial", raw) is None
    assert "synthetic-private" not in json.dumps(projected)
    assert raw["retry_report"]["requests"][0]["message"] == "synthetic-private"


def test_ambiguous_comma_join_is_not_guessed() -> None:
    """两个路径序列可拼成同一逗号串时，请求关联未知而非拆字符串猜测。"""

    raw = diagnostic_result()
    paths = ["a,b", "c", "a", "b,c"]
    items = [{"path": path, "classification": "timeout"} for path in paths]
    raw["manifest"]["coverage"].update(selected=items, completed=[], failed=items)
    raw["groups"] = [{"files": paths[:2]}, {"files": paths[2:]}]
    raw["retry_report"]["requests"][0]["file_path"] = "a,b,c"
    analysis = failure_analysis(raw)
    assert analysis is not None
    assert analysis["requests"][0]["group_id"] is None
    assert analysis["failed_group_count"] == 2


@pytest.mark.parametrize(("report", "state"), [
    (None, "missing"), ([], "malformed"), ({"schema_version": "future"}, "unsupported"),
    ({"schema_version": "ocr.llm-retry-report/v1", "requests": [None]}, "malformed"),
    ({"schema_version": "ocr.llm-retry-report/v1", "requests": [
        {"outcome": "failed", "attempts": [None]}]}, "malformed"),
    ({"schema_version": "ocr.llm-retry-report/v1", "requests": [{}] * 1001}, "limited"),
])
def test_bad_reports_are_explicitly_incomplete(report: Any, state: str) -> None:
    """损坏、未来版本和过大报告均不抛异常或泄露自由文本。"""

    raw = diagnostic_result()
    raw["retry_report"] = report
    analysis = failure_analysis(raw)
    assert analysis is not None and analysis["report_state"] == state
    assert not analysis["requests"]
    assert "http_504" not in {signal["code"] for signal in analysis["signals"]}


def test_malformed_tail_discards_partial_request_signals() -> None:
    """报告尾部损坏时，不展示一半请求造成已完整解析的错觉。"""

    raw = diagnostic_result()
    raw["retry_report"]["requests"].append(None)
    analysis = failure_analysis(raw)
    assert analysis is not None and analysis["report_state"] == "malformed"
    assert not analysis["requests"]
    assert all(signal["code"] != "http_504" for signal in analysis["signals"])


def test_truncation_preserves_counts_and_rejects_bad_group_membership() -> None:
    """展示有界，未知分组不返回未经覆盖验证的路径。"""

    raw = diagnostic_result()
    raw["retry_report"]["requests"] *= 51
    raw["groups"][1]["files"].append("synthetic-private")
    analysis = failure_analysis(raw)
    assert analysis is not None and analysis["report_state"] == "limited"
    assert len(analysis["requests"]) == 50
    assert analysis["failed_group_count"] is None and not analysis["groups"]
    assert "synthetic-private" not in json.dumps(analysis)
    assert next(x["count"] for x in analysis["signals"] if x["code"] == "http_504") == 51


def test_unknown_fields_and_invalid_numeric_types_are_not_echoed() -> None:
    """布尔值不当作毫秒，外部枚举只接受允许字段。"""

    raw = diagnostic_result()
    request = raw["retry_report"]["requests"][0]
    request.update(task_type=["bad"], request_no=True, logical_request_id="synthetic-private")
    request["attempts"] = [{"error_class": {"bad": "synthetic-private"},
                            "failure_phase": "synthetic-private",
                            "status_code": True, "duration_to_headers_ms": -1}]
    analysis = failure_analysis(raw)
    assert analysis is not None
    evidence = analysis["requests"][0]
    assert evidence["request_no"] is None and evidence["task_type"] == "unknown"
    assert evidence["error_classes"] == evidence["duration_to_headers_ms"] == []
    assert "synthetic-private" not in json.dumps(analysis)


def test_coverage_budget_and_missing_groups_do_not_become_network_fault() -> None:
    """预算与超时保持不同类别，无有效覆盖结构时不伪造分析。"""

    raw = diagnostic_result()
    raw["manifest"]["coverage"]["failed"][0]["classification"] = "budget"
    raw.pop("groups")
    raw.pop("retry_report")
    analysis = failure_analysis(raw)
    assert analysis is not None and analysis["failed_group_count"] is None
    assert any(x["code"] == "coverage_budget" for x in analysis["signals"])
    raw["manifest"]["coverage"]["failed"] = "bad"
    assert failure_analysis(raw) is None


def test_diagnostics_survive_database_history_and_report_without_list_details(
    client: TestClient, settings: Settings,
) -> None:
    """同一安全证据进入详情/历史导出；列表仅返回摘要，不读取文件或回填旧数据。"""

    store, _ = populate(client, settings, 1)
    job = store.next_job()
    assert job is not None
    store.finish_job(job["id"], "partial", None, diagnostic_result(), None)
    headers = {"X-Admin-Token": settings.admin_token}
    assert client.get("/api/jobs/1").status_code == 401
    detail = client.get("/api/jobs/1", headers=headers).json()
    assert detail["failure_analysis"]["failed_group_count"] == 1
    assert "HTTP 504" in detail["failure_summary"]
    listing = client.get("/api/task-search", headers=headers).json()["items"][0]
    assert listing["failure_summary"] == detail["failure_summary"]
    assert listing["failure_analysis"] is None
    report = client.get("/api/jobs/1/report", headers=headers).json()
    assert report["failure_analysis"] == detail["failure_analysis"]
    with store.connection() as db:
        history = json.loads(db.execute("SELECT result_json FROM review_attempts WHERE job_id=1")
                             .fetchone()[0])
    assert history["failure_analysis"] == detail["failure_analysis"]
    assert "synthetic-private" not in json.dumps(detail)
    store.retry_job(job["id"])
    assert store.next_job() is not None
    store.finish_job(job["id"], "failed", None, None, "合成失败")
    old_report = client.get("/api/jobs/1/report?attempt=1", headers=headers).json()
    assert old_report["failure_analysis"] == detail["failure_analysis"]
    assert client.get("/api/jobs/1/report", headers=headers).json()["failure_analysis"] is None


def test_read_only_report_checks_input_and_preserves_artifact(tmp_path: Path) -> None:
    """只读诊断拒绝输入漂移，不因缺失版本或损坏工件输出原文。"""

    result = diagnostic_result()
    result["manifest"].update(schema_version="ocr.run-manifest/v1",
                              input={"mode": "commit", "resolved_head": "a" * 40})
    path = tmp_path / "result.json"
    content = json.dumps(result).encode()
    path.write_bytes(content)
    report = diagnostic_report(path, "a" * 40)
    assert report["state"] == "partial" and report["business_data_modified"] is False
    assert "synthetic-private" not in json.dumps(report)
    assert path.read_bytes() == content
    for head in ("b" * 40, ""):
        with pytest.raises(ValueError, match="固定输入不匹配"):
            diagnostic_report(path, head)
    path.write_text("synthetic-private invalid")
    with pytest.raises(ValueError, match="格式无效"):
        diagnostic_report(path, "a" * 40)
