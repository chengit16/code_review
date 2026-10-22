"""验证卡片处理、撤销、审计及共享问题的事务边界，只使用本地合成结果。"""

from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient
from ocr_manager.config import Settings
from ocr_manager.storage import Store
from test_auth import create_user, enable_users, login
from test_review_issues import ADMIN, create_repository, finish_with_finding


@pytest.mark.parametrize("verdict,expected", [("false_positive", "ignored"), ("fixed", "fixed")])
def test_feedback_closes_issue_and_undo_reopens(
    client: TestClient, settings: Settings, verdict: str, expected: str,
) -> None:
    """误报和修复即时闭环，重复保存不重复审计，撤销恢复待处理。"""

    repository_id = create_repository(client)
    store = Store(settings.data_dir / "app.db")
    job_id = finish_with_finding(store, repository_id, 7, "a" * 40)
    job_url = f"/api/jobs/{job_id}"
    feedback_url = f"{job_url}/feedback/0"
    issue_id = client.get(job_url, headers=ADMIN).json()["issue_ids"]["0"]
    issue_url = f"/api/review-issues/{issue_id}"

    assert client.put(feedback_url, json={"verdict": "false_positive"}).status_code == 401
    assert client.get(issue_url, headers=ADMIN).json()["status"] == "open"
    for _ in range(2):
        assert client.put(feedback_url, headers=ADMIN,
                          json={"verdict": verdict}).status_code == 200
    detail = client.get(issue_url, headers=ADMIN).json()
    assert detail["status"] == expected and detail["closed_at"] is not None
    assert len(detail["events"]) == 2
    assert detail["events"][0]["actor"] == "共享管理员"
    assert f"任务 #{job_id}" in detail["events"][0]["note"]
    assert client.get(job_url, headers=ADMIN).json()["issue_statuses"] == {"0": expected}
    assert client.get("/api/review-issues?status=open", headers=ADMIN).json()["total"] == 0
    assert client.delete(feedback_url).status_code == 401
    assert client.delete(feedback_url, headers=ADMIN).status_code == 200
    reopened = client.get(issue_url, headers=ADMIN).json()
    assert reopened["status"] == "open" and reopened["closed_at"] is None
    assert client.get(job_url, headers=ADMIN).json()["feedback"] == {}


def test_switching_verdict_and_historical_mark_can_sync(
    client: TestClient, settings: Settings,
) -> None:
    """旧反馈原地重新确认可关闭问题；改为有帮助会撤销本卡片的处理。"""

    repository_id = create_repository(client)
    store = Store(settings.data_dir / "app.db")
    job_id = finish_with_finding(store, repository_id, 7, "a" * 40)
    url = f"/api/jobs/{job_id}/feedback/0"
    with store.connection() as db:
        db.execute("INSERT INTO review_feedback(job_id,comment_index,verdict) VALUES(?,0,?)",
                   (job_id, "false_positive"))
    for verdict, expected in (("false_positive", "ignored"), ("fixed", "fixed"),
                              ("helpful", "open")):
        assert client.put(url, headers=ADMIN, json={"verdict": verdict}).status_code == 200
        assert client.get(f"/api/jobs/{job_id}", headers=ADMIN).json()[
            "issue_statuses"] == {"0": expected}


