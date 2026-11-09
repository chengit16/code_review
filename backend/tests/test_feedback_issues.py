"""验证价值反馈与共享问题处置解耦；仅使用合成终态发现和临时 SQLite。"""

from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient
from ocr_manager.config import Settings
from ocr_manager.storage import Store
from test_auth import create_user, enable_users, login
from test_review_issues import ADMIN, create_repository, finish_with_finding


@pytest.mark.parametrize("verdict", ["helpful", "false_positive", "ignored"])
def test_feedback_does_not_close_issue_and_undo_does_not_reopen(
    client: TestClient, settings: Settings, verdict: str,
) -> None:
    """三种价值反馈只记录评价，不新增问题处理审计。"""

    repository_id = create_repository(client)
    store = Store(settings.data_dir / "app.db")
    job_id = finish_with_finding(store, repository_id, 7, "a" * 40)
    job_url = f"/api/jobs/{job_id}"
    url = f"{job_url}/feedback/0"
    issue_id = client.get(job_url, headers=ADMIN).json()["issue_ids"]["0"]
    issue_url = f"/api/review-issues/{issue_id}"
    before = client.get(issue_url, headers=ADMIN).json()
    assert client.put(url, json={"verdict": verdict}).status_code == 401
    for _ in range(2):
        assert client.put(url, headers=ADMIN, json={"verdict": verdict}).status_code == 200
    assert client.get(issue_url, headers=ADMIN).json() == before
    assert client.get(job_url, headers=ADMIN).json()["feedback"] == {"0": verdict}
    assert client.delete(url, headers=ADMIN).status_code == 200
    assert client.get(issue_url, headers=ADMIN).json() == before
    assert client.get(job_url, headers=ADMIN).json()["feedback"] == {}


def test_switching_feedback_preserves_independent_shared_decisions(
    client: TestClient, settings: Settings,
) -> None:
    """共享问题已关闭时，改选和撤销任何评价都不推翻人工决定。"""

    repository_id = create_repository(client)
    store = Store(settings.data_dir / "app.db")
    first = finish_with_finding(store, repository_id, 7, "a" * 40)
    second = finish_with_finding(store, repository_id, 8, "b" * 40)
    issue_id = client.get(f"/api/jobs/{first}", headers=ADMIN).json()["issue_ids"]["0"]
    issue_url = f"/api/review-issues/{issue_id}"
    for status in ("fixed", "ignored", "false_positive", "open"):
        assert client.post(issue_url, headers=ADMIN, json={"status": status}).status_code == 200
        before = client.get(issue_url, headers=ADMIN).json()
        for verdict in ("helpful", "false_positive", "ignored"):
            for job in (first, second):
                url = f"/api/jobs/{job}/feedback/0"
                assert client.put(url, headers=ADMIN, json={"verdict": verdict}).status_code == 200
                assert client.delete(url, headers=ADMIN).status_code == 200
        assert client.get(issue_url, headers=ADMIN).json() == before


def test_feedback_mirror_failure_rolls_back_value_only(
    client: TestClient, settings: Settings,
) -> None:
    """稳定镜像失败时整次反馈回滚，问题状态保持不变。"""

    repository_id = create_repository(client)
    store = Store(settings.data_dir / "app.db")
    job_id = finish_with_finding(store, repository_id, 7, "a" * 40)
    with store.connection() as db:
        db.execute("""CREATE TRIGGER reject_value BEFORE INSERT ON review_finding_feedback
            BEGIN SELECT RAISE(ABORT,'合成镜像故障'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="合成镜像故障"):
        store.set_review_feedback(job_id, 0, "ignored", "测试操作者")
    detail = client.get(f"/api/jobs/{job_id}", headers=ADMIN).json()
    assert detail["feedback"] == {} and detail["issue_statuses"] == {"0": "open"}


def test_reader_cannot_write_feedback_and_actor_comes_from_session(
    client: TestClient, settings: Settings,
) -> None:
    """真实读者只有查询权限，管理员反馈镜像记录真实身份。"""

    repository_id = create_repository(client)
    store = Store(settings.data_dir / "app.db")
    job_id = finish_with_finding(store, repository_id, 7, "a" * 40)
    url = f"/api/jobs/{job_id}/feedback/0"
    create_user(client, "alice", "admin")
    create_user(client, "bob", "reader")
    enable_users(client)
    reader = {"Authorization": f"Bearer {login(client, 'bob')['token']}"}
    admin = {"Authorization": f"Bearer {login(client, 'alice')['token']}"}
    assert client.put(url, headers=reader, json={"verdict": "ignored"}).status_code == 403
    assert client.put(url, headers=admin, json={"verdict": "ignored"}).status_code == 200
    assert client.delete(url, headers=reader).status_code == 403
    with store.connection() as db:
        assert db.execute("SELECT actor FROM review_finding_feedback").fetchone()[0] == "alice"
    assert client.get(f"/api/jobs/{job_id}", headers=reader).json()["issue_statuses"] == {
        "0": "open"}
