"""验证飞书通道共享、凭据隔离及删除后的仓库解绑。"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from ocr_manager import storage
from ocr_manager.config import Settings
from ocr_manager.storage import Store

ADMIN = {"X-Admin-Token": "test-admin-token"}
HOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/first"


def test_shared_target_updates_all_repositories_and_deletes_without_history_loss(
    client: TestClient, settings: Settings
) -> None:
    created = client.post(
        "/api/notification-targets",
        headers=ADMIN,
        json={"name": "研发审核群", "webhook_url": HOOK, "signing_secret": "private-signing-key"},
    )
    assert created.status_code == 201, created.text
    target_id = created.json()["id"]
    assert HOOK not in created.text
    assert "private-signing-key" not in created.text
    assert created.json()["has_signing_secret"] is True
    repository_ids = []
    for project_id in (42, 43):
        response = client.post(
            "/api/repositories",
            headers=ADMIN,
            json={
                "name": f"项目 {project_id}",
                "gitlab_url": "https://gitlab.example.test",
                "project_id": project_id,
                "remote_url": f"git@gitlab.example.test:team/repo-{project_id}.git",
                "target_branch": "main",
                "auth_kind": "secret",
                "feishu_target_id": target_id,
            },
        )
        assert response.status_code == 201, response.text
        repository_ids.append(response.json()["id"])
    store = Store(settings.data_dir / "app.db")
    assert client.get("/api/notification-targets", headers=ADMIN).json()[0]["repository_count"] == 2
    for repository_id in repository_ids:
        assert store.get_repository(repository_id)["feishu_target_id"] == target_id

    changed = client.patch(
        f"/api/notification-targets/{target_id}",
        headers=ADMIN,
        json={"webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/next"},
    )
    assert changed.status_code == 200
    assert store.get_notification_target(target_id)["webhook_ciphertext"] != HOOK
    assert changed.json()["repository_count"] == 2
    assert client.delete(f"/api/notification-targets/{target_id}", headers=ADMIN).status_code == 200
    for repository_id in repository_ids:
        assert store.get_repository(repository_id)["feishu_target_id"] is None
    assert len(client.get("/api/repositories", headers=ADMIN).json()) == 2


def test_unknown_target_cannot_be_assigned(client: TestClient) -> None:
    response = client.post(
        "/api/repositories",
        headers=ADMIN,
        json={
            "name": "项目",
            "gitlab_url": "https://gitlab.example.test",
            "project_id": 42,
            "remote_url": "git@gitlab.example.test:team/repo.git",
            "target_branch": "main",
            "auth_kind": "secret",
            "feishu_target_id": 999,
        },
    )
    assert response.status_code == 422


def test_existing_repository_hook_is_migrated_to_shared_target(tmp_path: Path) -> None:
    """升级旧数据库时保持已有飞书密文和项目关联，避免通知目标丢失。"""

    store = Store(tmp_path / "app.db")
    with store.connection() as db:
        db.executescript(
            "\n".join(
                (
                    storage.SCHEMA,
                    storage.SCHEMA_V2,
                    storage.SCHEMA_V3,
                    storage.SCHEMA_V4,
                    storage.SCHEMA_V5,
                    storage.SCHEMA_V6,
                    storage.SCHEMA_V7,
                )
            )
        )
        db.execute(
            """INSERT INTO repositories
            (name, gitlab_url, project_id, remote_url, target_branch,
             auth_kind, webhook_secret, feishu_webhook)
            VALUES ('旧项目', 'https://gitlab.example.test', 42,
              'git@gitlab.example.test:team/repo.git', 'main', 'secret',
              'encrypted-token', 'encrypted-hook')"""
        )
        db.execute("PRAGMA user_version=7")
    store.migrate()
    repository = store.get_repository(1)
    target = store.get_notification_target(1)
    assert repository is not None and target is not None
    assert repository["feishu_target_id"] == 1
    assert repository["feishu_webhook"] == ""
    assert target["webhook_ciphertext"] == "encrypted-hook"
