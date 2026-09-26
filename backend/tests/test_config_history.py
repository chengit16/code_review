"""验证配置版本同事务记录、密钥摘要与不破坏业务历史的恢复。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from ocr_manager.config import Settings
from ocr_manager.storage import Store


def test_history_redacts_keys_and_restores_without_losing_tasks(
    client: TestClient, settings: Settings,
) -> None:
    """历史 API 不含密文或明文；恢复名称不删除旧事件。"""

    headers = {"X-Admin-Token": settings.admin_token}
    repository = client.post("/api/repositories", headers=headers, json={
        "name": "原名称", "gitlab_url": "https://gitlab.example.test", "project_id": 42,
        "remote_url": "git@gitlab.example.test:a/b.git", "target_branch": "main",
        "webhook_token": "test-webhook-secret",
    }).json()
    original = client.get("/api/config-history/repository", headers=headers).json()[0]
    assert client.patch(f"/api/repositories/{repository['id']}", headers=headers,
                        json={"name": "新名称", "webhook_token": "replacement-webhook-key"}
                        ).status_code == 200
    history = client.get("/api/config-history/repository", headers=headers)
    assert "replacement-webhook-key" not in history.text
    assert "test-webhook-secret" not in history.text
    assert "gAAAA" not in history.text
    store = Store(settings.data_dir / "app.db")
    store.add_event(repository["id"], 7, None, None, None)
    response = client.post(
        f"/api/config-history/repository/{repository['id']}/{original['id']}/restore",
        headers=headers,
    )
    assert response.status_code == 200
    assert store.get_repository(repository["id"])["name"] == "原名称"
    assert len(store.list_events()) == 1
    with pytest.raises(RuntimeError), store.connection() as db:
        db.execute("UPDATE repositories SET name='回滚事务' WHERE id=?", (repository["id"],))
        raise RuntimeError("合成事务失败")
    assert "回滚事务" not in client.get("/api/config-history/repository", headers=headers).text


def test_history_permission_and_feishu_redaction(client: TestClient, settings: Settings) -> None:
    """共享飞书地址不进入版本响应，历史查看遵守管理鉴权。"""

    headers = {"X-Admin-Token": settings.admin_token}
    target = client.post("/api/notification-targets", headers=headers, json={
        "name": "群", "webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/test",
    })
    assert target.status_code == 201
    history = client.get("/api/config-history/notification_target", headers=headers)
    assert history.status_code == 200
    assert "open.feishu.cn" not in history.text
    assert client.get("/api/config-history/model_profile").status_code == 401


def test_history_restores_feishu_and_model_fields(client: TestClient, settings: Settings) -> None:
    """飞书与模型的恢复复用现有修改路径，旧密文不会出现在页面。"""

    headers = {"X-Admin-Token": settings.admin_token}
    target = client.post("/api/notification-targets", headers=headers, json={
        "name": "原群", "webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/original",
    }).json()
    target_version = client.get(
        "/api/config-history/notification_target", headers=headers,
    ).json()[0]
    assert client.patch(f"/api/notification-targets/{target['id']}", headers=headers,
                        json={"name": "新群"}).status_code == 200
    restored = client.post(
        f"/api/config-history/notification_target/{target['id']}/{target_version['id']}/restore",
        headers=headers,
    )
    assert restored.status_code == 200
    assert client.get("/api/notification-targets", headers=headers).json()[0]["name"] == "原群"

    profile = client.post("/api/model-profiles", headers=headers, json={
        "name": "原模型", "provider": "dashscope", "model": "qwen-test",
        "api_key": "model-test-key",
    }).json()
    profile_version = client.get("/api/config-history/model_profile", headers=headers).json()[0]
    assert client.patch(f"/api/model-profiles/{profile['id']}", headers=headers,
                        json={"name": "新模型"}).status_code == 200
    restored = client.post(
        f"/api/config-history/model_profile/{profile['id']}/{profile_version['id']}/restore",
        headers=headers,
    )
    assert restored.status_code == 200
    assert client.get("/api/model-profiles", headers=headers).json()[0]["name"] == "原模型"
