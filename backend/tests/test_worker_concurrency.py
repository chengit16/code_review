"""以隔离 SQLite 和受控执行器验证 1～10 容量、排空、仓库互斥与恢复，不调用真实模型。"""

from __future__ import annotations

import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from fastapi.testclient import TestClient
from ocr_manager import storage, worker
from ocr_manager.config import Settings
from ocr_manager.premerge import enqueue_premerge, finish_premerge, next_premerge
from ocr_manager.scheduler_config import (
    SchedulerConfigConflict,
    read_scheduler_config,
    save_scheduler_config,
)
from ocr_manager.scheduler_state import scheduler_snapshot
from ocr_manager.storage import Store
from ocr_manager.worker_scheduler import WorkerScheduler
from schema_fixtures import remove_scheduler_capacity_schema
from test_auth import create_user, enable_users, login
from test_task_operations import populate
from test_worker_scheduler import pump

ADMIN = {"X-Admin-Token": "test-admin-token"}
URL = "/api/worker-scheduler/config"


def repositories(client: TestClient, settings: Settings, count: int) -> tuple[Store, list[int]]:
    """每仓库创建两个有序任务，供容量与公平性验证，不复用业务数据。"""

    store, first = populate(client, settings, 2)
    original = store.get_repository(first)
    assert original
    ids = [first]
    for number in range(1, count):
        rid = store.add_repository({**original, "project_id": 42 + number})
        ids.append(rid)
        for iid in (1, 2):
            assert store.add_event(rid, iid, None, None, None)
            event = store.next_event()
            assert event
            sha = f"{iid:040x}"
            store.finish_event(event["id"], [sha], {sha: ("snapshot", "")}, None)
    return store, ids


def set_capacity(store: Store, value: int) -> None:
    """按最新版本显式更新容量，只有测试调用方决定何时调整。"""

    config = read_scheduler_config(store)
    save_scheduler_config(store, value, config["version"], "合成管理员")


def test_api_strict_bounds_conflicts_and_atomic_audit(
    client: TestClient, settings: Settings,
) -> None:
    """默认 1，拒绝 0/11/小数/布尔/字符串/未知键；过期版本不覆盖且保存审计可追溯。"""

    assert client.get(URL).status_code == 401
    assert client.put(URL, json={}).status_code == 401
    assert client.get(URL, headers=ADMIN).json() == {"model_task_concurrency": 1, "version": 1}
    for value in (0, 11, -1, 1.5, True, "2", None):
        assert client.put(URL, headers=ADMIN, json={"model_task_concurrency": value,
                                                   "version": 1}).status_code == 422
    assert client.put(URL, headers=ADMIN, json={"model_task_concurrency": 2, "version": 1,
                                               "extra": 1}).status_code == 422
    assert client.put(URL, headers=ADMIN, json={"model_task_concurrency": 10,
                                               "version": 1}).status_code == 200
    assert client.put(URL, headers=ADMIN, json={"model_task_concurrency": 2,
                                               "version": 1}).status_code == 409
    store = Store(settings.data_dir / "app.db")
    assert read_scheduler_config(store) == {"model_task_concurrency": 10, "version": 2}
    assert scheduler_snapshot(store)["applied_concurrency"] is None
    with store.connection() as db:
        changes = list(db.execute("SELECT * FROM worker_scheduler_changes"))
    assert len(changes) == 1
    assert changes[0]["previous_concurrency"] == 1 and changes[0]["model_task_concurrency"] == 10
    assert changes[0]["actor"] == "共享管理员"
    assert any(item["action"] == "PUT /api/worker-scheduler/config"
               for item in store.list_audit(1, 100)["items"])
    with ThreadPoolExecutor(max_workers=4) as executor:
        def update(value: int) -> bool:
            try:
                save_scheduler_config(store, value, 2, "合成管理员")
                return True
            except SchedulerConfigConflict:
                return False
        assert sum(executor.map(update, (1, 2, 3, 4))) == 1


def test_reader_cannot_save_capacity(client: TestClient) -> None:
    """账号模式的只读用户不能借管理接口调高付费并发。"""

    create_user(client, "admin", "admin")
    create_user(client, "reader", "reader")
    enable_users(client)
    session = login(client, "reader")
    headers = {"Authorization": f"Bearer {session['token']}"}
    assert client.get(URL, headers=headers).status_code == 200
    assert client.put(URL, headers=headers, json={"model_task_concurrency": 10,
                                                 "version": 1}).status_code == 403


