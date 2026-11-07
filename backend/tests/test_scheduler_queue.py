"""验证第四期原子领取、三仓库轮转与独立迁移，不运行外部服务。"""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from ocr_manager import storage, worker
from ocr_manager.config import Settings
from ocr_manager.premerge import enqueue_premerge, finish_premerge, next_premerge
from ocr_manager.publications import next_publication
from schema_fixtures import remove_improvement_schema
from test_task_operations import populate


def test_schema38_transaction_and_existing_running_evidence(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """迁移失败整版回滚；成功只新增调度表，不抢先恢复运行中任务或改写旧策略。"""

    store, _ = populate(client, settings, 1)
    job = store.next_job()
    assert job
    with store.connection() as db:
        remove_improvement_schema(db)
        db.execute("DROP TABLE worker_execution_slots")
        db.execute("PRAGMA user_version=37")
    migration = storage.SCHEDULER_MIGRATION
    monkeypatch.setattr(storage, "SCHEDULER_MIGRATION", migration + "\nINVALID SYNTHETIC SQL;")
    with pytest.raises(sqlite3.OperationalError):
        store.migrate()
    with store.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 37
        assert not db.execute("SELECT name FROM sqlite_master WHERE name='worker_execution_slots'")\
            .fetchone()
    monkeypatch.setattr(storage, "SCHEDULER_MIGRATION", migration)
    store.migrate()
    store.migrate()
    assert store.get_job(job["id"])["status"] == "running"
    with store.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == storage.SCHEMA_VERSION
        assert db.execute("SELECT COUNT(*) FROM worker_execution_slots").fetchone()[0] == 0


def test_three_repository_round_robin_and_event_backoff_preserves_order(
    client: TestClient, settings: Settings,
) -> None:
    """不是仅回避上一仓库：三个持续积压仓库均获机会，同仓库退避事件不可被越过。"""

    store, first_id = populate(client, settings, 3)
    repository = store.get_repository(first_id)
    assert repository
    ids = [first_id]
    for project_id in (43, 44):
        ids.append(store.add_repository({**repository, "project_id": project_id}))
    for repository_id in ids[1:]:
        for iid in range(1, 4):
            assert store.add_event(repository_id, iid, None, None, None)
            event = store.next_event()
            assert event
            sha = f"{iid:040x}"
            store.finish_event(event["id"], [sha], {sha: ("snapshot", "")}, None)
    seen = []
    last = None
    for _ in range(9):
        job = store.next_job(last)
        assert job
        last = job["repository_id"]
        seen.append(last)
        store.finish_job(job["id"], "complete", None, {"comments": []}, None)
    assert seen == ids * 3
    for repository_id in ids:
        for iid in (10, 11):
            assert store.add_event(repository_id, iid, None, None, None)
    events = []
    last = None
    for _ in range(3):
        event = store.next_event(last)
        assert event
        last = event["repository_id"]
        events.append(last)
        store.defer_event(event["id"], "合成退避")
    assert events == ids
    assert store.next_event() is None


def test_premerge_round_robin_and_atomic_claims(
    client: TestClient, settings: Settings,
) -> None:
    """合并前任务也跨仓库轮转，并行连接不能重复领取预审、诊断、补审或行内发布。"""

    store, repository_id = populate(client, settings, 1)
    repository = store.get_repository(repository_id)
    assert repository
    ids = [repository_id, store.add_repository({**repository, "project_id": 43}),
           store.add_repository({**repository, "project_id": 44})]
    for rid in ids:
        with store.connection() as db:
            db.execute("INSERT INTO premerge_settings(repository_id,enabled) VALUES(?,1)", (rid,))
        for iid in (1, 2):
            assert enqueue_premerge(store, rid, iid, "a" * 40)
    last = None
    seen = []
    for _ in range(6):
        review = next_premerge(store, last)
        assert review
        last = review["repository_id"]
        seen.append(last)
        finish_premerge(store, review["id"], "skipped", None, None, None, [], None)
    assert seen == ids * 2
    assert enqueue_premerge(store, repository_id, 10, "b" * 40)
    with ThreadPoolExecutor(max_workers=4) as executor:
        reviews = list(executor.map(lambda _: next_premerge(store), range(8)))
    assert sum(item is not None for item in reviews) == 1
    # 新的跨类型仓库互斥要求预审结束后才能领取同仓库初审。
    active_review = next(item for item in reviews if item is not None)
    assert store.next_job() is None
    finish_premerge(store, active_review["id"], "skipped", None, None, None, [], None)
    job = store.next_job()
    assert job
    store.finish_job(job["id"], "complete", None, {"comments": []}, None)
    store.enqueue_connection_check("model", None)
    with store.connection() as db:
        db.execute("INSERT INTO mr_backfills(repository_id,since,until) VALUES(?,?,?)",
                   (repository_id, "2026-01-01", "2026-01-02"))
        db.execute("INSERT INTO gitlab_publication_settings(repository_id,enabled) VALUES(?,1)",
                   (repository_id,))
        db.execute("INSERT INTO gitlab_publications(job_id,attempt_number,comment_index) "
                   "VALUES(1,1,0)")
    for claim in (lambda: store.next_connection_check(("model",)),
                  lambda: worker.claim_backfill(store), lambda: next_publication(store)):
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = [future.result() for future in [executor.submit(claim) for _ in range(8)]]
        assert sum(item is not None for item in results) == 1
