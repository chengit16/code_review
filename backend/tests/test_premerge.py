"""验证合并前版本队列、Webhook 鉴权及旧结果失效边界。"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from ocr_manager.config import Settings
from ocr_manager.premerge import (
    enqueue_premerge,
    finish_premerge,
    next_premerge,
    premerge_is_current,
)
from ocr_manager.storage import Store

ADMIN = {"X-Admin-Token": "test-admin-token"}
WEBHOOK = {"X-Gitlab-Token": "webhook-secret-123456", "X-Gitlab-Event": "Merge Request Hook"}


def create_repository(client: TestClient) -> int:
    """测试项目只保存在临时 SQLite，不访问外部 GitLab。"""

    response = client.post("/api/repositories", headers=ADMIN, json={
        "name": "合并前项目", "gitlab_url": "https://gitlab.example.test",
        "project_id": 42, "remote_url": "git@gitlab.example.test:team/repo.git",
        "target_branch": "main", "auth_kind": "secret",
        "webhook_token": "webhook-secret-123456",
    })
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def payload(head: str, action: str = "update") -> dict[str, object]:
    """构造 GitLab MR 更新所需的最小可信字段。"""

    return {"object_kind": "merge_request", "project": {"id": 42},
            "object_attributes": {"action": action, "iid": 7,
                                  "target_project_id": 42, "target_branch": "main",
                                  "last_commit": {"id": head}}}


def test_premerge_is_opt_in_and_versions_supersede(client: TestClient,
                                                    settings: Settings) -> None:
    """默认关闭；新 SHA 使运行中的旧版本失效，迟到结果不能复活。"""

    repo_id = create_repository(client)
    url = f"/api/webhooks/gitlab/{repo_id}"
    first = "a" * 40
    assert client.post(url, headers=WEBHOOK, json=payload(first)).json() == {
        "status": "ignored"}
    assert client.put(f"/api/repositories/{repo_id}/premerge", headers=ADMIN,
                      json={"enabled": True}).status_code == 200
    assert client.post(url, headers=WEBHOOK, json=payload(first)).json() == {
        "status": "queued"}
    assert client.post(url, headers=WEBHOOK, json=payload(first)).json() == {
        "status": "duplicate"}
    store = Store(settings.data_dir / "app.db")
    claimed = next_premerge(store)
    assert claimed is not None and claimed["attempts"] == 1
    assert premerge_is_current(store, claimed["id"])
    assert client.post(url, headers=WEBHOOK, json=payload("b" * 40)).json() == {
        "status": "queued"}
    assert not premerge_is_current(store, claimed["id"])
    finish_premerge(store, claimed["id"], "complete", first, {"comments": []},
                    "old/result.json", [], None)
    rows = client.get("/api/premerge-reviews", headers=ADMIN).json()
    assert [(row["head_sha"], row["status"]) for row in rows] == [
        ("b" * 40, "queued"), (first, "superseded")]
    assert rows[1]["result_json"] is None
    assert client.get(f"/api/premerge-reviews/{claimed['id']}", headers=ADMIN).json()[
        "status"] == "superseded"


def test_premerge_webhook_rejects_wrong_project_and_bad_sha(client: TestClient) -> None:
    """未鉴权载荷及错误项目/版本均不能生成合并前任务。"""

    repo_id = create_repository(client)
    client.put(f"/api/repositories/{repo_id}/premerge", headers=ADMIN,
               json={"enabled": True})
    url = f"/api/webhooks/gitlab/{repo_id}"
    assert client.post(url, headers={"X-Gitlab-Token": "wrong",
                                     "X-Gitlab-Event": "Merge Request Hook"},
                       json=payload("a" * 40)).status_code == 401
    wrong = payload("a" * 40)
    wrong["project"] = {"id": 999}
    assert client.post(url, headers=WEBHOOK, json=wrong).status_code == 403
    assert client.post(url, headers=WEBHOOK, json=payload("bad")).status_code == 422
    assert client.get("/api/premerge-reviews", headers=ADMIN).json() == []


def test_premerge_recover_and_current_result(client: TestClient, settings: Settings) -> None:
    """Worker 中断后只恢复当前版本，并保存可供页面读取的安全投影。"""

    repo_id = create_repository(client)
    client.put(f"/api/repositories/{repo_id}/premerge", headers=ADMIN,
               json={"enabled": True})
    store = Store(settings.data_dir / "app.db")
    assert enqueue_premerge(store, repo_id, 7, "a" * 40)
    claimed = next_premerge(store)
    assert claimed is not None
    store.recover()
    claimed = next_premerge(store)
    assert claimed is not None and claimed["attempts"] == 2
    result = {"comments": [{"path": "src/a.py", "content": "检查边界",
                            "severity": "high", "start_line": 2, "secret": "excluded"}],
              "manifest": {"terminal_state": "complete", "coverage": {}},
              "preview": {"reviewable_count": 1}}
    finish_premerge(store, claimed["id"], "complete", "b" * 40, result,
                    "runs/result.json", [{"path": "src/a.py"}], None)
    detail = client.get(f"/api/premerge-reviews/{claimed['id']}", headers=ADMIN).json()
    assert detail["status"] == "complete"
    assert json.loads(detail["result_json"])["comments"][0] == {
        "path": "src/a.py", "content": "检查边界", "severity": "high", "start_line": 2}