@pytest.mark.parametrize("capacity", [1, 2, 10])
def test_capacity_and_same_repository_exclusion(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch, capacity: int,
) -> None:
    """真实重叠的线程达到指定上限，但同仓库第二个任务保持排队，通知仍独立。"""

    store, ids = repositories(client, settings, 10)
    set_capacity(store, capacity)
    release = threading.Event()
    started: set[int] = set()
    lock = threading.Lock()

    def review(db: Store, _settings: Settings, task: dict[str, Any]) -> None:
        with lock:
            assert task["repository_id"] not in started
            started.add(task["repository_id"])
        assert release.wait(10)
        db.finish_job(task["id"], "complete", None, {"comments": []}, None)

    monkeypatch.setattr(worker, "review_job", review)
    monkeypatch.setattr(worker, "deliver_notification",
                        lambda db, _settings, task: db.finish_delivery(task["id"], None))
    with WorkerScheduler(store, settings) as scheduler:
        try:
            pump(scheduler, lambda: len(started) == capacity)
            for _ in range(4):
                scheduler.tick()
            facts = scheduler_snapshot(store)
            assert facts["applied_concurrency"] == capacity
            assert facts["running_model_tasks"] == capacity
            assert len(started) == capacity
            assert started == set(ids[:capacity])
            assert len({slot["slot_id"] for slot in facts["slots"]}) == capacity + 2
        finally:
            release.set()


def test_hot_raise_and_lower_drains_without_refill_or_cancellation(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """1→2→1 无需重启；低编号先结束时也不能越过仍在运行的高编号再次领取。"""

    store, ids = repositories(client, settings, 3)
    started: list[int] = []
    releases = {rid: threading.Event() for rid in ids}

    def review(db: Store, _settings: Settings, task: dict[str, Any]) -> None:
        started.append(task["repository_id"])
        assert releases[task["repository_id"]].wait(10)
        db.finish_job(task["id"], "complete", None, {"comments": []}, None)

    monkeypatch.setattr(worker, "review_job", review)
    monkeypatch.setattr(worker, "deliver_notification",
                        lambda db, _settings, task: db.finish_delivery(task["id"], None))
    with WorkerScheduler(store, settings) as scheduler:
        try:
            pump(scheduler, lambda: len(started) == 1)
            set_capacity(store, 2)
            pump(scheduler, lambda: len(started) == 2)
            set_capacity(store, 1)
            scheduler.tick()
            assert scheduler_snapshot(store)["draining"]
            assert not scheduler.stopping.is_set()
            releases[ids[0]].set()
            first = scheduler.lanes[0].future
            assert first
            first.result(timeout=4)
            for _ in range(4):
                scheduler.tick()
            assert started == ids[:2]
            assert scheduler_snapshot(store)["running_model_tasks"] == 1
            releases[ids[1]].set()
            pump(scheduler, lambda: len(started) == 3)
            assert started == ids
        finally:
            for event in releases.values():
                event.set()


def test_cross_kind_claims_are_atomic_and_slots_hold_cancelled_repository(
    client: TestClient, settings: Settings,
) -> None:
    """初审/预审并行领取只允许同仓库一个；业务取消终态不能提前释放在途槽。"""

    store, rid = populate(client, settings, 1)
    with store.connection() as db:
        db.execute("INSERT INTO premerge_settings(repository_id,enabled) VALUES(?,1)", (rid,))
    assert enqueue_premerge(store, rid, 7, "a" * 40)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(store.next_job), executor.submit(next_premerge, store)]
        results = [future.result() for future in futures]
    assert sum(item is not None for item in results) == 1
    with store.connection() as db:
        db.execute("UPDATE review_jobs SET status='queued',attempts=0")
        db.execute("UPDATE premerge_reviews SET status='queued',attempts=0")
    from ocr_manager.scheduler_state import finish_slot, start_slot

    with WorkerScheduler(store, settings) as scheduler:
        generation = start_slot(store, scheduler.owner, "model", "premerge",
                                {"id": 1, "repository_id": rid})
        finish_premerge(store, 1, "cancelled", None, None, None, [], None)
        assert store.next_job() is None
        finish_slot(store, scheduler.owner, "model", generation)
        assert store.next_job() is not None


