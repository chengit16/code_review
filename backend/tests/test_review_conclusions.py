"""用临时 SQLite 验证统一只读结论、稳定来源和费用边界，不调用 Git 或真实模型。"""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from ocr_manager.api import create_app
from ocr_manager.config import Settings
from ocr_manager.review_conclusions import attach_conclusions, read_conclusion
from ocr_manager.review_recovery_domain import digest
from ocr_manager.review_recovery_store import claim, enqueue, finish
from ocr_manager.review_results import project_review_result
from ocr_manager.storage import Store
from test_review_recovery import ADMIN, PATHS, child_result, command, make_source


@pytest.fixture
def recovered(client: TestClient, settings: Settings) -> tuple[Store, Settings, dict[str, Any]]:
    """原始 partial 保持不变，生成两个独立候选版本供读取与并发失效验证。"""

    store, enabled, raw = make_source(client, settings)
    enqueue(store, enabled, 1, command())
    task = claim(store)
    assert task and finish(store, task, child_result(raw, partial=True))
    enqueue(store, enabled, 1, command(1))
    task = claim(store)
    assert task and finish(store, task, child_result(raw, paths=PATHS[2:]))
    return store, enabled, raw


def test_versioned_findings_are_stable_and_read_only(
    recovered: tuple[Store, Settings, dict[str, Any]],
) -> None:
    """根发现和各批次发现固定来源；显式版本、原始数据和旧反馈不会互相覆盖。"""

    store, settings, _ = recovered
    with store.connection() as db:
        before = [tuple(row) for row in db.execute("SELECT * FROM review_attempts")]
        before_occurrences = [tuple(row) for row in db.execute(
            "SELECT * FROM review_issue_occurrences ORDER BY id")]
    with TestClient(create_app(settings)) as api:
        url = "/api/jobs/1/conclusion"
        assert api.get(url).status_code == 401
        assert api.get(url + "?source_attempt=1", headers=ADMIN).status_code == 422
        initial = api.get(url + "?revision=0", headers=ADMIN).json()
        assert initial["role"] == "initial" and initial["version"]["revision"] == 0
        assert initial["findings"][0]["finding_id"] == "j1:a1:c0"
        first = api.get(url + "?source_attempt=1&revision=1", headers=ADMIN).json()
        current = api.get(url, headers=ADMIN).json()
        assert current["consumer_integration_ready"] is True
        assert current["version"]["revision"] == 2 and current["role"] == "effective"
        assert current["version"]["terminal_state"] == "complete"
        assert [finding["finding_id"] for finding in current["findings"]] == [
            "j1:a1:c0", "j1:a1:r1:c0", "j1:a1:r2:c0"]
        assert current["findings"][:2] == first["findings"]
        assert first["findings"][1]["origin"] == {
            "kind": "recovery", "source_attempt": 1, "recovery_id": 1, "comment_index": 0}
        assert initial["execution_usage"]["known_tokens"]["total_tokens"] == 6
        assert first["execution_usage"]["known_tokens"]["total_tokens"] == 9
        assert current["execution_usage"]["known_tokens"]["total_tokens"] == 12
        assert current["usage_through_recovery_id"] == 2
        assert current["execution_usage"]["total_attempts"] == 3
        assert current["execution_usage"]["usage_complete"] is True
        assert api.put("/api/jobs/1/feedback/0", headers=ADMIN,
                       json={"verdict": "helpful"}).status_code == 200
        # 新发现只读身份不能误投到旧的根尝试索引接口。
        assert api.put("/api/jobs/1/feedback/1", headers=ADMIN,
                       json={"verdict": "helpful"}).status_code == 409
        detail = api.get("/api/jobs/1", headers=ADMIN).json()
        assert detail["feedback"] == {"0": "helpful"}
        assert detail["status"] == "partial" and len(detail["result"]["comments"]) == 1
    with store.connection() as db:
        assert [tuple(row) for row in db.execute("SELECT * FROM review_attempts")] == before
        assert db.execute("SELECT COUNT(*) FROM notification_deliveries").fetchone()[0] == 1
        assert [tuple(row) for row in db.execute(
            "SELECT * FROM review_issue_occurrences ORDER BY id")] == before_occurrences


