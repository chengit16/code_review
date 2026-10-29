"""验证按操作手册新增的仓库、统一 Webhook、Push 和模型配置链路。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from ocr_manager import worker
from ocr_manager.config import Settings, load_settings
from ocr_manager.git_repo import GitRepository
from ocr_manager.secrets import SecretBox
from ocr_manager.storage import Store

ADMIN = {"X-Admin-Token": "test-admin-token"}


def configured_repository(client: TestClient) -> tuple[int, str]:
    """模拟后台先建飞书通道，再创建无凭据 HTTPS 仓库。"""

    target = client.post(
        "/api/notification-targets",
        headers=ADMIN,
        json={
            "name": "研发审核群",
            "webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/example",
        },
    )
    assert target.status_code == 201
    repository = client.post(
        "/api/repositories",
        headers=ADMIN,
        json={
            "name": "订单服务",
            "gitlab_url": "https://gitlab.example.test",
            "project_id": 42,
            "path_with_namespace": "team/order",
            "remote_url": "https://gitlab.example.test/team/order.git",
            "target_branch": "main",
            "gitlab_token": "private-project-token",
            "feishu_target_id": target.json()["id"],
            "enable_merge_requests": True,
            "enable_default_branch_pushes": True,
        },
    )
    assert repository.status_code == 201, repository.text
    token = client.get(
        f"/api/repositories/{repository.json()['id']}/webhook-token", headers=ADMIN
    ).json()["webhook_token"]
    return repository.json()["id"], token


def test_document_repository_fields_and_shared_webhook(
    client: TestClient, settings: Settings
) -> None:
    repository_id, secret = configured_repository(client)
    listed = client.get("/api/repositories", headers=ADMIN).json()[0]
    assert listed["path_with_namespace"] == "team/order"
    assert listed["has_gitlab_token"] is True
    assert listed["webhook_url"] == "https://review.example.test/api/webhooks/gitlab"
    assert "private-project-token" not in str(listed)
    stored = Store(settings.data_dir / "app.db").get_repository(repository_id)
    assert stored is not None
    assert (
        SecretBox(settings.master_key).decrypt(stored["gitlab_token_ciphertext"])
        == "private-project-token"
    )
    payload = {
        "object_kind": "merge_request",
        "project": {"id": 42},
        "object_attributes": {
            "action": "merge",
            "iid": 7,
            "target_project_id": 42,
            "target_branch": "main",
            "merge_commit_sha": "a" * 40,
        },
    }
    headers = {"X-Gitlab-Token": secret, "X-Gitlab-Event": "Merge Request Hook"}
    assert client.post("/api/webhooks/gitlab", headers=headers, json=payload).json() == {
        "status": "queued"
    }
    assert (
        client.post(
            "/api/webhooks/gitlab", headers={**headers, "X-Gitlab-Token": "wrong"}, json=payload
        ).status_code
        == 401
    )
    rotated = client.post(f"/api/repositories/{repository_id}/webhook-token/rotate", headers=ADMIN)
    assert rotated.status_code == 200
    assert "webhook_token" not in rotated.text
    assert client.post("/api/webhooks/gitlab", headers=headers, json=payload).status_code == 401
    current = client.get(f"/api/repositories/{repository_id}/webhook-token", headers=ADMIN).json()[
        "webhook_token"
    ]
    assert current != secret


def test_project_id_can_be_corrected_before_business_events(
    client: TestClient, settings: Settings
) -> None:
    """录错 GitLab 数字 ID 时可保留现有凭据修正；业务事件建立后身份必须冻结。"""

    repository_id, webhook_secret = configured_repository(client)
    corrected = client.patch(
        f"/api/repositories/{repository_id}", headers=ADMIN, json={"project_id": 43}
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["project_id"] == 43
    assert corrected.json()["has_gitlab_token"] is True
    assert corrected.json()["feishu_target_id"] is not None
    assert (
        client.get(f"/api/repositories/{repository_id}/webhook-token", headers=ADMIN).json()[
            "webhook_token"
        ]
        == webhook_secret
    )
    store = Store(settings.data_dir / "app.db")
    assert store.enqueue_mr(repository_id, 7)
    rejected = client.patch(
        f"/api/repositories/{repository_id}", headers=ADMIN, json={"project_id": 44}
    )
    assert rejected.status_code == 409
    assert store.get_repository(repository_id)["project_id"] == 43


def test_project_id_is_frozen_after_authenticated_webhook(client: TestClient) -> None:
    """即使审核开关关闭，只要旧身份接收过合法投递就不再重新绑定项目。"""

    repository_id, secret = configured_repository(client)
    client.patch(
        f"/api/repositories/{repository_id}",
        headers=ADMIN,
        json={"enable_merge_requests": False},
    )
    response = client.post(
        "/api/webhooks/gitlab",
        headers={"X-Gitlab-Token": secret, "X-Gitlab-Event": "Merge Request Hook"},
        json={
            "object_kind": "merge_request",
            "project": {"id": 42},
            "object_attributes": {"target_branch": "main"},
        },
    )
    assert response.status_code == 204
    rejected = client.patch(
        f"/api/repositories/{repository_id}", headers=ADMIN, json={"project_id": 43}
    )
    assert rejected.status_code == 409


def test_repository_source_can_be_corrected_without_recreating_credentials(
    client: TestClient, settings: Settings
) -> None:
    """修改 Clone URL、命名空间和分支时，保留项目令牌、飞书关联及 Webhook Secret。"""

    repository_id, webhook_secret = configured_repository(client)
    corrected = client.patch(
        f"/api/repositories/{repository_id}",
        headers=ADMIN,
        json={
            "name": "订单服务新名称",
            "gitlab_url": "https://gitlab.example.test",
            "remote_url": "https://gitlab.example.test/team/order-renamed.git",
            "path_with_namespace": "team/order-renamed",
            "target_branch": "release",
        },
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["remote_url"].endswith("/team/order-renamed.git")
    assert corrected.json()["path_with_namespace"] == "team/order-renamed"
    assert corrected.json()["target_branch"] == "release"
    assert corrected.json()["has_gitlab_token"] is True
    assert corrected.json()["feishu_target_id"] is not None
    assert (
        client.get(f"/api/repositories/{repository_id}/webhook-token", headers=ADMIN).json()[
            "webhook_token"
        ]
        == webhook_secret
    )
    stored = Store(settings.data_dir / "app.db").get_repository(repository_id)
    assert stored is not None
    assert (
        SecretBox(settings.master_key).decrypt(stored["gitlab_token_ciphertext"])
        == "private-project-token"
    )


@pytest.mark.parametrize(
    "change",
    [
        {"remote_url": "https://oauth2:secret@gitlab.example.test/team/order.git"},
        {
            "remote_url": "https://gitlab.example.test/other/repo.git",
            "path_with_namespace": "team/order",
        },
        {"remote_url": "https://different.example.test/team/order.git"},
        {"target_branch": "../main"},
        {"gitlab_url": "http://gitlab.example.test"},
    ],
)
def test_repository_edit_reuses_source_validation(
    client: TestClient, change: dict[str, str]
) -> None:
    """编辑入口不能绕过新增时的凭据、同源路径和分支限制。"""

    repository_id, _secret = configured_repository(client)
    rejected = client.patch(f"/api/repositories/{repository_id}", headers=ADMIN, json=change)
    assert rejected.status_code == 422
    listed = client.get("/api/repositories", headers=ADMIN).json()[0]
    assert listed["remote_url"] == "https://gitlab.example.test/team/order.git"
    assert listed["target_branch"] == "main"


def test_repository_source_waits_for_active_event_and_freezes_project_identity(
    client: TestClient, settings: Settings
) -> None:
    """旧事件只属于原项目；活动队列也不能在来源改动中途切换分支。"""

    repository_id, _secret = configured_repository(client)
    store = Store(settings.data_dir / "app.db")
    assert store.enqueue_mr(repository_id, 7)
    active = client.patch(
        f"/api/repositories/{repository_id}", headers=ADMIN, json={"target_branch": "release"}
    )
    assert active.status_code == 409
    event = store.next_event()
    assert event is not None
    store.finish_event(event["id"], [], {}, None)
    corrected = client.patch(
        f"/api/repositories/{repository_id}", headers=ADMIN, json={"target_branch": "release"}
    )
    assert corrected.status_code == 200
    rejected = client.patch(
        f"/api/repositories/{repository_id}",
        headers=ADMIN,
        json={
            "gitlab_url": "https://other.example.test",
            "remote_url": "https://other.example.test/team/order.git",
            "path_with_namespace": "team/order",
        },
    )
    assert rejected.status_code == 409


def test_switching_back_to_webhook_secret_generates_new_token(client: TestClient) -> None:
    """改回 Secret token 时由服务端生成新值，旧令牌不再通过鉴权。"""

    repository_id, original = configured_repository(client)
    signing = client.patch(
        f"/api/repositories/{repository_id}",
        headers=ADMIN,
        json={"auth_kind": "signing", "webhook_token": "whsec_example-signature"},
    )
    assert signing.status_code == 200
    secret = client.patch(
        f"/api/repositories/{repository_id}", headers=ADMIN, json={"auth_kind": "secret"}
    )
    assert secret.status_code == 200
    regenerated = client.get(
        f"/api/repositories/{repository_id}/webhook-token", headers=ADMIN
    ).json()["webhook_token"]
    assert regenerated != original
    assert regenerated != "whsec_example-signature"


def test_https_repository_rejects_embedded_credentials_and_path_mismatch(
    client: TestClient,
) -> None:
    target = client.post(
        "/api/notification-targets",
        headers=ADMIN,
        json={
            "name": "通知群",
            "webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/example",
        },
    ).json()
    payload = {
        "name": "项目",
        "gitlab_url": "https://gitlab.example.test",
        "project_id": 42,
        "path_with_namespace": "team/order",
        "target_branch": "main",
        "gitlab_token": "private-project-token",
        "feishu_target_id": target["id"],
    }
    embedded = client.post(
        "/api/repositories",
        headers=ADMIN,
        json=payload | {"remote_url": "https://oauth2:secret@gitlab.example.test/team/order.git"},
    )
    assert embedded.status_code == 422
    mismatch = client.post(
        "/api/repositories",
        headers=ADMIN,
        json=payload | {"remote_url": "https://gitlab.example.test/other/repo.git"},
    )
    assert mismatch.status_code == 422
    different_port = client.post(
        "/api/repositories",
        headers=ADMIN,
        json=payload | {"remote_url": "https://gitlab.example.test:8443/team/order.git"},
    )
    assert different_port.status_code == 422


def test_repository_can_link_feishu_after_creation(client: TestClient) -> None:
    """项目与飞书通道分开保存，关联关系可在项目创建后补齐。"""

    created = client.post(
        "/api/repositories",
        headers=ADMIN,
        json={
            "name": "未关联项目",
            "gitlab_url": "https://gitlab.example.test",
            "project_id": 82,
            "path_with_namespace": "team/repo",
            "remote_url": "https://gitlab.example.test/team/repo.git",
            "target_branch": "main",
            "gitlab_token": "project-token",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["feishu_target_id"] is None


def test_legacy_environment_cannot_supply_project_or_model_credentials(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """后台四块配置以数据库为准，旧环境变量不得意外覆盖新配置。"""

    monkeypatch.setenv("OCR_APP_DEV_MODE", "1")
    monkeypatch.setenv("OCR_APP_MASTER_KEY", settings.master_key)
    monkeypatch.setenv("OCR_APP_GITLAB_API_TOKEN", "legacy-project-token")
    monkeypatch.setenv("OCR_APP_OCR_MODEL", "legacy-model")
    monkeypatch.setenv("OCR_APP_OCR_API_KEY", "legacy-model-key")
    loaded = load_settings()
    assert loaded.gitlab_api_token == ""
    assert loaded.ocr_model == ""
    assert loaded.ocr_api_key == ""


def test_default_branch_push_only_queues_matching_authenticated_event(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """一次多提交 Push 只建立并执行一个固定 before..after 范围任务。"""

    repository_id, secret = configured_repository(client)
    before, after = "a" * 40, "b" * 40
    payload = {
        "object_kind": "push",
        "project": {"id": 42},
        "ref": "refs/heads/main",
        "before": before,
        "after": after,
    }
    headers = {"X-Gitlab-Token": secret, "X-Gitlab-Event": "Push Hook"}
    url = "/api/webhooks/gitlab"
    assert (
        client.post(url, headers=headers, json=payload | {"ref": "refs/heads/dev"}).status_code
        == 204
    )
    assert client.post(url, headers=headers, json=payload).json() == {"status": "queued"}
    assert client.post(url, headers=headers, json=payload).json() == {"status": "duplicate"}
    store = Store(settings.data_dir / "app.db")
    event = store.next_event()
    assert event is not None and event["mr_iid"] < 0

    class FakeGitLab:
        def __init__(self, _url: str, token: str) -> None:
            assert token == "private-project-token"

        def check_access(self, *_args: Any) -> None:
            pass

    class FakeGit:
        def __init__(self, _root: Path, repo: dict[str, Any]) -> None:
            assert repo["id"] == repository_id
            assert repo["gitlab_token"] == "private-project-token"

        def fetch(self) -> None:
            pass

        def push_range(self, old: str, new: str) -> tuple[str, str]:
            assert (old, new) == (before, after)
            return old, new

        def rule_digest(self, _sha: str) -> str:
            return ""

        def is_on_target(self, sha: str) -> bool:
            return sha == after

        def is_range_base(self, base: str, head: str) -> bool:
            return (base, head) == (before, after)

        def checkout(self, sha: str, target: Path) -> None:
            assert sha == after
            target.mkdir(parents=True)

        def range_changed_files(
            self, base: str, head: str
        ) -> list[dict[str, str | int | None]]:
            assert (base, head) == (before, after)
            return [{"path": "app.py", "added": 3, "deleted": 1}]

        def commit_author(self, _sha: str) -> str:
            return "张三"

        def remove_checkout(self, _target: Path) -> None:
            pass

    monkeypatch.setattr(worker, "GitLabClient", FakeGitLab)
    monkeypatch.setattr(worker, "GitRepository", FakeGit)
    worker.expand_event(store, settings, event)
    jobs = store.list_jobs()
    assert len(jobs) == 1
    assert jobs[0]["mr_iid"] < 0
    assert jobs[0]["commit_sha"] == after
    assert jobs[0]["base_sha"] == before

    reviewed_ranges: list[tuple[str | None, str]] = []

    def fake_review(
        *_args: Any, base_sha: str | None = None, **_kwargs: Any
    ) -> tuple[str, dict[str, Any]]:
        reviewed_ranges.append((base_sha, after))
        return "complete", {"comments": [], "manifest": {}}

    monkeypatch.setattr(worker, "run_review", fake_review)
    job = store.next_job()
    assert job is not None
    worker.review_job(store, settings, job)
    detail = store.get_job(job["id"])
    assert detail is not None
    assert detail["status"] == "complete"
    assert reviewed_ranges == [(before, after)]
    assert detail["changed_files"] == '[{"path": "app.py", "added": 3, "deleted": 1}]'
    assert detail["commit_author"] == "张三"


def test_model_profiles_activate_without_revealing_key(client: TestClient) -> None:
    payload = {
        "name": "研发模型",
        "provider": "openai",
        "model": "test-model",
        "base_url": "https://gateway.example.test/v1",
        "api_key": "private-model-key",
    }
    created = client.post("/api/model-profiles", headers=ADMIN, json=payload)
    assert created.status_code == 201, created.text
    assert created.json()["enabled"] == 0
    assert "private-model-key" not in created.text
    model_id = created.json()["id"]
    activated = client.post(f"/api/model-profiles/{model_id}/activate", headers=ADMIN)
    assert activated.status_code == 200, activated.text
    assert activated.json()["enabled"] == 1
    assert "private-model-key" not in client.get("/api/model-profiles", headers=ADMIN).text
    assert client.delete(f"/api/model-profiles/{model_id}", headers=ADMIN).status_code == 409

    another = client.post(
        "/api/model-profiles",
        headers=ADMIN,
        json={
            "name": "备选模型",
            "provider": "dashscope",
            "model": "qwen-test",
            "api_key": "second-key",
        },
    )
    assert another.status_code == 201
    assert (
        client.post(
            f"/api/model-profiles/{another.json()['id']}/activate", headers=ADMIN
        ).status_code
        == 200
    )
    profiles = client.get("/api/model-profiles", headers=ADMIN).json()
    assert [profile["enabled"] for profile in profiles] == [0, 1]
    assert client.delete(f"/api/model-profiles/{model_id}", headers=ADMIN).status_code == 200


def test_model_edit_preserves_key_and_allows_active_changes_while_queued(
    client: TestClient, settings: Settings
) -> None:
    """编辑时保留密钥；即使启用模型有待处理事件也允许保存。"""

    created = client.post(
        "/api/model-profiles",
        headers=ADMIN,
        json={
            "name": "初始模型",
            "provider": "dashscope",
            "model": "qwen-test",
            "api_key": "private-model-key",
        },
    ).json()
    url = f"/api/model-profiles/{created['id']}"
    changed = client.patch(url, headers=ADMIN, json={"name": "已修改模型", "model": "qwen-next"})
    assert changed.status_code == 200
    assert changed.json()["version"] == created["version"] + 1
    assert changed.json()["has_api_key"] is True
    stored = Store(settings.data_dir / "app.db").list_model_profiles()[0]
    assert (
        SecretBox(settings.master_key).decrypt(stored["api_key_ciphertext"]) == "private-model-key"
    )
    assert client.post(f"{url}/activate", headers=ADMIN).status_code == 200
    repository_id, _secret = configured_repository(client)
    assert (
        client.post(f"/api/repositories/{repository_id}/mrs/7/enqueue", headers=ADMIN).status_code
        == 200
    )
    assert client.patch(url, headers=ADMIN, json={"model": "qwen-later"}).status_code == 200


def test_https_git_token_stays_out_of_git_arguments_and_local_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """只在 HTTPS 网络 Git 子进程注入访问令牌，主密钥不随进程环境传出。"""

    monkeypatch.setenv("OCR_APP_MASTER_KEY", "must-not-inherit")
    repository = GitRepository(
        tmp_path,
        {
            "id": 1,
            "remote_url": "https://gitlab.example.test/team/order.git",
            "target_branch": "main",
            "gitlab_token": "private-project-token",
        },
    )
    network_env = repository._git_environment(with_token=True)
    local_env = repository._git_environment()
    helper = Path(network_env["GIT_ASKPASS"])
    assert helper.is_file() and helper.stat().st_mode & 0o777 == 0o700
    assert "private-project-token" not in helper.read_text(encoding="utf-8")
    assert network_env["OCR_GITLAB_TOKEN"] == "private-project-token"
    assert "OCR_GITLAB_TOKEN" not in local_env
    assert "OCR_APP_MASTER_KEY" not in network_env


def test_unreadable_project_token_does_not_crash_review_worker(
    client: TestClient, settings: Settings
) -> None:
    """凭据解密失败发生在 Git 初始化前，Worker 仍应完成失败状态写入。"""

    repository_id, _secret = configured_repository(client)
    store = Store(settings.data_dir / "app.db")
    assert store.add_event(repository_id, 7, None, None, None)
    event = store.next_event()
    assert event is not None
    sha = "a" * 40
    store.finish_event(event["id"], [sha], {sha: (worker.config_hash(store, settings), "")}, None)
    job = store.next_job()
    assert job is not None
    store.update_repository(repository_id, {"gitlab_token_ciphertext": "damaged"})
    worker.review_job(store, settings, job)
    detail = store.get_job(job["id"])
    assert detail is not None
    assert detail["status"] == "failed"
