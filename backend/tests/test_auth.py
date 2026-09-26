"""验证多用户会话、只读授权、管理员保护和操作者审计。"""

from __future__ import annotations

from fastapi.testclient import TestClient
from ocr_manager.config import Settings
from ocr_manager.storage import Store

ADMIN = {"X-Admin-Token": "test-admin-token"}


def create_user(client: TestClient, username: str, role: str) -> dict[str, object]:
    """用共享管理员入口建立账号，账号模式启用后不再接受共享口令。"""

    response = client.post("/api/auth/users", headers=ADMIN, json={
        "username": username, "password": "testing-password-123", "role": role,
    })
    assert response.status_code == 201, response.text
    return response.json()


def enable_users(client: TestClient) -> None:
    """显式切换模式，供权限场景复用。"""

    response = client.put("/api/auth/mode", headers=ADMIN, json={"users_enabled": True})
    assert response.status_code == 200, response.text


def login(client: TestClient, username: str) -> dict[str, object]:
    """登录凭据只在测试内存中保留。"""

    response = client.post("/api/auth/login", json={
        "username": username, "password": "testing-password-123",
    })
    assert response.status_code == 200, response.text
    return response.json()


def test_users_mode_requires_admin_and_enforces_reader(client: TestClient,
                                                        settings: Settings) -> None:
    """只读会话可查看任务，不能修改项目或读取 Webhook Token。"""

    assert client.put("/api/auth/mode", headers=ADMIN,
                      json={"users_enabled": True}).status_code == 409
    administrator = create_user(client, "alice", "admin")
    reader = create_user(client, "bob", "reader")
    store = Store(settings.data_dir / "app.db")
    with store.connection() as db:
        hashes = [row[0] for row in db.execute("SELECT password_hash FROM management_users")]
    assert all("testing-password-123" not in value for value in hashes)
    assert "password_hash" not in administrator
    assert reader["role"] == "reader"
    enable_users(client)
    assert client.get("/api/health").json()["auth_mode"] == "users"
    assert client.get("/api/repositories", headers=ADMIN).status_code == 401
    reader_session = login(client, "bob")
    reader_headers = {"Authorization": f"Bearer {reader_session['token']}"}
    assert client.get("/api/repositories", headers=reader_headers).status_code == 200
    assert client.post("/api/repositories", headers=reader_headers, json={}).status_code == 403
    assert client.get("/api/repositories/1/webhook-token", headers=reader_headers
                      ).status_code == 403
    assert client.get("/api/auth/users", headers=reader_headers).status_code == 403
    assert client.post("/api/auth/logout", headers=reader_headers).status_code == 200
    assert client.get("/api/repositories", headers=reader_headers).status_code == 401


def test_last_admin_protected_and_role_change_revokes_session(client: TestClient) -> None:
    """最后管理员不能降权；被修改用户的旧会话立即失效。"""

    admin_user = create_user(client, "alice", "admin")
    reader = create_user(client, "bob", "reader")
    enable_users(client)
    admin_session = login(client, "alice")
    admin_headers = {"Authorization": f"Bearer {admin_session['token']}"}
    assert client.patch(f"/api/auth/users/{admin_user['id']}", headers=admin_headers,
                        json={"role": "reader"}).status_code == 409
    assert client.delete(f"/api/auth/users/{admin_user['id']}", headers=admin_headers
                         ).status_code == 409
    assert client.patch(f"/api/auth/users/{reader['id']}", headers=admin_headers,
                        json={"role": "admin"}).status_code == 200
    assert client.get("/api/auth/me", headers=admin_headers).json()["username"] == "alice"
    assert client.patch(f"/api/auth/users/{admin_user['id']}", headers=admin_headers,
                        json={"role": "reader"}).status_code == 200
    assert client.get("/api/repositories", headers=admin_headers).status_code == 401
    new_session = login(client, "alice")
    new_headers = {"Authorization": f"Bearer {new_session['token']}"}
    assert client.get("/api/auth/me", headers=new_headers).json()["role"] == "reader"
    bob_session = login(client, "bob")
    bob_headers = {"Authorization": f"Bearer {bob_session['token']}"}
    assert client.delete(f"/api/auth/users/{admin_user['id']}", headers=bob_headers
                         ).status_code == 200
    assert client.get("/api/repositories", headers=new_headers).status_code == 401


def test_login_lockout_and_actor_audit(client: TestClient, settings: Settings) -> None:
    """连续错误有有限锁定，成功的账号操作可追溯到操作者。"""

    create_user(client, "alice", "admin")
    enable_users(client)
    for _ in range(5):
        assert client.post("/api/auth/login", json={"username": "alice",
                                                      "password": "wrong"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "alice",
                                                  "password": "testing-password-123"}
                       ).status_code == 401
    store = Store(settings.data_dir / "app.db")
    with store.connection() as db:
        attempts = db.execute("SELECT failed_attempts FROM management_users WHERE username='alice'"
                              ).fetchone()[0]
        assert attempts == 5
        db.execute("UPDATE management_users SET locked_until=datetime('now','-1 minute') "
                   "WHERE username='alice'")
    session = login(client, "alice")
    headers = {"Authorization": f"Bearer {session['token']}"}
    created = client.post("/api/auth/users", headers=headers, json={
        "username": "charlie", "password": "testing-password-123", "role": "reader",
    })
    assert created.status_code == 201
    audit = client.get("/api/audit-logs", headers=headers).json()
    assert audit[0]["actor_name"] == "alice"
    assert audit[0]["actor_id"] == session["user"]["id"]
    assert "testing-password-123" not in str(audit)
