"""保护等待中的评审任务不被更换后的模型或 OCR 安装静默改写。"""

from __future__ import annotations

from typing import Any

from ocr_manager import worker
from ocr_manager.config import Settings
from ocr_manager.storage import Store


def test_queued_job_rejects_changed_configuration(settings: Settings, monkeypatch: Any) -> None:
    """任务快照不匹配时不拉取 Git，也不启动 OCR。"""

    store = Store(settings.data_dir / "app.db")
    store.migrate()
    repository_id = store.add_repository(
        {
            "name": "快照项目",
            "gitlab_url": "https://gitlab.example.test",
            "project_id": 42,
            "remote_url": "git@gitlab.example.test:team/repo.git",
            "target_branch": "main",
            "auth_kind": "secret",
            "webhook_secret": "ciphertext",
            "feishu_webhook": "ciphertext",
        }
    )
    assert store.add_event(repository_id, 7, None, None, None)
    event = store.next_event()
    assert event is not None
    sha = "a" * 40
    store.finish_event(event["id"], [sha], {sha: ("old-config", "rule-blob")}, None)
    job = store.next_job()
    assert job is not None

    class ForbiddenGit:
        """快照冲突应在任何仓库操作之前终止。"""

        def __init__(self, *_args: Any) -> None:
            raise AssertionError("不应访问 Git")

    monkeypatch.setattr(worker, "GitRepository", ForbiddenGit)
    worker.review_job(store, settings, job)
    detail = store.get_job(job["id"])
    assert detail is not None
    assert detail["status"] == "failed"
    assert "配置已变化" in detail["error"]
    assert detail["delivery"]["status"] == "pending"
