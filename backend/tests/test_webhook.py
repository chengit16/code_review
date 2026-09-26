"""保护 GitLab webhook 鉴权、合并过滤、密钥不回显和重复投递。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from typing import Any

from fastapi.testclient import TestClient
from ocr_manager.config import Settings
from ocr_manager.storage import Store


def create_repository(client: TestClient, token: str, kind: str = "secret") -> int:
    """通过真实管理 API 建立测试项目，确保入站鉴权使用密文配置。"""

    response = client.post(
        "/api/repositories",
        headers={"X-Admin-Token": "test-admin-token"},
        json={
            "name": "示例项目",
            "gitlab_url": "https://gitlab.example.test",
            "project_id": 42,
            "remote_url": "git@gitlab.example.test:team/repo.git",
            "target_branch": "main",
            "auth_kind": kind,
            "webhook_token": token,
            "feishu_webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/example",
        },
    )
    assert response.status_code == 201, response.text
    assert "webhook_secret" not in response.json()
    assert "feishu_webhook" not in response.json()
    return int(response.json()["id"])


def merge_payload(action: str = "merge", branch: str = "main") -> dict[str, Any]:
    """构造只含 GitLab 官方合并事件关键字段的合成载荷。"""

    return {
        "object_kind": "merge_request",
        "project": {"id": 42},
        "object_attributes": {
            "action": action,
            "iid": 7,
            "target_project_id": 42,
            "target_branch": branch,
            "merge_commit_sha": "a" * 40,
        },
    }


def test_secret_webhook_only_queues_matching_merge(client: TestClient) -> None:
    """非合并事件不入队，重复合并只保存一次。"""

    repository_id = create_repository(client, "local-secret-token-123")
    url = f"/api/webhooks/gitlab/{repository_id}"
    headers = {"X-Gitlab-Token": "local-secret-token-123", "X-Gitlab-Event": "Merge Request Hook"}
    assert client.post(url, headers=headers, json=merge_payload("update")).json() == {
        "status": "ignored"
    }
    assert client.post(url, headers=headers, json=merge_payload(branch="develop")).json() == {
        "status": "ignored"
    }
    assert client.post(url, headers=headers, json=merge_payload()).json() == {"status": "queued"}
    assert client.post(url, headers=headers, json=merge_payload()).json() == {"status": "duplicate"}
    events = client.get("/api/events", headers={"X-Admin-Token": "test-admin-token"}).json()
    assert len(events) == 1
    assert events[0]["mr_iid"] == 7


def test_project_can_be_saved_before_feishu_hook(client: TestClient) -> None:
    """项目配置与飞书通知配置可分开保存，响应只暴露 Hook 是否已配置。"""

    admin = {"X-Admin-Token": "test-admin-token"}
    project = {
        "name": "先接入项目",
        "gitlab_url": "https://gitlab.example.test",
        "project_id": 43,
        "remote_url": "git@gitlab.example.test:team/without-feishu.git",
        "target_branch": "main",
        "auth_kind": "secret",
        "webhook_token": "local-secret-token-123",
    }
    created = client.post("/api/repositories", headers=admin, json=project)
    assert created.status_code == 201, created.text
    assert created.json()["has_feishu_webhook"] is False
    repository_id = created.json()["id"]

    configured = client.patch(
        f"/api/repositories/{repository_id}",
        headers=admin,
        json={"feishu_webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/example"},
    )
    assert configured.status_code == 200, configured.text
    assert configured.json()["has_feishu_webhook"] is True
    assert "feishu_webhook" not in configured.json()


def test_project_and_feishu_hook_deletion_are_separate(
    client: TestClient, settings: Settings
) -> None:
    """Hook 可独立删除；项目即使已有完整处理历史也允许级联删除。"""

    repository_id = create_repository(client, "local-secret-token-123")
    admin = {"X-Admin-Token": "test-admin-token"}
    cleared = client.delete(f"/api/repositories/{repository_id}/feishu-hook", headers=admin)
    assert cleared.status_code == 200
    assert cleared.json()["has_feishu_webhook"] is False
    assert client.get("/api/repositories", headers=admin).json()[0]["id"] == repository_id
    assert (
        client.delete(f"/api/repositories/{repository_id}/feishu-hook", headers=admin).status_code
        == 200
    )

    assert client.post(
        f"/api/repositories/{repository_id}/mrs/7/enqueue", headers=admin
    ).json() == {"status": "queued"}
    store = Store(settings.data_dir / "app.db")
    check_id = store.enqueue_connection_check("git", repository_id)
    event = store.next_event()
    assert check_id is not None
    assert event is not None
    commit_sha = "a" * 40
    store.finish_event(event["id"], [commit_sha], {commit_sha: ("config", "")}, None)
    job = store.next_job()
    assert job is not None
    store.finish_job(job["id"], "complete", "result.json", {"comments": []}, None)
    delivery = store.next_delivery()
    assert delivery is not None

    deleted = client.delete(f"/api/repositories/{repository_id}", headers=admin)
    assert deleted.status_code == 200
    assert client.get("/api/repositories", headers=admin).json() == []
    assert client.get("/api/events", headers=admin).json() == []
    assert client.get("/api/jobs", headers=admin).json() == []
    with store.connection() as db:
        for table in (
            "merge_events",
            "review_jobs",
            "review_attempts",
            "notification_deliveries",
            "connection_checks",
        ):
            assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0

    # Worker 可能在删除前已经领取记录；迟到的回写必须安全结束，不能让进程退出。
    store.finish_connection_check(check_id, None)
    store.finish_event(event["id"], [commit_sha], {commit_sha: ("config", "")}, None)
    store.finish_job(job["id"], "complete", None, {"comments": []}, None)
    store.defer_job(job["id"], "临时失败")
    store.finish_delivery(delivery["id"], None)


def test_project_without_history_can_be_deleted(client: TestClient) -> None:
    """未产生事件、评审或连接测试的项目允许清理。"""

    repository_id = create_repository(client, "local-secret-token-123")
    response = client.delete(
        f"/api/repositories/{repository_id}", headers={"X-Admin-Token": "test-admin-token"}
    )
    assert response.status_code == 200
    assert (
        client.get("/api/repositories", headers={"X-Admin-Token": "test-admin-token"}).json() == []
    )


def test_webhook_rejects_bad_secret_and_project(client: TestClient) -> None:
    """不能用已知回调地址绕过密钥或替换 GitLab 项目 ID。"""

    repository_id = create_repository(client, "local-secret-token-123")
    url = f"/api/webhooks/gitlab/{repository_id}"
    assert client.post(url, json=merge_payload()).status_code == 401
    payload = merge_payload()
    payload["project"]["id"] = 99
    response = client.post(
        url,
        headers={
            "X-Gitlab-Token": "local-secret-token-123",
            "X-Gitlab-Event": "Merge Request Hook",
        },
        json=payload,
    )
    assert response.status_code == 403


def test_webhook_rejects_boolean_mr_iid(client: TestClient) -> None:
    """JSON true 在 Python 中属于 int，但不能作为真实 MR IID 入队。"""

    repository_id = create_repository(client, "local-secret-token-123")
    payload = merge_payload()
    payload["object_attributes"]["iid"] = True
    response = client.post(
        f"/api/webhooks/gitlab/{repository_id}",
        headers={
            "X-Gitlab-Token": "local-secret-token-123",
            "X-Gitlab-Event": "Merge Request Hook",
        },
        json=payload,
    )
    assert response.status_code == 422


def test_webhook_rejects_oversized_body_before_authentication(client: TestClient) -> None:
    """请求体超过上限时立即拒绝，不能把大载荷保留到签名解析阶段。"""

    repository_id = create_repository(client, "local-secret-token-123")
    response = client.post(
        f"/api/webhooks/gitlab/{repository_id}",
        headers={"X-Gitlab-Token": "local-secret-token-123"},
        content=b"x" * (1024 * 1024 + 1),
    )
    assert response.status_code == 413
    assert client.get("/api/events", headers={"X-Admin-Token": "test-admin-token"}).json() == []


def test_signing_webhook_checks_raw_body_and_timestamp(client: TestClient) -> None:
    """签名必须覆盖原始字节，旧时间戳和被篡改的 JSON 都会拒绝。"""

    key = b"test-signing-key-0123456789"
    token = "whsec_" + base64.b64encode(key).decode()
    repository_id = create_repository(client, token, "signing")
    url = f"/api/webhooks/gitlab/{repository_id}"
    body = (
        b'{"object_kind":"merge_request","project":{"id":42},"object_attributes":{"action":"merge","iid":7,"target_project_id":42,"target_branch":"main","merge_commit_sha":"'
        + b"a" * 40
        + b'"}}'
    )
    timestamp = str(int(time.time()))
    message_id = "test-delivery-id"
    digest = hmac.new(
        key, message_id.encode() + b"." + timestamp.encode() + b"." + body, hashlib.sha256
    ).digest()
    headers = {
        "webhook-id": message_id,
        "webhook-timestamp": timestamp,
        "webhook-signature": "v1," + base64.b64encode(digest).decode(),
        "X-Gitlab-Event": "Merge Request Hook",
    }
    assert client.post(url, headers=headers, content=body).status_code == 200
    assert client.post(url, headers=headers, content=body + b" ").status_code == 401
    assert (
        client.post(url, headers={**headers, "webhook-timestamp": "1"}, content=body).status_code
        == 401
    )


def test_management_recovery_and_model_key_are_private(client: TestClient) -> None:
    """补触发只建立一条事件，模型密钥只进入加密存储。"""

    repository_id = create_repository(client, "local-secret-token-123")
    admin = {"X-Admin-Token": "test-admin-token"}
    url = f"/api/repositories/{repository_id}/mrs/7/enqueue"
    assert client.post(url, headers=admin).json() == {"status": "queued"}
    assert client.post(url, headers=admin).status_code == 409
    payload = {"provider": "dashscope", "model": "qwen-test", "api_key": "private-model-key"}
    assert client.put("/api/model-profile", headers=admin, json=payload).status_code == 409
    profile = client.get("/api/model-profile", headers=admin).json()
    assert "api_key" not in profile


def test_remote_must_match_gitlab_host(client: TestClient) -> None:
    """仓库接入拒绝不受信任主机，避免后续 Git 操作指向外部地址。"""

    response = client.post(
        "/api/repositories",
        headers={"X-Admin-Token": "test-admin-token"},
        json={
            "name": "示例项目",
            "gitlab_url": "https://gitlab.example.test",
            "project_id": 42,
            "remote_url": "git@other.example.test:team/repo.git",
            "target_branch": "main",
            "auth_kind": "secret",
            "webhook_token": "local-secret-token-123",
            "feishu_webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/example",
        },
    )
    assert response.status_code == 422


def test_model_profile_can_be_saved_without_revealing_key(client: TestClient) -> None:
    """空队列允许配置模型，更新时可保留旧密钥且响应不包含敏感字段。"""

    admin = {"X-Admin-Token": "test-admin-token"}
    first = client.put(
        "/api/model-profile",
        headers=admin,
        json={"provider": "dashscope", "model": "qwen-test", "api_key": "private-model-key"},
    )
    assert first.status_code == 200
    assert first.json() == {
        "provider": "dashscope",
        "model": "qwen-test",
        "has_api_key": True,
        "version": 1,
    }
    updated = client.put(
        "/api/model-profile",
        headers=admin,
        json={"provider": "dashscope", "model": "qwen-next"},
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    assert "private-model-key" not in updated.text


def test_repository_pause_and_webhook_rotation(client: TestClient, settings: Settings) -> None:
    """暂停后不接收或领取事件；令牌轮换后旧令牌失效且密文不回显。"""

    repository_id = create_repository(client, "local-secret-token-123")
    admin = {"X-Admin-Token": "test-admin-token"}
    webhook_url = f"/api/webhooks/gitlab/{repository_id}"
    headers = {"X-Gitlab-Token": "local-secret-token-123", "X-Gitlab-Event": "Merge Request Hook"}
    assert client.post(webhook_url, headers=headers, json=merge_payload()).status_code == 200
    paused = client.patch(
        f"/api/repositories/{repository_id}", headers=admin, json={"enabled": False}
    )
    assert paused.status_code == 200
    assert paused.json()["enabled"] == 0
    assert paused.json()["last_webhook_at"] is not None
    assert client.post(webhook_url, headers=headers, json=merge_payload()).status_code == 404
    store = Store(settings.data_dir / "app.db")
    assert store.next_event() is None
    assert (
        client.patch(
            f"/api/repositories/{repository_id}",
            headers=admin,
            json={"auth_kind": "signing"},
        ).status_code
        == 422
    )
    rotated = client.patch(
        f"/api/repositories/{repository_id}",
        headers=admin,
        json={"enabled": True, "webhook_token": "new-secret-token-456", "webhook_id": "hook-42"},
    )
    assert rotated.status_code == 200
    assert rotated.json()["webhook_id"] == "hook-42"
    assert "webhook_secret" not in rotated.json()
    assert client.post(webhook_url, headers=headers, json=merge_payload()).status_code == 401
    new_headers = {**headers, "X-Gitlab-Token": "new-secret-token-456"}
    assert client.post(webhook_url, headers=new_headers, json=merge_payload()).status_code == 200
    assert store.next_event() is not None


def test_audit_records_management_outcomes_without_secrets(client: TestClient) -> None:
    """成功和被拒绝的管理写操作均留下路由级审计，令牌不进入记录。"""

    repository_id = create_repository(client, "local-secret-token-123")
    admin = {"X-Admin-Token": "test-admin-token"}
    assert (
        client.patch(
            f"/api/repositories/{repository_id}",
            headers=admin,
            json={"auth_kind": "signing"},
        ).status_code
        == 422
    )
    audit = client.get("/api/audit-logs", headers=admin)
    assert audit.status_code == 200
    entries = audit.json()
    assert entries[0]["action"] == "PATCH /api/repositories/{repository_id}"
    assert entries[0]["object_id"] == repository_id
    assert entries[0]["outcome"] == "http_422"
    assert entries[1]["action"] == "POST /api/repositories"
    assert entries[1]["outcome"] == "success"
    assert "local-secret-token-123" not in audit.text
