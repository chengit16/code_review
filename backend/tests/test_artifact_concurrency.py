"""验证工件清理与重审、通知重发的跨连接互斥和锁内状态复检。"""

from pathlib import Path

import pytest
from ocr_manager import monitoring
from ocr_manager.artifact_lock import artifact_lock
from ocr_manager.storage import Store


def old_job(tmp_path: Path) -> tuple[Store, int, Path]:
    """只生成合成终态任务和可清理目录，不接触本机业务数据。"""

    store = Store(tmp_path / "app.db")
    store.migrate()
    repository_id = store.add_repository({
        "name": "并发测试", "gitlab_url": "https://example.test", "project_id": 42,
        "remote_url": "git@example.test:a/b.git", "target_branch": "main",
        "auth_kind": "secret", "webhook_secret": "ciphertext", "feishu_webhook": "",
    })
    store.add_event(repository_id, 7, None, None, None)
    event = store.next_event()
    assert event is not None
    sha = "a" * 40
    store.finish_event(event["id"], [sha], {sha: ("snapshot", "")}, None)
    job = store.next_job()
    assert job is not None
    store.finish_job(job["id"], "complete", None, {"comments": []}, None)
    delivery = store.next_delivery()
    assert delivery is not None
    store.finish_delivery(delivery["id"], None)
    with store.connection() as db:
        db.execute("UPDATE review_jobs SET finished_at='2020-01-01' WHERE id=?", (job["id"],))
    directory = tmp_path / "runs" / str(job["id"])
    directory.mkdir(parents=True)
    (directory / "report.json").write_text("{}", encoding="utf-8")
    return store, int(job["id"]), directory


def test_cleanup_blocks_retry_and_notification_requeue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """模拟实际目录删除期间另一管理连接尝试重审和重发。"""

    store, job_id, directory = old_job(tmp_path)
    real_remove = monitoring.shutil.rmtree

    def remove(path: Path) -> None:
        assert store.retry_job(job_id) is None
        assert store.retry_delivery(job_id) is False
        real_remove(path)

    monkeypatch.setattr(monitoring.shutil, "rmtree", remove)
    assert monitoring.prune_artifacts(store, tmp_path, 90)["count"] == 1
    assert not directory.exists()
    assert store.retry_job(job_id) == job_id


def test_cleanup_rechecks_state_after_initial_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """任务在候选查询之后重排队，锁内复检必须保留目录。"""

    store, job_id, directory = old_job(tmp_path)
    real_select = monitoring.eligible_artifacts

    def select(store: Store, data_dir: Path, days: int,
               selected_job: int | None = None) -> list[tuple[int, Path, int]]:
        result = real_select(store, data_dir, days, selected_job)
        if selected_job is None:
            assert store.retry_job(job_id) == job_id
        return result

    monkeypatch.setattr(monitoring, "eligible_artifacts", select)
    assert monitoring.prune_artifacts(store, tmp_path, 90)["count"] == 0
    assert directory.is_dir()


def test_busy_artifact_lock_skips_cleanup(tmp_path: Path) -> None:
    """其他进程持有锁时清理返回零项，退出后不遗留死锁。"""

    store, job_id, directory = old_job(tmp_path)
    with artifact_lock(tmp_path, job_id) as acquired:
        assert acquired
        assert monitoring.prune_artifacts(store, tmp_path, 90)["count"] == 0
        assert directory.exists()
    assert monitoring.prune_artifacts(store, tmp_path, 90)["count"] == 1
