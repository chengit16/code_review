"""验证跨 MR 问题身份、人工决策与旧任务补建，不访问外部服务。"""

from __future__ import annotations

from fastapi.testclient import TestClient
from ocr_manager.config import Settings
from ocr_manager.storage import Store

ADMIN = {"X-Admin-Token": "test-admin-token"}


def create_repository(client: TestClient) -> int:
    """问题生命周期只使用本地项目和合成评审结果。"""

    response = client.post("/api/repositories", headers=ADMIN, json={
        "name": "跟进项目", "gitlab_url": "https://gitlab.example.test",
        "project_id": 42, "remote_url": "git@gitlab.example.test:team/repo.git",
        "target_branch": "main", "auth_kind": "secret",
        "webhook_token": "local-secret-token-123",
    })
    assert response.status_code == 201
    return int(response.json()["id"])


def finish_with_finding(store: Store, repository_id: int, mr_iid: int,
                        sha: str, line: int = 4,
                        content: str = "缺少输入校验") -> int:
    """每个 MR 生成一条已确认输入的任务，行号变化不应复制相同问题。"""

    assert store.add_event(repository_id, mr_iid, f"delivery-{mr_iid}", sha, None)
    event = store.next_event()
    assert event is not None
    store.finish_event(event["id"], [sha], {sha: ("snapshot", "")}, None)
    job = store.next_job()
    assert job is not None
    store.finish_job(job["id"], "complete", None, {"comments": [{
        "path": "src/app.py", "start_line": line, "severity": "high",
        "category": "security", "content": content,
    }]}, None)
    return int(job["id"])


def test_issue_lifecycle_tracks_occurrences_without_inferred_fix(
    client: TestClient, settings: Settings,
) -> None:
    """相同开放问题跨 MR 复用；认可反馈和后续结果不推断修复。"""

    repository_id = create_repository(client)
    store = Store(settings.data_dir / "app.db")
    first = finish_with_finding(store, repository_id, 7, "a" * 40)
    second = finish_with_finding(store, repository_id, 8, "b" * 40, 9)
    listing = client.get("/api/review-issues", headers=ADMIN).json()
    assert listing["total"] == 1
    issue_id = listing["items"][0]["id"]
    assert listing["items"][0]["occurrence_count"] == 2
    assert client.get(f"/api/jobs/{second}", headers=ADMIN).json()["issue_ids"] == {
        "0": issue_id}
    assert client.put(f"/api/jobs/{first}/feedback/0", headers=ADMIN,
                      json={"verdict": "helpful"}).status_code == 200
    assert client.get(f"/api/review-issues/{issue_id}", headers=ADMIN).json()[
        "status"] == "open"
    assert client.patch(f"/api/review-issues/{issue_id}", json={"status": "fixed"}
                        ).status_code == 401
    changed = client.patch(f"/api/review-issues/{issue_id}", headers=ADMIN,
                           json={"status": "fixed", "note": "已核对修复"})
    assert changed.status_code == 200
    detail = client.get(f"/api/review-issues/{issue_id}", headers=ADMIN).json()
    assert detail["events"][0]["actor"] == "共享管理员"
    assert detail["events"][0]["note"] == "已核对修复"
    third = finish_with_finding(store, repository_id, 9, "c" * 40)
    assert third > second
    assert client.get("/api/review-issues?status=open", headers=ADMIN).json()["total"] == 1
    assert client.get("/api/review-issues?status=fixed", headers=ADMIN).json()["total"] == 1
    # 相同发现再次出现也不会自动重开已经人工关闭的历史问题。
    new_issue = client.get("/api/review-issues?status=open", headers=ADMIN).json()[
        "items"][0]["id"]
    assert new_issue != issue_id
    assert client.patch(f"/api/review-issues/{issue_id}", headers=ADMIN,
                        json={"status": "open"}).status_code == 200
    assert client.post(f"/api/review-issues/{new_issue}/merge", headers=ADMIN,
                       json={"target_id": issue_id}).status_code == 200
    merged = client.get(f"/api/review-issues/{issue_id}", headers=ADMIN).json()
    assert len(merged["occurrences"]) == 3
    assert client.get(f"/api/review-issues/{new_issue}", headers=ADMIN).json()[
        "merged_into_id"] == issue_id
    fourth = finish_with_finding(store, repository_id, 10, "d" * 40,
                                 content="缺少边界校验")
    different_issue = client.get(f"/api/jobs/{fourth}", headers=ADMIN).json()[
        "issue_ids"]["0"]
    assert different_issue != issue_id
    assert client.post(f"/api/review-issues/{different_issue}/merge", headers=ADMIN,
                       json={"target_id": issue_id}).status_code == 200
    fifth = finish_with_finding(store, repository_id, 11, "e" * 40,
                                content="缺少边界校验")
    assert client.get(f"/api/jobs/{fifth}", headers=ADMIN).json()["issue_ids"] == {
        "0": issue_id}
    assert client.get("/api/review-issues?status=open", headers=ADMIN).json()["total"] == 1
    assert client.delete(f"/api/repositories/{repository_id}", headers=ADMIN).status_code == 200
    assert client.get("/api/review-issues", headers=ADMIN).json()["total"] == 0


def test_backfill_is_idempotent_and_only_uses_current_result(
    client: TestClient, settings: Settings,
) -> None:
    """迁移中断后可重新补建；当前结果为空的旧尝试不推断问题已修复。"""

    repository_id = create_repository(client)
    store = Store(settings.data_dir / "app.db")
    job_id = finish_with_finding(store, repository_id, 7, "a" * 40)
    with store.connection() as db:
        db.execute("DELETE FROM review_issue_occurrences")
        db.execute("DELETE FROM review_issue_events")
        db.execute("DELETE FROM review_issues")
        db.execute("UPDATE review_issue_backfill SET completed=0 WHERE id=1")
    store.migrate()
    store.migrate()
    detail = client.get(f"/api/jobs/{job_id}", headers=ADMIN).json()
    assert len(detail["issue_ids"]) == 1
    assert client.get("/api/review-issues", headers=ADMIN).json()["total"] == 1
