"""删除项目后工件不会泄露给复用 ID；运行锁防止清理在评审中发生。"""

from __future__ import annotations

from pathlib import Path

from ocr_manager.artifact_lock import artifact_lock
from ocr_manager.monitoring import prune_orphan_artifacts
from ocr_manager.storage import Store


def add_job(store: Store, project_id: int) -> tuple[int, int]:
    """以合成事件生成一个可追踪任务。"""

    repository_id = store.add_repository({
        "name": f"项目 {project_id}", "gitlab_url": "https://gitlab.example.test",
        "project_id": project_id, "remote_url": "https://gitlab.example.test/team/a.git",
        "target_branch": "main", "auth_kind": "secret", "webhook_secret": "x",
        "feishu_webhook": "",
    })
    assert store.add_event(repository_id, 7, None, "a" * 40, None)
    event = store.next_event()
    assert event
    store.finish_event(event["id"], ["a" * 40], {"a" * 40: ("snapshot", "")}, None)
    job = store.list_jobs()[0]
    return repository_id, job["id"]


def test_deleted_project_artifacts_and_ids(tmp_path: Path) -> None:
    """持锁任务晚清理，新项目也永远不会继承其目录编号。"""

    store = Store(tmp_path / "app.db")
    store.migrate()
    repository_id, job_id = add_job(store, 41)
    directory = tmp_path / "runs" / str(job_id)
    directory.mkdir(parents=True)
    directory.joinpath("result.json").write_text("synthetic", encoding="utf-8")
    with artifact_lock(tmp_path, job_id):
        assert store.delete_repository(repository_id)
        assert prune_orphan_artifacts(store, tmp_path)["count"] == 0
    assert prune_orphan_artifacts(store, tmp_path)["count"] == 1
    assert not directory.exists()
    _new_repository, new_job_id = add_job(store, 42)
    assert new_job_id > job_id
