"""验证保存前结构预检与版本绑定的连接检查状态。"""

from __future__ import annotations

from fastapi.testclient import TestClient
from ocr_manager.config import Settings
from ocr_manager.storage import Store


def test_preflight_does_not_save_and_checks_source(client: TestClient, settings: Settings) -> None:
    """预检不建立项目，错误来源在保存前反馈。"""

    headers = {"X-Admin-Token": settings.admin_token}
    payload = {"name": "试点", "gitlab_url": "https://gitlab.example.test", "project_id": 42,
               "remote_url": "git@gitlab.example.test:a/b.git", "target_branch": "main",
               "path_with_namespace": "a/b"}
    assert client.post("/api/repositories/preflight", json=payload).status_code == 401
    response = client.post("/api/repositories/preflight", headers=headers, json=payload)
    assert response.status_code == 200
    assert client.get("/api/repositories", headers=headers).json() == []
    bad = payload | {"remote_url": "git@other.example.test:a/b.git"}
    assert client.post("/api/repositories/preflight", headers=headers, json=bad).status_code == 422
    saved = client.post("/api/repositories", headers=headers, json=payload)
    assert saved.status_code == 201
    assert client.post("/api/repositories/preflight", headers=headers,
                       json=payload).status_code == 409


def test_readiness_invalidates_after_config_change(client: TestClient, settings: Settings) -> None:
    """配置更新后同一秒内旧连接测试也不得误判为已验证。"""

    headers = {"X-Admin-Token": settings.admin_token}
    repository = client.post("/api/repositories", headers=headers, json={
        "name": "试点", "gitlab_url": "https://gitlab.example.test", "project_id": 42,
        "remote_url": "git@gitlab.example.test:a/b.git", "target_branch": "main",
    }).json()
    store = Store(settings.data_dir / "app.db")
    for kind in ("git", "gitlab"):
        check_id = store.enqueue_connection_check(kind, repository["id"])
        assert check_id
        claimed = store.next_connection_check()
        assert claimed is not None
        store.finish_connection_check(check_id, None)
    readiness = client.get("/api/repository-readiness", headers=headers).json()[0]
    assert readiness["status"] == "ready"
    assert client.patch(f"/api/repositories/{repository['id']}", headers=headers,
                        json={"name": "改名"}).status_code == 200
    readiness = client.get("/api/repository-readiness", headers=headers).json()[0]
    assert readiness["status"] == "needs_check"
