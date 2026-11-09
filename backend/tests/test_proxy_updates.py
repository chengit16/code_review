"""验证穿透兼容入口与原 PATCH 共用业务及授权，不连接真实外部服务。"""

from __future__ import annotations

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from ocr_manager.config import Settings
from ocr_manager.storage import Store

ADMIN = {"X-Admin-Token": "test-admin-token"}
UPDATE_PATHS = (
    "/api/notification-targets/999",
    "/api/repositories/999",
    "/api/model-profiles/999",
    "/api/auth/users/999",
    "/api/review-issues/999",
)


def test_all_patch_routes_share_post_handler_and_dependencies(client: TestClient) -> None:
    """新增 PATCH 时也须提供 POST，且不能绕过原依赖、请求体模型或处理函数。"""

    routes = [route for route in client.app.routes if isinstance(route, APIRoute)]
    patches = [route for route in routes if "PATCH" in route.methods]
    assert len(patches) == 5
    for patch in patches:
        post = next(route for route in routes
                    if route.path == patch.path and "POST" in route.methods)
        assert post.endpoint is patch.endpoint
        assert post.dependencies == patch.dependencies
        schema = client.app.openapi()["paths"][patch.path]
        assert schema["post"]["requestBody"] == schema["patch"]["requestBody"]


@pytest.mark.parametrize("path", UPDATE_PATHS)
def test_post_updates_require_authentication(client: TestClient, path: str) -> None:
    """缺少管理凭据时拒绝兼容写入，不将 POST 当成公开入口。"""

    assert client.post(path, json={}).status_code == 401


def test_post_updates_reject_readers(client: TestClient) -> None:
    """账号模式中只读用户不能使用任一 POST 更新入口。"""

    for username, role in (("admin-user", "admin"), ("reader-user", "reader")):
        assert client.post("/api/auth/users", headers=ADMIN, json={
            "username": username, "password": "synthetic-password-123", "role": role,
        }).status_code == 201
    assert client.put("/api/auth/mode", headers=ADMIN,
                      json={"users_enabled": True}).status_code == 200
    session = client.post("/api/auth/login", json={
        "username": "reader-user", "password": "synthetic-password-123",
    }).json()
    for path in UPDATE_PATHS:
        assert client.post(path, headers={"Authorization": f"Bearer {session['token']}"},
                           json={}).status_code == 403


@pytest.mark.parametrize("method", ["PATCH", "POST"])
def test_repository_updates_preserve_history_and_audit(
    client: TestClient, settings: Settings, method: str,
) -> None:
    """兼容保存和启停保留项目 Token，审计仍记录实际方法与资源。"""

    created = client.post("/api/repositories", headers=ADMIN, json={
        "name": "合成项目", "gitlab_url": "https://gitlab.example.test",
        "project_id": 42, "remote_url": "https://gitlab.example.test/team/repo.git",
        "target_branch": "main", "auth_kind": "secret", "gitlab_token": "synthetic-token",
    })
    assert created.status_code == 201
    repository_id = created.json()["id"]
    store = Store(settings.data_dir / "app.db")
    before = store.get_repository(repository_id)
    assert before is not None
    response = client.request(method, f"/api/repositories/{repository_id}", headers=ADMIN,
                              json={"name": "合成修改", "enabled": False})
    assert response.status_code == 200
    after = store.get_repository(repository_id)
    assert after is not None and after["name"] == "合成修改" and after["enabled"] == 0
    assert after["gitlab_token_ciphertext"] == before["gitlab_token_ciphertext"]
    audit = client.get("/api/audit-logs", headers=ADMIN).json()["items"][0]
    assert audit["action"] == f"{method} /api/repositories/{{repository_id}}"
    assert audit["outcome"] == "success" and audit["object_id"] == repository_id
    assert "synthetic-token" not in response.text