def test_list_detail_reports_and_metrics_share_candidate_selection(
    recovered: tuple[Store, Settings, dict[str, Any]],
) -> None:
    """所有只读摘要指向相同根尝试/版本；历史报告不捎带当前候选。"""

    store, settings, _ = recovered
    with TestClient(create_app(settings)) as api:
        detail = api.get("/api/jobs/1", headers=ADMIN).json()
        listing = api.get("/api/task-search", headers=ADMIN).json()["items"][0]
        report = api.get("/api/jobs/1/report", headers=ADMIN).json()
        assert detail["conclusions"] == listing["conclusions"] == report["conclusions"]
        summary = detail["conclusions"]
        assert summary["initial"]["terminal_state"] == "partial"
        assert summary["initial"]["finding_count"] == 1
        assert summary["candidate"]["terminal_state"] == "complete"
        assert summary["candidate"]["revision"] == 2
        assert summary["candidate"]["finding_count"] == 3
        assert "findings" not in summary["candidate"]
        assert "content" not in json.dumps(listing)
        for endpoint in ("/api/overview", "/api/operations"):
            assert api.get(endpoint, headers=ADMIN).json()["conclusion_candidates"] == {
                "complete": 1}
        history = api.get("/api/jobs/1/report?attempt=1", headers=ADMIN).json()
        assert history["conclusions"] is None
        assert len(history["comments"]) == 1
        explicit = api.get("/api/jobs/1/report?attempt=1&recovery_revision=1",
                           headers=ADMIN).json()
        assert explicit["requested_conclusion"]["version"]["revision"] == 1
        assert explicit["requested_conclusion"]["version"]["terminal_state"] == "partial"
        assert len(explicit["comments"]) == 1
        assert api.get("/api/jobs/1/report?recovery_revision=9",
                       headers=ADMIN).status_code == 404
    assert store.retry_job(1) == 1
    with TestClient(create_app(settings)) as api:
        assert api.get("/api/jobs/1", headers=ADMIN).json()["conclusions"]["candidate"] is None
        assert api.get("/api/overview", headers=ADMIN).json()["conclusion_candidates"] == {}
        assert api.get("/api/jobs/1/conclusion", headers=ADMIN).status_code == 409
        old = api.get("/api/jobs/1/conclusion?source_attempt=1&revision=2", headers=ADMIN)
        assert old.status_code == 200 and old.json()["is_current_source"] is False
        assert old.json()["version"]["terminal_state"] == "complete"


@pytest.mark.parametrize("fault", [
    "missing_origin", "negative_index", "bool_index", "unknown_recovery", "future_recovery",
    "source_attempt", "source_comment", "duplicate_origin", "coverage", "state", "source_bool",
    "extra_origin", "parent_batch", "broken_child",
])
def test_corrupt_provenance_never_falls_back_to_false_green(
    recovered: tuple[Store, Settings, dict[str, Any]], fault: str,
) -> None:
    """目标版本不允许借用其他批次、未来批次或损坏的来源映射；显式报冲突不猜测。"""

    store, settings, _ = recovered
    with store.connection() as db:
        row = db.execute("SELECT * FROM review_recovery_aggregates WHERE revision=1").fetchone()
        result, origins = json.loads(row["result_json"]), json.loads(row["origins_json"])
        if fault == "missing_origin":
            origins.pop()
        elif fault == "negative_index":
            origins[1]["comment_index"] = -1
        elif fault == "bool_index":
            origins[1]["comment_index"] = True
        elif fault in {"unknown_recovery", "future_recovery"}:
            origins[1]["recovery_id"] = 999 if fault == "unknown_recovery" else 2
        elif fault == "source_attempt":
            origins[0]["source_attempt"] = 2
        elif fault == "source_bool":
            origins[0]["source_attempt"] = True
        elif fault == "extra_origin":
            origins[0]["also_seen_in"] = [{"recovery_id": 999, "comment_index": 0}]
        elif fault == "parent_batch":
            db.execute("UPDATE review_recoveries SET status='failed' WHERE id=1")
        elif fault == "broken_child":
            db.execute("UPDATE review_recoveries SET result_json='invalid' WHERE id=1")
        elif fault == "source_comment":
            result["comments"][0]["content"] = "伪造根发现"
        elif fault == "duplicate_origin":
            origins[1] = origins[0]
        elif fault == "coverage":
            result["manifest"]["coverage"]["selected"][0]["item_id"] = "changed"
        else:
            result["manifest"]["terminal_state"] = "complete"
        db.execute("""UPDATE review_recovery_aggregates SET result_json=?,origins_json=?
            WHERE revision=1""",
                   (json.dumps(result), json.dumps(origins)))
    with TestClient(create_app(settings)) as api:
        response = api.get("/api/jobs/1/conclusion?revision=1", headers=ADMIN)
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "conclusion_evidence_invalid"


