"""验证排队、累计耗时、历史费用和范围证据；只使用合成时间与临时 SQLite。"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from ocr_manager import storage
from ocr_manager.attempt_history import attempt_job
from ocr_manager.config import Settings
from ocr_manager.review_metrics import performance_metrics
from ocr_manager.review_observability import execution_summary, reason_code, usage_summary
from ocr_manager.tasks import set_job_stage
from schema_fixtures import remove_observability_schema
from test_task_operations import populate


def test_three_hour_attempts_and_six_hour_queue_are_separate() -> None:
    """三次各一小时不能显示为累计一小时，排队也不能算执行时间。"""

    job = {"attempts": 3, "status": "failed", "created_at": "2026-01-01 00:00:00",
           "started_at": "2026-01-01 10:00:00", "finished_at": "2026-01-01 11:00:00"}
    attempts = [{"attempt_number": number, "started_at": f"2026-01-01 {start:02}:00:00",
                 "finished_at": f"2026-01-01 {start+1:02}:00:00"}
                for number, start in enumerate((6, 8, 10), 1)]
    timing = execution_summary(job, attempts)
    assert timing["first_queue_seconds"] == 21600
    assert timing["latest_execution_seconds"] == 3600
    assert timing["cumulative_execution_seconds"] == 10800
    assert timing["total_elapsed_seconds"] == 39600
    assert timing["execution_complete"] and timing["retry_backoff_seconds"] is None
    skipped = job | {"attempts": 1, "status": "skipped", "finished_at": "2026-01-01 06:00:01"}
    assert execution_summary(skipped, [attempts[0] | {
        "finished_at": "2026-01-01 06:00:01"}])["cumulative_execution_seconds"] == 1


def test_running_backoff_and_ready_wait_do_not_double_count() -> None:
    """已结束尝试和当前尝试各计一次，退避与就绪后等待不重叠。"""

    attempt = {"attempt_number": 1, "started_at": "2026-01-01 06:00:00",
               "finished_at": "2026-01-01 07:00:00", "retry_ready_at": "2026-01-01 07:00:20"}
    job = {"status": "running", "attempts": 2, "created_at": "2026-01-01 00:00:00",
           "started_at": "2026-01-01 08:00:00", "finished_at": None}
    timing = execution_summary(job, [attempt], datetime(2026, 1, 1, 8, 10, tzinfo=UTC))
    assert timing["cumulative_execution_seconds"] == 4200
    assert timing["latest_execution_seconds"] == 600
    assert timing["retry_backoff_seconds"] == 20
    assert timing["retry_ready_wait_seconds"] == 3580
    queued = job | {"status": "queued", "attempts": 1}
    timing = execution_summary(queued, [attempt], datetime(2026, 1, 1, 7, 0, 10, tzinfo=UTC))
    assert timing["latest_execution_seconds"] == 3600
    assert timing["cumulative_execution_seconds"] == 3600
    assert timing["retry_backoff_seconds"] == 10
    assert timing["retry_ready_wait_seconds"] == 0


def test_missing_and_invalid_history_remains_unknown() -> None:
    """缺失开始时间、编号空洞或负区间不能用总历时填补累计执行。"""

    job = {"status": "failed", "attempts": 2, "created_at": "2026-01-01 00:00:00",
           "finished_at": "2026-01-01 08:00:00"}
    timing = execution_summary(job, [{"attempt_number": 2, "finished_at": job["finished_at"]}])
    assert timing["cumulative_execution_seconds"] is None
    assert timing["latest_execution_seconds"] is None
    assert timing["first_queue_seconds"] is None and not timing["execution_complete"]
    timing = execution_summary(job, [{"attempt_number": 1, "started_at": "invalid"}])
    assert timing["cumulative_execution_seconds"] is None


def test_usage_uses_each_attempt_price_and_discloses_unknowns() -> None:
    """历史费用逐次计算且不同币种分列；无最终 JSON 的超时不能当成零费用。"""

    def attempt(rate: str, currency: str = "CNY") -> dict[str, Any]:
        return {"status": "failed", "result_json": json.dumps({"usage": {
            "input_tokens": 1000000, "output_tokens": 0}}),
            "config_snapshot": json.dumps({"pricing": {"price_currency": currency,
                "input_price_per_million": rate, "output_price_per_million": "0"}})}

    result = usage_summary({"attempts": 3}, [attempt("2"), attempt("4"), {"status": "failed"}])
    assert result["known_costs"] == [{"currency": "CNY", "total": "6"}]
    assert not result["usage_complete"] and not result["cost_complete"]
    assert result["known_tokens"]["total_tokens"] == 2000000
    assert len(usage_summary({"attempts": 2}, [attempt("2"), attempt("4", "USD")])[
        "known_costs"]) == 2
    partial = usage_summary({"attempts": 1}, [{"status": "failed", "result_json": json.dumps({
        "usage": {"total_tokens": 99}})}])
    assert partial["known_tokens"] == {"total_tokens": 99} and not partial["usage_complete"]


def test_recovery_time_does_not_count_downtime_as_execution() -> None:
    """恢复时写入的结束时间只用于审计，实际进程结束未知时不累计停机间隔。"""

    job = {"status": "cancelled", "attempts": 1, "created_at": "2026-01-01 00:00:00",
           "finished_at": "2026-01-02 00:00:00"}
    attempt = {"attempt_number": 1, "started_at": "2026-01-01 06:00:00",
               "finished_at": job["finished_at"], "reason_code": "interrupted_cancelled"}
    timing = execution_summary(job, [attempt])
    assert timing["latest_execution_seconds"] is None
    assert timing["cumulative_execution_seconds"] is None
    assert not timing["execution_complete"]
    assert timing["total_elapsed_seconds"] == 86400


def test_reasons_never_call_skipped_or_cancelled_success() -> None:
    """空差异、规则排除与取消有稳定原因码，不推断纯换行已被过滤。"""

    assert reason_code("skipped", {"preview": {"files": []}}, None) == "empty_diff"
    assert reason_code("skipped", {"preview": {"files": [{"path": ".vscode/settings.json"}]}},
                       None) == "excluded_by_rules"
    assert reason_code("skipped", None, None) == "skipped_unknown"
    assert reason_code("cancelled", None, None) == "cancelled"
    assert reason_code("failed", None, "[scope_limit] 超限") == "scope_limit"


def test_attempt_evidence_survives_retry_and_report_is_historical(
    client: TestClient, settings: Settings,
) -> None:
    """数据库保存范围、阶段和调度；成功后取消不覆盖原报告的状态与费用。"""

    store, _ = populate(client, settings, 1)
    job = store.next_job()
    assert job is not None
    set_job_stage(store, job["id"], "git")
    set_job_stage(store, job["id"], "preview")
    with store.connection() as db:
        db.execute("UPDATE review_jobs SET scope_json=? WHERE id=?", (json.dumps({
            "original_count": 20, "newline_only_count": 19, "filter_enabled": False}), job["id"]))
    store.finish_job(job["id"], "complete", None, {"comments": []}, None)
    assert store.retry_job(job["id"]) == job["id"]
    assert store.next_job() is not None
    store.finish_job(job["id"], "cancelled", None, None, "用户停止")
    detail = store.get_job(job["id"])
    assert detail is not None
    assert detail["reason"]["code"] == "cancelled"
    historical = attempt_job(detail, 1)
    assert historical["status"] == "complete"
    assert historical["scope_analysis"]["original_count"] == 20
    assert historical["cumulative_usage"]["total_attempts"] == 1
    assert all(stage["attempt_number"] == 1 and stage["finished_at"]
               for stage in historical["stage_timings"])
    listed = client.get("/api/task-search", headers={"X-Admin-Token": settings.admin_token}).json()
    assert listed["items"][0]["timing"]["total_attempts"] == 2
    assert listed["items"][0]["reason"]["code"] == "cancelled"


def test_retry_schedule_is_persisted_and_cancellation_recovery_keeps_attempt(
    client: TestClient, settings: Settings,
) -> None:
    """重试调度是逐次事实，重启时取消也留下最后尝试而非只改任务状态。"""

    store, _ = populate(client, settings, 1)
    job = store.next_job()
    assert job is not None
    store.defer_job(job["id"], "[network] 暂时故障", delay_seconds=25)
    detail = store.get_job(job["id"])
    assert detail and detail["attempt_history"][0]["retry_ready_at"]
    assert detail["attempt_history"][0]["scheduled_at"]
    with store.connection() as db:
        db.execute("UPDATE review_jobs SET next_run_at=CURRENT_TIMESTAMP WHERE id=?", (job["id"],))
    assert store.next_job()
    with store.connection() as db:
        db.execute("UPDATE review_jobs SET cancel_requested=1 WHERE id=?", (job["id"],))
    store.recover()
    store.recover()
    detail = store.get_job(job["id"])
    assert detail and len(detail["attempt_history"]) == 2
    assert detail["attempt_history"][0]["status"] == "cancelled"
    assert not detail["timing"]["execution_complete"]


def test_35_to_36_preserves_unknowns_and_rolls_back_on_failure(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """旧记录不伪造调度证据；迁移失败连同 DDL 一起回滚。"""

    store, _ = populate(client, settings, 1)
    with store.connection() as db:
        remove_observability_schema(db)
        db.execute("PRAGMA user_version=35")
    with monkeypatch.context() as patch:
        patch.setattr(storage, "OBSERVABILITY_MIGRATION", storage.OBSERVABILITY_MIGRATION +
                      "CREATE TABLE broken (id); CREATE TABLE broken (id);")
        with pytest.raises(sqlite3.OperationalError):
            store.migrate()
    with store.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 35
        columns = {row["name"] for row in db.execute("PRAGMA table_info(review_jobs)")}
        assert "scope_json" not in columns
    store.migrate()
    with store.connection() as db:
        row = db.execute("SELECT * FROM review_jobs").fetchone()
        assert row["scope_json"] is None and row["attempt_ready_at"] is None


def test_metrics_exclude_skipped_from_success_execution(
    client: TestClient, settings: Settings,
) -> None:
    """运维分组保留状态和规模，跳过不混入成功执行的分位数样本。"""

    store, _ = populate(client, settings, 1)
    job = store.next_job()
    assert job is not None
    store.finish_job(job["id"], "skipped", None, {"comments": [], "preview": {"files": []}}, None)
    with store.connection() as db:
        groups = performance_metrics(db)
    assert len(groups) == 1 and groups[0]["status"] == "skipped"
    assert groups[0]["execution_samples"] == 0
    assert groups[0]["execution_p95_seconds"] is None
