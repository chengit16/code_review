"""用临时 SQLite 和有界合成执行器验证第四阶段解耦、轮转和停止，不调用外部服务。"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from fastapi.testclient import TestClient
from ocr_manager import checks, worker
from ocr_manager.artifact_lock import artifact_lock
from ocr_manager.cancellation import check_cancellation
from ocr_manager.config import Settings
from ocr_manager.monitoring import prune_orphan_artifacts
from ocr_manager.premerge import enqueue_premerge, finish_premerge
from ocr_manager.scheduler_state import finish_slot, scheduler_snapshot
from ocr_manager.storage import Store
from ocr_manager.worker_scheduler import WorkerScheduler
from test_task_operations import populate


def pump(scheduler: WorkerScheduler, condition: Callable[[], bool], timeout: float = 4) -> None:
    """同步等待合成事件，不用任意长 sleep 猜测线程是否已执行。"""

    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "隔离调度未在期限内完成"
        scheduler.tick()
        time.sleep(0.01)


def test_long_review_does_not_block_event_or_notification(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """长 OCR 阻塞期间，事件展开、投递和心跳均推进，第二个模型任务仍保持 queued。"""

    store, repository_id = populate(client, settings, 3)
    finished = store.next_job()
    assert finished
    store.finish_job(finished["id"], "complete", None, {"comments": []}, None)
    assert store.add_event(repository_id, 99, None, None, None)
    started, release, notified, expanded = (threading.Event() for _ in range(4))
    calls: list[int] = []

    def review(_store: Store, _settings: Settings, task: dict[str, Any]) -> None:
        calls.append(task["id"])
        started.set()
        assert release.wait(5)
        _store.finish_job(task["id"], "complete", None, {"comments": []}, None)

    def event(_store: Store, _settings: Settings, task: dict[str, Any]) -> None:
        _store.finish_event(task["id"], [], {}, None)
        expanded.set()

    def notify(_store: Store, _settings: Settings, task: dict[str, Any]) -> None:
        _store.finish_delivery(task["id"], None)
        notified.set()

    monkeypatch.setattr(worker, "review_job", review)
    monkeypatch.setattr(worker, "expand_event", event)
    monkeypatch.setattr(worker, "deliver_notification", notify)
    with worker.worker_lock(settings.data_dir), WorkerScheduler(store, settings) as scheduler:
        try:
            pump(scheduler, lambda: started.is_set() and notified.is_set() and expanded.is_set())
            for _ in range(10):
                scheduler.tick()
            assert len(calls) == 1
            with store.connection() as db:
                row = db.execute(
                    "SELECT COUNT(*) FROM review_jobs WHERE status='queued'").fetchone()
                assert row[0] == 1
                db.execute("UPDATE worker_execution_slots SET heartbeat_at='2000-01-01 00:00:00'")
            scheduler.last_heartbeat = 0
            scheduler.tick()
            snapshot = scheduler_snapshot(store)
            model = next(slot for slot in snapshot["slots"] if slot["lane"] == "model")
            assert model["state"] == "running" and model["task_id"] == calls[0]
            assert model["heartbeat_age_seconds"] < 2
            assert snapshot["model_task_concurrency"] == 1
        finally:
            release.set()


def test_model_lane_rotates_reviews_premerge_and_diagnostics(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """持续合并后任务不能饿死合并前任务和模型诊断，三个类别从不重叠调用模型。"""

    store, repository_id = populate(client, settings, 4)
    with store.connection() as db:
        db.execute("INSERT INTO premerge_settings(repository_id,enabled) VALUES(?,1)",
                   (repository_id,))
    assert enqueue_premerge(store, repository_id, 7, "a" * 40)
    check_id = store.enqueue_connection_check("model", None)
    assert check_id
    seen: list[str] = []
    active = 0
    maximum = 0

    def enter(kind: str) -> None:
        nonlocal active, maximum
        active += 1
        maximum = max(active, maximum)
        seen.append(kind)
        time.sleep(0.01)
        active -= 1

    def review(_store: Store, _settings: Settings, task: dict[str, Any]) -> None:
        enter("review")
        _store.finish_job(task["id"], "complete", None, {"comments": []}, None)

    def premerge(_store: Store, _settings: Settings, task: dict[str, Any]) -> None:
        enter("premerge")
        finish_premerge(_store, task["id"], "skipped", None, None, None, [], None)

    def check(_store: Store, _settings: Settings, task: dict[str, Any]) -> None:
        enter("check")
        _store.finish_connection_check(task["id"], None)

    monkeypatch.setattr(worker, "review_job", review)
    monkeypatch.setattr(worker, "review_premerge", premerge)
    monkeypatch.setattr(checks, "run_connection_check", check)
    monkeypatch.setattr(worker, "deliver_notification",
                        lambda db, _settings, task: db.finish_delivery(task["id"], None))
    with WorkerScheduler(store, settings) as scheduler:
        pump(scheduler, lambda: len(seen) >= 4)
    assert seen[:4] == ["review", "premerge", "check", "review"]
    assert maximum == 1


def test_stopping_is_not_user_cancel_and_recovery_is_bounded(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """停止执行器不伪造失败/成功；下一次独占恢复保留中断尝试并沿用两次预算。"""

    store, _ = populate(client, settings, 1)
    started = threading.Event()

    def review(_store: Store, _settings: Settings, task: dict[str, Any]) -> None:
        with _store.connection() as db:
            db.execute("UPDATE review_jobs SET config_snapshot=? WHERE id=?",
                       (json.dumps({"review_policy": worker.REVIEW_POLICY}), task["id"]))
        started.set()
        while True:
            check_cancellation()
            time.sleep(0.01)

    monkeypatch.setattr(worker, "review_job", review)
    for attempt in (1, 2):
        with worker.worker_lock(settings.data_dir):
            scheduler = WorkerScheduler(store, settings)
            pump(scheduler, started.is_set)
            scheduler.close()
            store.recover()
        detail = store.get_job(1)
        assert detail and detail["status"] == ("queued" if attempt == 1 else "failed")
        assert len(detail["attempt_history"]) == attempt
        assert "中断" in detail["attempt_history"][0]["error"]
        started.clear()


def test_deleted_project_stops_active_review_and_cleanup_waits_for_artifact_lock(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """删除不复活结果，工件清理不能越过正在使用目录的执行槽。"""

    store, repository_id = populate(client, settings, 1)
    started, deleted, cleaned = threading.Event(), threading.Event(), threading.Event()
    directory = settings.data_dir / "runs/1"
    directory.mkdir(parents=True)
    (directory / "synthetic.json").write_text("{}")

    def review(_store: Store, _settings: Settings, task: dict[str, Any]) -> None:
        started.set()
        assert deleted.wait(4)
        assert worker.cancellation_requested(_store, task["id"])
        assert cleaned.wait(4)

    monkeypatch.setattr(worker, "review_job", review)
    with WorkerScheduler(store, settings) as scheduler:
        try:
            pump(scheduler, started.is_set)
            store.delete_repository(repository_id)
            deleted.set()
            assert prune_orphan_artifacts(store, settings.data_dir)["count"] == 0
        finally:
            deleted.set()
            cleaned.set()
    assert prune_orphan_artifacts(store, settings.data_dir)["count"] == 1
    assert store.get_job(1) is None


def test_parallel_claim_and_sending_prevent_duplicate_or_stale_notification(
    client: TestClient, settings: Settings,
) -> None:
    """并行数据库连接只能领取一次；旧结果正在发送时重评审必须冲突。"""

    store, repository_id = populate(client, settings, 1)
    job = store.next_job()
    assert job
    store.finish_job(job["id"], "complete", None, {"comments": []}, None)
    with ThreadPoolExecutor(max_workers=4) as executor:
        deliveries = list(executor.map(lambda _: store.next_delivery(), range(8)))
    claimed = [item for item in deliveries if item]
    assert len(claimed) == 1
    assert store.retry_job(job["id"]) is None
    assert store.retry_job(job["id"], "different-snapshot") is None
    store.finish_delivery(claimed[0]["id"], None)
    assert store.retry_job(job["id"]) == job["id"]
    assert store.add_event(repository_id, 8, None, None, None)
    with ThreadPoolExecutor(max_workers=4) as executor:
        events = list(executor.map(lambda _: store.next_event(), range(8)))
    assert sum(item is not None for item in events) == 1


def test_late_generation_cannot_release_active_slot(
    client: TestClient, settings: Settings,
) -> None:
    """旧身份或旧代次的释放操作不影响当前执行单元。"""

    from ocr_manager.scheduler_state import start_slot

    store, _ = populate(client, settings, 0)
    with WorkerScheduler(store, settings) as scheduler:
        generation = start_slot(store, scheduler.owner, "model", "review", {"id": 123})
        finish_slot(store, "old-owner", "model", generation)
        finish_slot(store, scheduler.owner, "model", generation - 1)
        model = next(slot for slot in scheduler_snapshot(store)["slots"] if slot["lane"] == "model")
        assert model["state"] == "running"


def test_unhandled_execution_failure_stops_dispatch(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """执行器异常不能无限吞掉或把未确认任务标为完成，重启后统一恢复。"""

    store, _ = populate(client, settings, 2)

    def fail(*_args: Any) -> None:
        raise RuntimeError("合成执行器故障")

    monkeypatch.setattr(worker, "review_job", fail)
    with WorkerScheduler(store, settings) as scheduler:
        scheduler.tick()
        with pytest.raises(RuntimeError, match="合成执行器故障"):
            pump(scheduler, lambda: False)
    assert store.get_job(1)["status"] == "running"
    assert store.get_job(2)["status"] == "queued"


def test_model_checks_remain_queued_while_review_is_blocked(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """模型连接诊断不能绕过唯一模型槽；Git/飞书诊断按各自配额运行。"""

    store, repository_id = populate(client, settings, 1)
    started, release = threading.Event(), threading.Event()
    checked: list[str] = []

    def review(*_args: Any) -> None:
        started.set()
        assert release.wait(4)

    def check(_store: Store, _settings: Settings, task: dict[str, Any]) -> None:
        checked.append(task["kind"])
        _store.finish_connection_check(task["id"], None)

    monkeypatch.setattr(worker, "review_job", review)
    monkeypatch.setattr(checks, "run_connection_check", check)
    store.enqueue_connection_check("model", None)
    store.enqueue_connection_check("git", repository_id)
    store.enqueue_connection_check("feishu", repository_id)
    with WorkerScheduler(store, settings) as scheduler:
        try:
            pump(scheduler, lambda: started.is_set() and len(checked) == 2)
            assert set(checked) == {"git", "feishu"}
            assert next(item for item in store.list_connection_checks()
                        if item["kind"] == "model")["status"] == "queued"
        finally:
            release.set()


def test_operations_exposes_only_persisted_scheduler_facts(
    client: TestClient, settings: Settings,
) -> None:
    """调度信息保持管理员权限；空表不伪造已启用，启动后只显示三个安全执行槽。"""

    store, _ = populate(client, settings, 0)
    assert client.get("/api/operations").status_code == 401
    headers = {"X-Admin-Token": settings.admin_token}
    assert client.get("/api/operations", headers=headers).json()["scheduler"]["slots"] == []
    with worker.worker_lock(settings.data_dir), WorkerScheduler(store, settings):
        facts = client.get("/api/operations", headers=headers).json()["scheduler"]
        assert facts["model_task_concurrency"] == 1
        assert {slot["lane"] for slot in facts["slots"]} == {"model", "ingress", "delivery"}
        assert all(slot["state"] == "idle" for slot in facts["slots"])
        assert "api_key" not in json.dumps(facts)


def test_deleted_project_invalidates_claimed_notification_before_send(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """通知已领取但尚未取得工件锁时删除项目，解锁后不能发送旧快照。"""

    store, repository_id = populate(client, settings, 1)
    job = store.next_job()
    assert job
    store.finish_job(job["id"], "complete", None, {"comments": []}, None)
    sent = threading.Event()
    monkeypatch.setattr(worker, "deliver_notification", lambda *_args: sent.set())
    with WorkerScheduler(store, settings) as scheduler:
        with artifact_lock(settings.data_dir, job["id"], blocking=True):
            scheduler.tick()
            with store.connection() as db:
                assert db.execute("SELECT status FROM notification_deliveries").fetchone()[0] \
                    == "sending"
            store.delete_repository(repository_id)
        delivery = next(lane for lane in scheduler.lanes if lane.name == "delivery")
        assert delivery.future is not None
        delivery.future.result(timeout=4)
    assert not sent.is_set()
