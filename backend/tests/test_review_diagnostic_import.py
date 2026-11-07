"""合成工件验证全量历史导入、来源绑定、并发与幂等；禁止使用真实业务工件或调用外部模型。"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from ocr_manager.artifact_lock import artifact_lock
from ocr_manager.config import Settings
from ocr_manager.review_diagnostic_import import import_diagnostics
from ocr_manager.review_recovery_store import claim, enqueue, finish
from ocr_manager.storage import Store
from test_review_recovery import ADMIN, child_result, command, make_source


def historic(client: TestClient, settings: Settings) -> tuple[Store, Path, dict[str, Any]]:
    """构造已保存原始工件但没有新版诊断的尝试，保持当前任务与尝试完全相同。"""

    store, _, raw = make_source(client, settings)
    raw["groups"] = [{"files": [item["path"] for item in raw["manifest"]["coverage"]["selected"]]}]
    raw["retry_report"] = {"schema_version": "ocr.llm-retry-report/v1", "requests": [{
        "outcome": "failed", "task_type": "plan_task", "file_path": ",".join(
            raw["groups"][0]["files"]), "attempts": [{"status_code": 504,
            "error_class": "timeout", "failure_phase": "http", "duration_to_headers_ms": 60001,
            "response": "synthetic-private-response"}]}]}
    with store.connection() as db:
        row = db.execute("SELECT * FROM review_jobs WHERE id=1").fetchone()
        path = Path(row["result_path"])
        result = json.loads(row["result_json"])
        result.pop("failure_analysis", None)
        encoded = json.dumps(result)
        db.execute("UPDATE review_jobs SET result_json=? WHERE id=1", (encoded,))
        db.execute("UPDATE review_attempts SET result_json=? WHERE job_id=1", (encoded,))
    path.write_text(json.dumps(raw))
    return store, path, raw


def facts(store: Store) -> list[list[tuple[Any, ...]]]:
    """比较任务、尝试、投递与补审原事实，排除独立导入表和新增审计记录。"""

    with store.connection() as db:
        return [[tuple(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY 1")]
                for table in ("review_jobs", "review_attempts", "notification_deliveries",
                              "review_recoveries", "review_recovery_aggregates",
                              "review_effective_conclusions", "review_recovery_deliveries")]


def test_preview_import_idempotency_and_all_read_surfaces(
    client: TestClient, settings: Settings,
) -> None:
    """预览不写业务表；导入只新增诊断与审计，详情/列表/当前及单次报告读同一证据。"""

    store, path, _ = historic(client, settings)
    before, artifact = facts(store), path.read_bytes()
    assert import_diagnostics(settings.data_dir)["counts"] == {"ready": 1}
    with store.connection() as db:
        assert db.execute("SELECT count(*) FROM review_historical_diagnostics").fetchone()[0] == 0
    assert import_diagnostics(settings.data_dir, apply=True)["counts"] == {"imported": 1}
    assert import_diagnostics(settings.data_dir, apply=True)["counts"] == {"already_imported": 1}
    assert facts(store) == before and path.read_bytes() == artifact
    with store.connection() as db:
        assert db.execute("SELECT count(*) FROM audit_log WHERE "
                          "action='historical_diagnostic_import'").fetchone()[0] == 1
    detail = client.get("/api/jobs/1", headers=ADMIN).json()
    assert detail["failure_analysis_imported_at"]
    assert "504" in detail["failure_summary"]
    assert detail["failure_analysis"]["requests"][0]["duration_to_headers_ms"] == [60001]
    listing = client.get("/api/task-search", headers=ADMIN).json()["items"][0]
    assert listing["failure_summary"] == detail["failure_summary"]
    assert listing["failure_analysis"] is None
    for suffix in ("", "?attempt=1"):
        report = client.get("/api/jobs/1/report" + suffix, headers=ADMIN).json()
        assert report["failure_analysis"] == detail["failure_analysis"]
        assert "synthetic-private-response" not in json.dumps(report)
    assert "synthetic-private-response" not in json.dumps(detail)


@pytest.mark.parametrize("fault,reason", [
    ("missing", "artifact_missing"), ("outside", "artifact_path_invalid"),
    ("symlink", "artifact_path_invalid"), ("directory_symlink", "artifact_path_invalid"),
    ("bad_json", "artifact_invalid"),
    ("oversize", "artifact_too_large"), ("sha", "artifact_invalid"),
    ("findings", "source_result_mismatch"), ("coverage", "source_result_mismatch"),
])
def test_import_rejects_untrusted_artifacts(
    client: TestClient, settings: Settings, tmp_path: Path, fault: str, reason: str,
) -> None:
    """越界、链接、超限与覆盖/发现/SHA 漂移不写任何诊断，不输出私有异常正文。"""

    store, path, raw = historic(client, settings)
    if fault == "missing":
        path.unlink()
    elif fault == "directory_symlink":
        original = path.parent.with_name("original")
        path.parent.rename(original)
        path.parent.symlink_to(original, target_is_directory=True)
    elif fault in {"outside", "symlink"}:
        outside = tmp_path / "outside" / "result.json"
        outside.parent.mkdir()
        outside.write_bytes(path.read_bytes())
        if fault == "symlink":
            path.unlink()
            path.symlink_to(outside)
        else:
            with store.connection() as db:
                db.execute("UPDATE review_attempts SET result_path=?", (str(outside),))
    elif fault == "bad_json":
        path.write_text("synthetic-private invalid")
    elif fault == "oversize":
        path.write_bytes(b"x" * (16 * 1024 * 1024 + 1))
    else:
        if fault == "sha":
            raw["manifest"]["input"]["resolved_head"] = "f" * 40
        elif fault == "findings":
            raw["comments"] = []
        else:
            raw["manifest"]["coverage"]["failed"][0]["classification"] = "budget"
        path.write_text(json.dumps(raw))
    before = facts(store)
    report = import_diagnostics(settings.data_dir, apply=True)
    assert report["counts"] == {reason: 1}
    assert "synthetic-private" not in json.dumps(report)
    assert facts(store) == before
    with store.connection() as db:
        assert db.execute("SELECT count(*) FROM review_historical_diagnostics").fetchone()[0] == 0


def test_native_evidence_and_artifact_lock_are_respected(
    client: TestClient, settings: Settings,
) -> None:
    """新任务已有诊断不覆盖；清理/执行占锁期间不读取工件。"""

    store, _, _ = make_source(client, settings)
    assert import_diagnostics(settings.data_dir, apply=True)["counts"] == {
        "native_diagnostic_present": 1}
    with artifact_lock(settings.data_dir, 1) as acquired:
        assert acquired
        assert import_diagnostics(settings.data_dir, apply=True)["counts"] == {"artifacts_busy": 1}


def test_current_job_without_attempt_row_can_be_imported(
    client: TestClient, settings: Settings,
) -> None:
    """旧库缺少尝试行但当前结果仍可信时单独绑定当前源，不伪造历史尝试。"""

    store, _, _ = historic(client, settings)
    with store.connection() as db:
        db.execute("DELETE FROM review_attempts WHERE job_id=1")
    assert import_diagnostics(settings.data_dir, apply=True)["counts"] == {"imported": 1}
    detail = client.get("/api/jobs/1", headers=ADMIN).json()
    assert detail["failure_analysis_imported_at"] and not detail["attempt_history"]
    assert "504" in detail["failure_summary"]


def test_old_attempt_diagnostic_does_not_leak_into_new_attempt(
    client: TestClient, settings: Settings,
) -> None:
    """旧尝试可独立导入和导出，新一次评审不能继承旧 504 或导入时间。"""

    store, _, raw = historic(client, settings)
    assert store.retry_job(1)
    assert store.next_job()
    raw.pop("retry_report")
    store.finish_job(1, "partial", None, raw, None)
    assert import_diagnostics(settings.data_dir, apply=True)["counts"] == {
        "imported": 1, "native_diagnostic_present": 1}
    detail = client.get("/api/jobs/1", headers=ADMIN).json()
    assert detail["failure_analysis_imported_at"] is None
    assert "504" not in detail["failure_analysis"]["summary"]
    assert "504" in client.get("/api/jobs/1/report?attempt=1", headers=ADMIN).json()[
        "failure_analysis"]["summary"]


def test_import_leaves_recovery_source_chain_and_effective_pointer_intact(
    client: TestClient, settings: Settings,
) -> None:
    """补审执行/聚合之后仍可导入旧诊断，不能使有效结论失效或改变来源摘要。"""

    store, _, raw = historic(client, settings)
    enqueue(store, settings, 1, command())
    task = claim(store)
    assert task and finish(store, task, child_result(raw))
    before = facts(store)
    assert import_diagnostics(settings.data_dir, apply=True)["counts"] == {"imported": 1}
    assert facts(store) == before
    detail = client.get("/api/jobs/1", headers=ADMIN).json()
    assert detail["effective_status"] == "complete"
    assert "504" in detail["failure_analysis"]["summary"]


def test_source_change_hides_import_and_commit_failure_rolls_back(
    client: TestClient, settings: Settings,
) -> None:
    """审计失败与诊断一起回滚；随后原证据改变，读取不再沿用独立导入记录。"""

    store, _, _ = historic(client, settings)
    with store.connection() as db:
        db.execute("""CREATE TRIGGER reject_import BEFORE INSERT ON audit_log
            WHEN NEW.action='historical_diagnostic_import'
            BEGIN SELECT RAISE(ABORT,'synthetic rejection'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        import_diagnostics(settings.data_dir, apply=True)
    with store.connection() as db:
        assert db.execute("SELECT count(*) FROM review_historical_diagnostics").fetchone()[0] == 0
        db.execute("DROP TRIGGER reject_import")
    import_diagnostics(settings.data_dir, apply=True)
    with store.connection() as db:
        db.execute("UPDATE review_attempts SET result_json='{}' WHERE job_id=1")
    detail = client.get("/api/jobs/1", headers=ADMIN).json()
    assert detail["failure_analysis"] is None and detail["failure_analysis_imported_at"] is None


def test_source_change_between_preview_and_commit_is_rejected(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """解析完之后的源变更必须在提交时再次发现，不能把旧分析绑定到新结果。"""

    from ocr_manager import review_diagnostic_import as importer

    store, _, _ = historic(client, settings)
    original = importer._analysis

    def changed(data_dir: Path, candidate: dict[str, Any]) -> tuple[str, str]:
        result = original(data_dir, candidate)
        with store.connection() as db:
            db.execute("UPDATE review_attempts SET result_json='{}' WHERE job_id=1")
        return result

    monkeypatch.setattr(importer, "_analysis", changed)
    assert import_diagnostics(settings.data_dir, apply=True)["counts"] == {"source_changed": 1}


def test_batch_import_covers_multiple_jobs_and_keeps_missing_evidence_unknown(
    client: TestClient, settings: Settings,
) -> None:
    """不固定单个任务编号；整批导入可信工件，缺证据任务保留具体跳过原因。"""

    store, _, raw = historic(client, settings)
    with store.connection() as db:
        repository = db.execute("SELECT repository_id FROM review_jobs WHERE id=1").fetchone()[0]
    for number in (2, 3):
        store.add_event(repository, number, None, None, None)
        event = store.next_event()
        assert event
        sha = f"{number:040x}"
        store.finish_event(event["id"], [sha], {sha: ("snapshot", "")}, None)
        job = store.next_job()
        assert job
        local = json.loads(json.dumps(raw))
        local["manifest"]["input"]["resolved_head"] = sha
        path = settings.data_dir / "runs" / str(job["id"]) / "result.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(local))
        store.finish_job(job["id"], "partial", str(path), local, None)
        with store.connection() as db:
            value = json.loads(db.execute("SELECT result_json FROM review_jobs WHERE id=?",
                                         (job["id"],)).fetchone()[0])
            value.pop("failure_analysis")
            encoded = json.dumps(value)
            db.execute("UPDATE review_jobs SET result_json=? WHERE id=?", (encoded, job["id"]))
            db.execute("UPDATE review_attempts SET result_json=? WHERE job_id=?",
                       (encoded, job["id"]))
        if number == 3:
            path.unlink()
    assert import_diagnostics(settings.data_dir, apply=True)["counts"] == {
        "imported": 2, "artifact_missing": 1}
    for number in (1, 2):
        assert client.get(f"/api/jobs/{number}", headers=ADMIN).json()["failure_analysis"]
    assert client.get("/api/jobs/3", headers=ADMIN).json()["failure_analysis"] is None


def test_46_migration_is_atomic_idempotent_and_does_not_import(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """只新增结构；故障回滚到 45，重复迁移无副作用，不在启动迁移里扫描历史工件。"""

    import ocr_manager.storage as storage

    store, _, _ = historic(client, settings)
    before = facts(store)
    with store.connection() as db:
        from schema_fixtures import remove_chat_capture_schema
        remove_chat_capture_schema(db)
        db.execute("DROP TABLE review_historical_diagnostics")
        db.execute("PRAGMA user_version=45")
    migration = storage.DIAGNOSTIC_IMPORT_MIGRATION
    monkeypatch.setattr(storage, "DIAGNOSTIC_IMPORT_MIGRATION", migration + "invalid SQL;")
    with pytest.raises(sqlite3.OperationalError):
        store.migrate()
    with store.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 45
    monkeypatch.setattr(storage, "DIAGNOSTIC_IMPORT_MIGRATION", migration)
    store.migrate()
    store.migrate()
    assert facts(store) == before
    with store.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == storage.SCHEMA_VERSION
        assert db.execute("SELECT count(*) FROM review_historical_diagnostics").fetchone()[0] == 0