def test_new_attempt_hides_old_candidate_but_explicit_history_is_unchanged(
    recovered: tuple[Store, Settings, dict[str, Any]],
) -> None:
    """全量重审后默认版本属于新根尝试，显式旧版本仍可审计，发现身份不复用。"""

    store, settings, raw = recovered
    with store.connection() as db:
        historical = read_conclusion(db, 1, source_attempt=1, revision=2)
    assert store.retry_job(1) == 1
    job = store.next_job()
    assert job
    with store.connection() as db:
        assert db.execute("SELECT attempts FROM review_jobs WHERE id=1").fetchone()[0] == 2
    store.finish_job(1, "partial", None, raw, None)
    with TestClient(create_app(settings)) as api:
        doc = api.get("/api/jobs/1/conclusion", headers=ADMIN).json()
        assert doc["version"]["source_attempt"] == 2 and doc["version"]["revision"] == 0
        assert doc["findings"][0]["finding_id"] == "j1:a2:c0"
        detail = api.get("/api/jobs/1", headers=ADMIN).json()
        assert detail["conclusions"]["candidate"] is None
        assert detail["conclusions"]["initial"]["source_attempt"] == 2
        old = api.get("/api/jobs/1/conclusion?source_attempt=1&revision=2", headers=ADMIN).json()
        assert old == historical.model_dump() | {"is_current_source": False}


def test_version_report_redacts_known_credentials_without_raw_fields(
    recovered: tuple[Store, Settings, dict[str, Any]],
) -> None:
    """显式补审报告仍使用已有凭据脱敏出口，不导出快照、工件或模型推理。"""

    store, settings, _ = recovered
    with store.connection() as db:
        rows = db.execute("SELECT * FROM review_recovery_aggregates").fetchall()
        # 在临时库中让根与各来源一致携带合成管理口令，验证报告统一脱敏。
        for table in ("review_jobs", "review_attempts", "review_recoveries"):
            for row in db.execute(f"SELECT rowid AS identity,result_json FROM {table}").fetchall():
                if row["result_json"]:
                    result = json.loads(row["result_json"])
                    for item in result["comments"]:
                        item["content"] += settings.admin_token
                    db.execute(f"UPDATE {table} SET result_json=? WHERE rowid=?",
                               (json.dumps(result), row["identity"]))
        for row in rows:
            result = json.loads(row["result_json"])
            for item in result["comments"]:
                item["content"] += settings.admin_token
            db.execute("UPDATE review_recovery_aggregates SET result_json=? WHERE recovery_id=?",
                       (json.dumps(result), row["recovery_id"]))
        # 来源正文改变后同步重建合成冻结快照和摘要；生产不会允许这样修改历史。
        for batch in db.execute("SELECT id,source_result_json FROM review_recoveries").fetchall():
            frozen = json.loads(batch["source_result_json"])
            for item in frozen["comments"]:
                item["content"] += settings.admin_token
            db.execute("UPDATE review_recoveries SET source_result_json=?,source_digest=? "
                       "WHERE id=?", (json.dumps(frozen), digest(frozen), batch["id"]))
    with TestClient(create_app(settings)) as api:
        response = api.get("/api/jobs/1/report?recovery_revision=2", headers=ADMIN)
        assert response.status_code == 200
        assert settings.admin_token not in response.text and "[REDACTED]" in response.text
        document = response.json()["requested_conclusion"]
        assert document["findings"][2]["finding_id"] == "j1:a1:r2:c0"
        assert "config_snapshot" not in document and "result_path" not in document


def test_repeated_findings_retain_primary_identity_and_verified_extra_origin(
    client: TestClient, settings: Settings,
) -> None:
    """精确重复发现只添加来源，根身份不变，未来反馈无需按聚合下标迁移。"""

    store, enabled, raw = make_source(client, settings)
    raw["comments"][0]["path"] = PATHS[1]
    projected = json.dumps(project_review_result(raw))
    with store.connection() as db:
        db.execute("UPDATE review_jobs SET result_json=? WHERE id=1", (projected,))
        db.execute("UPDATE review_attempts SET result_json=? WHERE job_id=1", (projected,))
    enqueue(store, enabled, 1, command())
    task = claim(store)
    child = child_result(raw)
    child["comments"] = list(raw["comments"])
    assert task and finish(store, task, child)
    with store.connection() as db:
        document = read_conclusion(db, 1)
    assert len(document.findings) == 1 and document.findings[0].finding_id == "j1:a1:c0"
    assert document.findings[0].also_seen_in[0].recovery_id == task["id"]
    assert document.findings[0].also_seen_in[0].comment_index == 0


