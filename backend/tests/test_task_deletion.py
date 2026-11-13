"""验证删除权限、版本冲突、后台在途保护与跨任务统计来源；仅使用合成数据。"""

from __future__ import annotations

import sqlite3
from typing import Any

import pytest
from fastapi.testclient import TestClient
from ocr_manager.artifact_lock import artifact_lock
from ocr_manager.config import Settings
from ocr_manager.review_recovery_store import enqueue
from ocr_manager.storage import Store
from ocr_manager.task_deletion import DeleteTaskRequest, delete_task
from test_auth import create_user, enable_users, login
from test_review_recovery import command, make_source
from test_task_operations import populate

ADMIN = {"X-Admin-Token": "test-admin-token"}


def finished_tasks(client: TestClient, settings: Settings) -> Store:
    """两个任务共享一条发现，第一个另有独占发现，通知均已终结。"""

    store, _ = populate(client, settings, 2)
    for number in (1, 2):
        job = store.next_job()
        assert job and job["id"] == number
        comments = [{"path": "shared.py", "content": "共享合成发现", "severity": "high"}]
        if number == 1:
            comments.append({"path": "only.py", "content": "独占合成发现",
                             "severity": "medium"})
        store.finish_job(number, "complete", None, {"comments": comments}, None)
    with store.connection() as db:
        db.execute("UPDATE notification_deliveries SET status='sent'")
    return store


def snapshot(store: Store, job_id: int = 1) -> dict[str, Any]:
    """从持久事实获取待确认版本，不伪造当前时间或运行结果。"""

    job = store.get_job(job_id)
    assert job
    return {"expected_status": job["status"], "expected_attempts": job["attempts"],
            "expected_finished_at": job["finished_at"]}


def test_delete_cleans_statistics_preserves_shared_sources_and_audit(
    client: TestClient, settings: Settings,
) -> None:
    """删除及审计一致提交；事件、共享问题和其他任务保留，重复删除不复活数据。"""

    store = finished_tasks(client, settings)
    store.set_review_feedback(1, 0, "helpful", "合成管理员")
    response = client.request("DELETE", "/api/jobs/1", headers=ADMIN, json=snapshot(store))
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "deleted", "job_id": 1,
                               "deleted_findings": 2, "deleted_issues": 1}
    assert client.get("/api/jobs/1", headers=ADMIN).status_code == 404
    assert client.get("/api/task-search", headers=ADMIN).json()["total"] == 1
    assert client.get("/api/review-issues", headers=ADMIN).json()["total"] == 1
    assert store.get_job(2)
    with store.connection() as db:
        for table in ("review_attempts", "review_feedback", "notification_deliveries",
                      "review_issue_occurrences", "review_stage_timings"):
            assert db.execute(f"SELECT COUNT(*) FROM {table} WHERE job_id=1").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM merge_events").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM job_identity").fetchone()[0] == 2
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        audit = db.execute("SELECT * FROM audit_log WHERE action='delete_review_job'").fetchone()
        assert audit and audit["object_id"] == 1 and audit["actor_name"] == "共享管理员"
    assert client.request("DELETE", "/api/jobs/1", headers=ADMIN, json={
        "expected_status": "complete", "expected_attempts": 1,
        "expected_finished_at": None,
    }).status_code == 404


def test_delete_requires_admin_and_exact_version(client: TestClient, settings: Settings) -> None:
    """无会话和只读账号不可删除；未知字段和过期快照不会越过服务端边界。"""

    store = finished_tasks(client, settings)
    expected = snapshot(store)
    assert client.request("DELETE", "/api/jobs/1", json=expected).status_code == 401
    assert client.request("DELETE", "/api/jobs/1", headers=ADMIN, json={
        **expected, "expected_attempts": 2,
    }).status_code == 409
    assert client.request("DELETE", "/api/jobs/1", headers=ADMIN, json={
        **expected, "force": True,
    }).status_code == 422
    create_user(client, "admin-test", "admin")
    create_user(client, "reader-test", "reader")
    enable_users(client)
    session = login(client, "reader-test")
    assert client.request("DELETE", "/api/jobs/1", json=expected, headers={
        "Authorization": f"Bearer {session['token']}",
    }).status_code == 403
    assert store.get_job(1)