def test_feedback_preserves_other_decisions_and_resolves_merged_target(
    client: TestClient, settings: Settings,
) -> None:
    """跨任务认可或撤销不能推翻其他卡片、人工入口及合并目标的关闭决定。"""

    repository_id = create_repository(client)
    store = Store(settings.data_dir / "app.db")
    first = finish_with_finding(store, repository_id, 7, "a" * 40)
    second = finish_with_finding(store, repository_id, 8, "b" * 40, content="另一个问题")
    first_id = client.get(f"/api/jobs/{first}", headers=ADMIN).json()["issue_ids"]["0"]
    second_id = client.get(f"/api/jobs/{second}", headers=ADMIN).json()["issue_ids"]["0"]
    assert client.post(f"/api/review-issues/{first_id}/merge", headers=ADMIN,
                       json={"target_id": second_id}).status_code == 200
    first_url = f"/api/jobs/{first}/feedback/0"
    second_url = f"/api/jobs/{second}/feedback/0"
    issue_url = f"/api/review-issues/{second_id}"
    assert client.put(first_url, headers=ADMIN,
                      json={"verdict": "false_positive"}).status_code == 200
    assert client.get(issue_url, headers=ADMIN).json()["status"] == "ignored"
    assert client.get(f"/api/review-issues/{first_id}", headers=ADMIN).json()["status"] == "merged"
    assert client.put(second_url, headers=ADMIN, json={"verdict": "helpful"}).status_code == 200
    assert client.delete(second_url, headers=ADMIN).status_code == 200
    assert client.get(issue_url, headers=ADMIN).json()["status"] == "ignored"
    assert client.patch(issue_url, headers=ADMIN, json={"status": "fixed"}).status_code == 200
    assert client.delete(first_url, headers=ADMIN).status_code == 200
    assert client.get(issue_url, headers=ADMIN).json()["status"] == "fixed"
    assert client.put(first_url, headers=ADMIN,
                      json={"verdict": "false_positive"}).status_code == 200
    assert client.get(issue_url, headers=ADMIN).json()["status"] == "fixed"


def test_retry_feedback_only_handles_current_attempt(
    client: TestClient, settings: Settings,
) -> None:
    """重审后相同索引的新发现不能关闭旧尝试关联的问题。"""

    repository_id = create_repository(client)
    store = Store(settings.data_dir / "app.db")
    job_id = finish_with_finding(store, repository_id, 7, "a" * 40)
    old_id = client.get(f"/api/jobs/{job_id}", headers=ADMIN).json()["issue_ids"]["0"]
    assert store.retry_job(job_id) == job_id
    assert store.next_job() is not None
    store.finish_job(job_id, "complete", None,
                     {"comments": [{"path": "other.py", "content": "新发现"}]}, None)
    assert client.put(f"/api/jobs/{job_id}/feedback/0", headers=ADMIN,
                      json={"verdict": "fixed"}).status_code == 200
    assert client.get(f"/api/review-issues/{old_id}", headers=ADMIN).json()["status"] == "open"
    detail = client.get(f"/api/jobs/{job_id}", headers=ADMIN).json()
    assert detail["issue_statuses"] == {"0": "fixed"}


def test_issue_sync_failure_rolls_back_feedback(
    client: TestClient, settings: Settings,
) -> None:
    """问题审计写入失败时，反馈和状态一起回滚，不能产生只更新一半的事实。"""

    repository_id = create_repository(client)
    store = Store(settings.data_dir / "app.db")
    job_id = finish_with_finding(store, repository_id, 7, "a" * 40)
    with store.connection() as db:
        db.execute("""CREATE TRIGGER reject_issue_event BEFORE INSERT ON review_issue_events
            BEGIN SELECT RAISE(ABORT,'合成审计故障'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="合成审计故障"):
        store.set_review_feedback(job_id, 0, "false_positive", "测试操作者")
    detail = client.get(f"/api/jobs/{job_id}", headers=ADMIN).json()
    assert detail["feedback"] == {} and detail["issue_statuses"] == {"0": "open"}


def test_reader_cannot_close_or_reopen_and_actor_comes_from_session(
    client: TestClient, settings: Settings,
) -> None:
    """联动仍由服务端管理员权限保护，审计使用真实登录身份。"""

    repository_id = create_repository(client)
    store = Store(settings.data_dir / "app.db")
    job_id = finish_with_finding(store, repository_id, 7, "a" * 40)
    url = f"/api/jobs/{job_id}/feedback/0"
    create_user(client, "alice", "admin")
    create_user(client, "bob", "reader")
    enable_users(client)
    reader = {"Authorization": f"Bearer {login(client, 'bob')['token']}"}
    admin = {"Authorization": f"Bearer {login(client, 'alice')['token']}"}
    assert client.put(url, headers=reader, json={"verdict": "fixed"}).status_code == 403
    assert client.put(url, headers=admin, json={"verdict": "false_positive"}).status_code == 200
    assert client.delete(url, headers=reader).status_code == 403
    job = client.get(f"/api/jobs/{job_id}", headers=reader).json()
    assert job["issue_statuses"] == {"0": "ignored"}
    issue = client.get(f"/api/review-issues/{job['issue_ids']['0']}", headers=reader).json()
    assert issue["events"][0]["actor"] == "alice"