def test_failed_batch_unknown_usage_is_included_but_later_cost_is_not(
    client: TestClient, settings: Settings,
) -> None:
    """费用按版本截止，失败批次未知用量不补零，后续批次不会改变旧版本的累计。"""

    store, enabled, raw = make_source(client, settings)
    revision = 0
    for failed in (True, False, True):
        enqueue(store, enabled, 1, command(revision))
        task = claim(store)
        assert task
        assert finish(store, task, None if failed else child_result(raw, partial=True),
                      error_code="synthetic" if failed else None)
        if not failed:
            revision += 1
            with store.connection() as db:
                earlier = read_conclusion(db, 1).model_dump()
    with store.connection() as db:
        current = read_conclusion(db, 1).model_dump()
    assert current == earlier
    usage = current["execution_usage"]
    assert usage["total_attempts"] == 3 and usage["known_usage_attempts"] == 2
    assert usage["known_tokens"]["total_tokens"] == 9 and usage["usage_complete"] is False
    assert current["usage_through_recovery_id"] == 2


def test_summary_queries_are_batched_and_do_not_return_full_result(
    recovered: tuple[Store, Settings, dict[str, Any]],
) -> None:
    """重复列表输入也只需一批两个摘要查询，不按行读取完整 JSON/发现或访问工件。"""

    store, _, _ = recovered
    queries: list[str] = []
    with store.connection() as db:
        db.set_trace_callback(queries.append)
        jobs = [{"id": 1} for _ in range(100)]
        attach_conclusions(db, jobs)
    assert len(queries) == 2
    assert all(job["conclusions"]["candidate"]["revision"] == 2 for job in jobs)
    assert "content" not in json.dumps(jobs) and "result_json" not in json.dumps(jobs)


def test_invalid_versions_permissions_and_deleted_job(
    recovered: tuple[Store, Settings, dict[str, Any]],
) -> None:
    """版本参数不接受负数，缺失版本/源尝试与删除后的任务不能暴露遗留结果。"""

    store, settings, _ = recovered
    with TestClient(create_app(settings)) as api:
        url = "/api/jobs/1/conclusion"
        for query in ("?revision=-1", "?source_attempt=0", "?revision=invalid"):
            assert api.get(url + query, headers=ADMIN).status_code == 422
        assert api.get(url + "?revision=99", headers=ADMIN).status_code == 404
        assert api.get(url + "?source_attempt=99&revision=1", headers=ADMIN).status_code == 409
        assert api.get("/api/jobs/999/conclusion", headers=ADMIN).status_code == 404
        assert store.delete_repository(1)
        assert api.get(url, headers=ADMIN).status_code == 404


def test_initial_budget_conflict_uses_validated_attempt_status(
    client: TestClient, settings: Settings,
) -> None:
    """OCR 写 complete 但预算不确定时，读取统一使用平台已验证的 partial，不恢复绿色结论。"""

    store, enabled, raw = make_source(client, settings)
    raw["manifest"]["terminal_state"] = "complete"
    coverage = raw["manifest"]["coverage"]
    coverage["completed"] = coverage["selected"]
    coverage["failed"] = []
    raw["summary"]["budget_exceeded"] = True
    result = json.dumps(project_review_result(raw))
    with store.connection() as db:
        db.execute("UPDATE review_jobs SET result_json=? WHERE id=1", (result,))
        db.execute("UPDATE review_attempts SET result_json=? WHERE job_id=1", (result,))
    with TestClient(create_app(enabled)) as api:
        doc = api.get("/api/jobs/1/conclusion", headers=ADMIN)
        assert doc.status_code == 200
        assert doc.headers["Cache-Control"] == "no-store"
        assert doc.json()["version"]["terminal_state"] == "partial"
        summary = api.get("/api/task-search", headers=ADMIN).json()["items"][0]["conclusions"]
        assert summary["initial"]["terminal_state"] == "partial"
        assert summary["candidate"] is None
