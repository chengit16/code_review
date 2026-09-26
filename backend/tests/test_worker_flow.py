"""用合成外部服务验证 webhook 入队至飞书投递的持久化闭环。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from ocr_manager import worker
from ocr_manager.config import Settings
from ocr_manager.storage import Store


def test_merged_mr_runs_review_and_notification(
    client: TestClient, settings: Settings, monkeypatch: Any
) -> None:
    """HTTP 回调仅入库，Worker 分三轮完成展开、OCR 与独立通知。"""

    admin = {"X-Admin-Token": settings.admin_token}
    response = client.post(
        "/api/repositories",
        headers=admin,
        json={
            "name": "试点项目",
            "gitlab_url": "https://gitlab.example.test",
            "project_id": 42,
            "remote_url": "git@gitlab.example.test:team/repo.git",
            "target_branch": "main",
            "auth_kind": "secret",
            "webhook_token": "local-secret-token-123",
            "feishu_webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/test-secret",
        },
    )
    repository_id = response.json()["id"]
    webhook = client.post(
        f"/api/webhooks/gitlab/{repository_id}",
        headers={
            "X-Gitlab-Token": "local-secret-token-123",
            "X-Gitlab-Event": "Merge Request Hook",
        },
        json={
            "object_kind": "merge_request",
            "project": {"id": 42},
            "object_attributes": {
                "action": "merge",
                "iid": 7,
                "target_project_id": 42,
                "target_branch": "main",
                "merge_commit_sha": "a" * 40,
            },
        },
    )
    assert webhook.json() == {"status": "queued"}

    class FakeGitLab:
        """模拟 GitLab 对最终 MR 状态的只读确认。"""

        def __init__(self, _base: str, _token: str) -> None:
            pass

        def check_access(self, _project: int, _branch: str, _remote: str) -> None:
            pass

        def get_merge_request(self, _project: int, _iid: int) -> dict[str, Any]:
            return {
                "state": "merged",
                "target_branch": "main",
                "target_project_id": 42,
                "merge_commit_sha": "a" * 40,
            }

    class FakeGit:
        """模拟受控 Git checkout，避免测试访问真实远端。"""

        def __init__(self, _root: Path, _repository: dict[str, Any]) -> None:
            pass

        def fetch(self) -> None:
            pass

        def is_on_target(self, _sha: str) -> bool:
            return True

        def merge_commits(self, _sha: str) -> list[str]:
            return ["a" * 40]

        def rule_digest(self, _sha: str) -> str:
            return "rule-blob"

        def checkout(self, _sha: str, target: Path) -> None:
            target.mkdir(parents=True)

        def remove_checkout(self, _target: Path) -> None:
            pass

    sent: list[tuple[str, int, str, str]] = []
    monkeypatch.setattr(worker, "GitLabClient", FakeGitLab)
    monkeypatch.setattr(worker, "GitRepository", FakeGit)
    monkeypatch.setattr(
        worker, "run_review", lambda *_args: ("complete", {"comments": [], "manifest": {}})
    )
    monkeypatch.setattr(
        worker,
        "send_review",
        lambda url, job: sent.append((url, job["job_id"], job["mr_url"], job["commit_url"])),
    )
    store = Store(settings.data_dir / "app.db")
    assert worker.run_once(store, settings)[0]
    assert worker.run_once(store, settings)[0]
    assert worker.run_once(store, settings)[0]
    assert len(sent) == 1
    assert sent[0][0].endswith("test-secret")
    assert sent[0][2].endswith("/team/repo/-/merge_requests/7")
    assert sent[0][3].endswith("/team/repo/-/commit/" + "a" * 40)
    detail = client.get(f"/api/jobs/{sent[0][1]}", headers=admin).json()
    assert detail["status"] == "complete"
    assert detail["delivery"]["status"] == "sent"
    assert detail["mr_url"] == sent[0][2]
    assert detail["commit_url"] == sent[0][3]
    assert len(detail["attempt_history"]) == 1
    assert worker.run_once(store, settings)[0] is False


def test_worker_rejects_mr_from_other_target_project(
    client: TestClient, settings: Settings, monkeypatch: Any
) -> None:
    """GitLab API 目标项目不符时，事件转人工处理且不拉取 Git。"""

    response = client.post(
        "/api/repositories",
        headers={"X-Admin-Token": settings.admin_token},
        json={
            "name": "目标项目校验",
            "gitlab_url": "https://gitlab.example.test",
            "project_id": 42,
            "remote_url": "git@gitlab.example.test:team/repo.git",
            "target_branch": "main",
            "auth_kind": "secret",
            "webhook_token": "local-secret-token-123",
            "feishu_webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/test-secret",
        },
    )
    repository_id = response.json()["id"]
    assert (
        client.post(
            f"/api/repositories/{repository_id}/mrs/7/enqueue",
            headers={"X-Admin-Token": settings.admin_token},
        ).status_code
        == 200
    )

    class WrongProjectGitLab:
        """模拟读取到目标项目不同的已合并 MR。"""

        def __init__(self, _base: str, _token: str) -> None:
            pass

        def check_access(self, _project: int, _branch: str, _remote: str) -> None:
            pass

        def get_merge_request(self, _project: int, _iid: int) -> dict[str, Any]:
            return {"state": "merged", "target_branch": "main", "target_project_id": 99}

    class ForbiddenGit:
        """范围未验证前任何 Git 操作都应被阻止。"""

        def __init__(self, *_args: Any) -> None:
            raise AssertionError("不应初始化 Git 仓库")

    monkeypatch.setattr(worker, "GitLabClient", WrongProjectGitLab)
    monkeypatch.setattr(worker, "GitRepository", ForbiddenGit)
    store = Store(settings.data_dir / "app.db")
    assert worker.run_once(store, settings)[0]
    event = store.list_events()[0]
    assert event["status"] == "needs_attention"
    assert store.list_jobs() == []