@pytest.mark.parametrize("table,state", [
    ("notification_deliveries", "pending"), ("notification_deliveries", "sending"),
    ("review_attempts", "running"), ("review_jobs", "queued"),
    ("review_jobs", "running"),
])
def test_inflight_or_requeued_records_reject_delete(
    client: TestClient, settings: Settings, table: str, state: str,
) -> None:
    """确认后 Worker 领取、通知重发或重新排队时，删除必须整体拒绝。"""

    store = finished_tasks(client, settings)
    expected = snapshot(store)
    with store.connection() as db:
        key = "id" if table == "review_jobs" else "job_id"
        db.execute(f"UPDATE {table} SET status=? WHERE {key}=1", (state,))
    assert client.request("DELETE", "/api/jobs/1", headers=ADMIN,
                          json=expected).status_code == 409
    assert store.get_job(1)


def test_merge_conflict_and_audit_failure_roll_back(
    client: TestClient, settings: Settings,
) -> None:
    """无来源合并目标拒绝破坏人工关系；审计失败必须回滚所有级联删除。"""

    store = finished_tasks(client, settings)
    expected = DeleteTaskRequest(**snapshot(store))
    with store.connection() as db:
        unique = db.execute("SELECT id FROM review_issues WHERE path='only.py'").fetchone()[0]
        db.execute("""INSERT INTO review_issues(repository_id,fingerprint,status,path,content,
            merged_into_id) VALUES(1,'alias','merged','alias.py','合成合并来源',?)""", (unique,))
    with pytest.raises(ValueError, match="人工合并"):
        delete_task(store, 1, expected, actor_id=None, actor_name="合成管理员", correlation_id="")
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM review_jobs").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM review_issue_occurrences").fetchone()[0] == 3
        db.execute("DELETE FROM review_issues WHERE fingerprint='alias'")
        db.execute("""CREATE TRIGGER reject_delete_audit BEFORE INSERT ON audit_log
            WHEN NEW.action='delete_review_job' BEGIN SELECT RAISE(ABORT,'合成审计失败'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="合成审计失败"):
        delete_task(store, 1, expected, actor_id=None, actor_name="合成管理员", correlation_id="")
    assert store.get_job(1)
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM review_issue_occurrences").fetchone()[0] == 3


@pytest.mark.parametrize("state", ["queued", "running", "failed"])
def test_recovery_protects_active_and_cascades_terminal_sources(
    client: TestClient, settings: Settings, state: str,
) -> None:
    """独立补审等待和运行时拒绝；终态补审及预算证据随任务一并清理。"""

    store, enabled, _ = make_source(client, settings)
    recovery = enqueue(store, enabled, 1, command())
    with store.connection() as db:
        db.execute("UPDATE notification_deliveries SET status='sent'")
        db.execute("UPDATE review_recoveries SET status=? WHERE id=?", (state, recovery))
    response = client.request("DELETE", "/api/jobs/1", headers=ADMIN, json=snapshot(store))
    assert response.status_code == (200 if state == "failed" else 409), response.text
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM review_recoveries").fetchone()[0] == (
            0 if state == "failed" else 1)
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_artifact_operation_prevents_delete(client: TestClient, settings: Settings) -> None:
    """全量重审及补审持有工件锁时，终态快照也不能直接删除。"""

    store = finished_tasks(client, settings)
    expected = snapshot(store)
    with artifact_lock(settings.data_dir, 1) as acquired:
        assert acquired
        assert client.request("DELETE", "/api/jobs/1", headers=ADMIN,
                              json=expected).status_code == 409
    assert store.get_job(1)