def test_schema49_transaction_preserves_old_slot_and_rejects_old_program(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """从 48 升级保留在途证据，失败整版回滚；旧程序不得打开新版数据库。"""

    store, _ = populate(client, settings, 1)
    with WorkerScheduler(store, settings):
        pass
    with store.connection() as db:
        remove_scheduler_capacity_schema(db)
        db.execute("UPDATE worker_execution_slots SET state='running',task_kind='review',task_id=9")
        db.execute("PRAGMA user_version=48")
    migration = storage.CONCURRENCY_MIGRATION
    monkeypatch.setattr(storage, "CONCURRENCY_MIGRATION", migration + "INVALID SQL;")
    with pytest.raises(sqlite3.OperationalError):
        store.migrate()
    with store.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 48
        columns = {row[1] for row in db.execute("PRAGMA table_info(worker_execution_slots)")}
        assert "slot_id" not in columns
    monkeypatch.setattr(storage, "CONCURRENCY_MIGRATION", migration)
    store.migrate()
    store.migrate()
    facts = scheduler_snapshot(store)
    assert len(facts["slots"]) == 3
    assert all(slot["state"] == "running" and slot["task_id"] == 9 for slot in facts["slots"])
    assert facts["applied_concurrency"] is None
    monkeypatch.setattr(storage, "SCHEMA_VERSION", 48)
    with pytest.raises(RuntimeError, match="数据库版本高于"):
        store.migrate()


def test_recovery_shares_capacity_and_repository_guard_without_expanding_budget(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """补审与另一仓库初审可重叠，同源预审等待；扩容不增加批准批次或 Token。"""

    from ocr_manager import review_recovery_worker
    from ocr_manager.review_recovery_store import enqueue, finish
    from test_review_recovery import child_result, command, make_source

    store, enabled, raw = make_source(client, settings)
    source = store.get_job(1)
    assert source
    rid = source["repository_id"]
    original = store.get_repository(rid)
    assert original
    other = store.add_repository({**original, "project_id": 43})
    assert store.add_event(other, 1, None, None, None)
    event = store.next_event()
    assert event
    sha = "b" * 40
    store.finish_event(event["id"], [sha], {sha: ("snapshot", "")}, None)
    with store.connection() as db:
        db.execute("INSERT INTO premerge_settings(repository_id,enabled) VALUES(?,1)", (rid,))
    assert enqueue_premerge(store, rid, 7, "a" * 40)
    recovery_id = enqueue(store, enabled, 1, command())
    set_capacity(store, 2)
    release = threading.Event()
    started: set[str] = set()

    def review(db: Store, _settings: Settings, task: dict[str, Any]) -> None:
        started.add("review")
        assert release.wait(10)
        db.finish_job(task["id"], "complete", None, {"comments": []}, None)

    def recover(db: Store, _settings: Settings, task: dict[str, Any]) -> None:
        assert task["id"] == recovery_id
        assert task["token_budget"] == 1000
        started.add("recovery")
        assert release.wait(10)
        assert finish(db, task, child_result(raw))

    monkeypatch.setattr(worker, "review_job", review)
    monkeypatch.setattr(review_recovery_worker, "execute_recovery", recover)
    monkeypatch.setattr(worker, "deliver_notification",
                        lambda db, _settings, task: db.finish_delivery(task["id"], None))
    with WorkerScheduler(store, enabled) as scheduler:
        try:
            pump(scheduler, lambda: started == {"review", "recovery"})
            for _ in range(3):
                scheduler.tick()
            assert scheduler_snapshot(store)["running_model_tasks"] == 2
            assert next_premerge(store) is None
            with store.connection() as db:
                rows = list(db.execute("SELECT token_budget,status FROM review_recoveries"))
            assert len(rows) == 1 and rows[0]["token_budget"] == 1000
            assert rows[0]["status"] == "running"
        finally:
            release.set()


def test_model_diagnostics_count_toward_shared_capacity(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """两个槽中的一个可用于模型诊断，不能在两槽都忙时额外启动第三个模型工作。"""

    from ocr_manager import checks

    store, _ = repositories(client, settings, 3)
    set_capacity(store, 2)
    check_id = store.enqueue_connection_check("model", None)
    started: list[str] = []
    release = threading.Event()

    def review(db: Store, _settings: Settings, task: dict[str, Any]) -> None:
        started.append("review")
        assert release.wait(10)
        db.finish_job(task["id"], "complete", None, {"comments": []}, None)

    def check(db: Store, _settings: Settings, task: dict[str, Any]) -> None:
        assert task["id"] == check_id
        started.append("check")
        assert release.wait(10)
        db.finish_connection_check(task["id"], None)

    monkeypatch.setattr(worker, "review_job", review)
    monkeypatch.setattr(checks, "run_connection_check", check)
    with WorkerScheduler(store, settings) as scheduler:
        try:
            pump(scheduler, lambda: len(started) == 2)
            for _ in range(4):
                scheduler.tick()
            assert sorted(started) == ["check", "review"]
            assert scheduler_snapshot(store)["running_model_tasks"] == 2
        finally:
            release.set()


def test_multiple_interrupted_reviews_recover_under_single_worker_fence(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """两槽停止都保留中断而非成功；独占恢复逐任务记账，重启沿用容量并拒绝旧 owner。"""

    import json

    from ocr_manager.cancellation import check_cancellation
    from ocr_manager.scheduler_state import finish_slot

    store, _ = repositories(client, settings, 2)
    set_capacity(store, 2)
    started: list[int] = []

    def review(db: Store, _settings: Settings, task: dict[str, Any]) -> None:
        with db.connection() as connection:
            connection.execute("UPDATE review_jobs SET config_snapshot=? WHERE id=?",
                               (json.dumps({"review_policy": worker.REVIEW_POLICY}), task["id"]))
        started.append(task["id"])
        while True:
            check_cancellation()
            threading.Event().wait(0.01)

    monkeypatch.setattr(worker, "review_job", review)
    with worker.worker_lock(settings.data_dir):
        scheduler = WorkerScheduler(store, settings)
        pump(scheduler, lambda: len(started) == 2)
        owner = scheduler.owner
        scheduler.close()
        store.recover()
        for job_id in started:
            job = store.get_job(job_id)
            assert job and job["status"] == "queued"
            assert len(job["attempt_history"]) == 1
            assert "中断" in job["attempt_history"][0]["error"]
        with WorkerScheduler(store, settings) as restarted:
            assert restarted.owner != owner and restarted.capacity == 2
            finish_slot(store, owner, "model", 1)
            facts = scheduler_snapshot(store)
            assert facts["applied_concurrency"] == 2
            assert all(slot["owner"] == restarted.owner for slot in facts["slots"])


def test_capacity_does_not_invalidate_review_snapshot_or_queued_input(
    client: TestClient, settings: Settings,
) -> None:
    """容量是调度元数据，调整至 10 不改队列 SHA/快照、内部并发或冻结输入摘要。"""

    store, rid = populate(client, settings, 1)
    before = worker.configuration_snapshot(store, settings, repository_id=rid)
    with store.connection() as db:
        queued = [dict(row) for row in db.execute("SELECT * FROM review_jobs")]
    set_capacity(store, 10)
    after = worker.configuration_snapshot(store, settings, repository_id=rid)
    assert before == after
    assert worker.snapshot_hash(before) == worker.snapshot_hash(after)
    with store.connection() as db:
        assert [dict(row) for row in db.execute("SELECT * FROM review_jobs")] == queued


def test_stale_heartbeat_does_not_confirm_applied_capacity_or_release_repository(
    client: TestClient, settings: Settings,
) -> None:
    """失联只使已应用容量未知；持久化运行槽仍禁止同仓库再次领取。"""

    from ocr_manager.scheduler_state import start_slot

    store, rid = populate(client, settings, 1)
    set_capacity(store, 10)
    with WorkerScheduler(store, settings) as scheduler:
        start_slot(store, scheduler.owner, "model:10", "review", {"id": 999, "repository_id": rid})
        with store.connection() as db:
            db.execute("UPDATE worker_execution_slots SET heartbeat_at='2000-01-01 00:00:00'")
        facts = scheduler_snapshot(store)
        assert facts["model_task_concurrency"] == 10 and facts["applied_concurrency"] is None
        assert facts["running_model_tasks"] == 1
        assert store.next_job() is None
