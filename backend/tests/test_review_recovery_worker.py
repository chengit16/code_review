"""用合成 Git/OCR 适配器验证补审执行边界；不访问外网、不消耗模型额度。"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from ocr_manager import review_recovery_worker as worker
from ocr_manager import storage
from ocr_manager.config import Settings
from ocr_manager.review_recovery_store import cancel, claim, enqueue, finish
from test_review_recovery import PATHS, child_result, command, make_source


def install_adapters(
    monkeypatch: pytest.MonkeyPatch,
    raw: dict[str, Any],
    observations: list[Any],
    *,
    git_valid: bool = True,
    after_review: Any = None,
) -> None:
    """替换所有外部操作，并检查执行确实携带有限预算、原 SHA 和冻结剩余集合。"""

    class SyntheticGit:
        def __init__(self, *_: Any) -> None:
            pass

        def fetch(self) -> None:
            observations.append("fetch")

        def is_on_target(self, _: str) -> bool:
            return git_valid

        def is_range_base(self, base: str, head: str) -> bool:
            observations.append((base, head))
            return git_valid

        def rule_digest(self, _: str) -> str:
            return ""

        def checkout(self, sha: str, path: Path) -> None:
            observations.append(("checkout", sha))
            path.mkdir(parents=True)

        def remove_checkout(self, _: Path) -> None:
            observations.append("cleanup")

    def run(
        settings: Settings, checkout: Path, run_dir: Path, sha: str, *_: Any, **kwargs: Any
    ) -> tuple[str, dict[str, Any]]:
        observations.append("model")
        assert checkout.name == "checkout"
        assert sha == raw["manifest"]["input"]["resolved_head"]
        assert settings.ocr_max_tokens_budget == 1000 and settings.ocr_timeout_seconds == 20
        assert kwargs["recovery_selection"] == (set(PATHS), set(PATHS[1:]))
        result = child_result(raw)
        if after_review:
            after_review(result)
        (run_dir / "result.json").write_text(json.dumps(result))
        return "complete", result

    monkeypatch.setattr(worker, "GitRepository", SyntheticGit)
    monkeypatch.setattr(worker, "inspect_range", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(worker, "run_review", run)


@pytest.mark.parametrize("mode", ["commit", "range"])
def test_fixed_input_subset_worker_creates_candidate_only(
    client: TestClient,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    """两种固定输入均在隔离目录执行；成功只生成候选，不重写初审或创建补充通知。"""

    store, enabled, raw = make_source(client, settings)
    if mode == "range":
        raw["manifest"]["input"].update(mode="range", resolved_base="b" * 40)
        with store.connection() as db:
            db.execute("UPDATE review_jobs SET base_sha=? WHERE id=1", ("b" * 40,))
            path = Path(db.execute("SELECT result_path FROM review_jobs").fetchone()[0])
        path.write_text(json.dumps(raw))
    enqueue(store, enabled, 1, command())
    task = claim(store)
    assert task
    observations: list[Any] = []
    install_adapters(monkeypatch, raw, observations)
    worker.execute_recovery(store, enabled, task)
    assert observations.count("model") == 1 and observations[-1] == "cleanup"
    with store.connection() as db:
        assert db.execute("SELECT status FROM review_recoveries").fetchone()[0] == "complete"
        assert db.execute("SELECT COUNT(*) FROM review_recovery_aggregates").fetchone()[0] == 1
        assert db.execute("SELECT status FROM review_jobs").fetchone()[0] == "partial"
        assert db.execute("SELECT COUNT(*) FROM notification_deliveries").fetchone()[0] == 1
    assert (enabled.data_dir / "runs/1/recoveries/1/result.json").is_file()


@pytest.mark.parametrize("fault", ["deleted", "symlink", "outside", "json", "sha", "finding"])
def test_untrusted_source_artifact_is_rejected_before_git_or_model(
    client: TestClient,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    """数据库引用不能绕过目录边界，原始输入/发现不符时禁止消耗模型。"""

    store, enabled, raw = make_source(client, settings)
    enqueue(store, enabled, 1, command())
    task = claim(store)
    assert task
    with store.connection() as db:
        path = Path(db.execute("SELECT result_path FROM review_jobs").fetchone()[0])
    outside = enabled.data_dir / "outside.json"
    outside.write_bytes(path.read_bytes())
    if fault == "deleted":
        path.unlink()
    elif fault == "symlink":
        path.unlink()
        path.symlink_to(outside)
    elif fault == "outside":
        with store.connection() as db:
            db.execute("UPDATE review_attempts SET result_path=?", (str(outside),))
    elif fault == "json":
        path.write_text("synthetic-private invalid")
    else:
        if fault == "sha":
            raw["manifest"]["input"]["resolved_head"] = "f" * 40
        else:
            raw["comments"][0]["content"] = "synthetic-private mutation"
        path.write_text(json.dumps(raw))
    observations: list[Any] = []
    install_adapters(monkeypatch, raw, observations)
    worker.execute_recovery(store, enabled, task)
    assert observations == []
    with store.connection() as db:
        row = db.execute("SELECT status,error_code,result_json FROM review_recoveries").fetchone()
        assert row["status"] == "failed" and row["error_code"] == "source_artifact_invalid"
        assert row["result_json"] is None


def test_config_change_and_unreachable_commit_never_call_model(
    client: TestClient,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """原模型快照不可静默升级；Git 不可达是输入问题，不当作网关错误整批重试。"""

    store, enabled, raw = make_source(client, settings)
    observations: list[Any] = []
    install_adapters(monkeypatch, raw, observations, git_valid=False)
    enqueue(store, enabled, 1, command())
    task = claim(store)
    assert task
    worker.execute_recovery(store, replace(enabled, ocr_model="changed"), task)
    assert observations == []
    enqueue(store, enabled, 1, command())
    next_task = claim(store)
    assert next_task
    worker.execute_recovery(store, enabled, next_task)
    assert "model" not in observations
    with store.connection() as db:
        assert [row[0] for row in db.execute("SELECT error_code FROM review_recoveries")] == [
            "configuration_changed",
            "git_input_changed",
        ]


def test_cancel_during_model_preserves_valid_usage_without_aggregate(
    client: TestClient,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """取消优先于迟到可信 JSON；本批次用量可记录，但不能推进聚合。"""

    store, enabled, raw = make_source(client, settings)
    batch = enqueue(store, enabled, 1, command())
    task = claim(store)
    assert task
    install_adapters(monkeypatch, raw, [], after_review=lambda _: cancel(store, batch))
    worker.execute_recovery(store, enabled, task)
    with store.connection() as db:
        row = db.execute("SELECT status,result_json FROM review_recoveries").fetchone()
        assert row["status"] == "cancelled"
        assert json.loads(row["result_json"])["usage"]["total_tokens"] == 3
        assert db.execute("SELECT COUNT(*) FROM review_recovery_aggregates").fetchone()[0] == 0


def test_migration_from_42_and_failed_migration_roll_back(
    client: TestClient,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """仅在临时库回放新迁移；失败保留版本 42 与原任务，不留下半张新表。"""

    store, _, _ = make_source(client, settings)
    with store.connection() as db:
        before = [tuple(row) for row in db.execute("SELECT * FROM review_jobs")]
        from schema_fixtures import remove_finding_schema

        remove_finding_schema(db)
        db.execute("DROP TABLE review_recovery_aggregates")
        db.execute("DROP TABLE review_recoveries")
        db.execute("PRAGMA user_version=42")
    with monkeypatch.context() as broken:
        broken.setattr(
            storage,
            "RECOVERY_MIGRATION",
            storage.RECOVERY_MIGRATION + "\nINSERT INTO missing_table VALUES(1);",
        )
        with pytest.raises(sqlite3.OperationalError):
            store.migrate()
    with store.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 42
        assert not db.execute(
            "SELECT 1 FROM sqlite_master WHERE name='review_recoveries'"
        ).fetchone()
    store.migrate()
    store.migrate()
    with store.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == storage.SCHEMA_VERSION
        assert [tuple(row) for row in db.execute("SELECT * FROM review_jobs")] == before


def test_aggregate_write_failure_rolls_back_and_old_token_cannot_finalize(
    client: TestClient,
    settings: Settings,
) -> None:
    """候选写入与批次终态同事务，数据库错误不留下完成假象或复用过期执行身份。"""

    store, enabled, raw = make_source(client, settings)
    enqueue(store, enabled, 1, command())
    task = claim(store)
    assert task
    assert not finish(store, task | {"execution_token": "wrong"}, child_result(raw))
    with store.connection() as db:
        db.execute("""CREATE TRIGGER reject_candidate BEFORE INSERT ON review_recovery_aggregates
            BEGIN SELECT RAISE(ABORT,'synthetic'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        finish(store, task, child_result(raw))
    with store.connection() as db:
        assert db.execute("SELECT status FROM review_recoveries").fetchone()[0] == "running"
        assert db.execute("SELECT COUNT(*) FROM review_recovery_aggregates").fetchone()[0] == 0


def test_settings_read_race_is_rejected_before_external_calls(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """配置摘要与实际凭据装配之间变更模型时，即使之后恢复原配置也不误调用新模型。"""

    from ocr_manager import worker as review_worker

    store, enabled, raw = make_source(client, settings)
    enqueue(store, enabled, 1, command())
    task = claim(store)
    assert task
    original = review_worker.review_settings
    reads = 0

    def changing(*args: Any, **kwargs: Any) -> tuple[Settings, int]:
        nonlocal reads
        reads += 1
        model, version = original(*args, **kwargs)
        return (replace(model, ocr_model="changed") if reads == 2 else model), version

    observations: list[Any] = []
    install_adapters(monkeypatch, raw, observations)
    monkeypatch.setattr(review_worker, "review_settings", changing)
    worker.execute_recovery(store, enabled, task)
    assert reads == 2 and observations == []
    with store.connection() as db:
        assert db.execute("SELECT error_code FROM review_recoveries").fetchone()[0] == (
            "configuration_changed")


def test_recovery_shares_model_lane_with_normal_reviews(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """初审占槽时补审不被提前领取，槽释放后才执行一次且不会调用旧串行入口。"""

    import threading

    from ocr_manager import worker as review_worker
    from ocr_manager.worker_scheduler import WorkerScheduler
    from test_worker_scheduler import pump

    store, enabled, raw = make_source(client, settings)
    enqueue(store, enabled, 1, command())
    with store.connection() as db:
        # 只复制合成任务的固定输入，避开队列去重约束，不接触任何真实业务库。
        db.execute("""INSERT INTO review_jobs(id,repository_id,event_id,mr_iid,commit_sha,
            config_hash,ordinal) SELECT 2,repository_id,event_id,mr_iid,commit_sha,
            'synthetic-next-config',2 FROM review_jobs WHERE id=1""")
        db.execute("UPDATE notification_deliveries SET status='sent'")
    started, release, recovered = (threading.Event() for _ in range(3))
    seen: list[str] = []

    def normal(_store: Any, _settings: Settings, task: dict[str, Any]) -> None:
        seen.append("normal")
        started.set()
        assert release.wait(5)
        _store.finish_job(task["id"], "complete", None, {"comments": []}, None)

    def recovery(_store: Any, _settings: Settings, task: dict[str, Any]) -> None:
        assert release.is_set()
        seen.append("recovery")
        assert finish(_store, task, child_result(raw))
        recovered.set()

    monkeypatch.setattr(review_worker, "review_job", normal)
    monkeypatch.setattr(worker, "execute_recovery", recovery)
    monkeypatch.setattr(review_worker, "run_once", lambda *_args: pytest.fail("不能混用旧协调器"))
    monkeypatch.setattr(review_worker, "deliver_notification",
                        lambda db, _settings, task: db.finish_delivery(task["id"], None))
    with review_worker.worker_lock(enabled.data_dir), WorkerScheduler(store, enabled) as scheduler:
        try:
            pump(scheduler, started.is_set)
            for _ in range(5):
                scheduler.tick()
            with store.connection() as db:
                assert db.execute("SELECT status FROM review_recoveries").fetchone()[0] == "queued"
            release.set()
            pump(scheduler, recovered.is_set)
        finally:
            release.set()
    assert seen == ["normal", "recovery"]
