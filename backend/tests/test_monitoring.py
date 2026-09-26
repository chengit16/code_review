"""验证运维监控和清理范围不破坏业务历史或待发送通知。"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from ocr_manager.config import Settings
from ocr_manager.storage import Store


def test_monitor_and_prune_keep_database_history(
    client: TestClient, settings: Settings,
) -> None:
    """旧终态工件可清理，任务状态与安全结果仍可查询。"""

    headers = {"X-Admin-Token": settings.admin_token}
    repository = client.post("/api/repositories", headers=headers, json={
        "name": "试点", "gitlab_url": "https://gitlab.example.test", "project_id": 42,
        "remote_url": "git@gitlab.example.test:a/b.git", "target_branch": "main",
    }).json()
    store = Store(settings.data_dir / "app.db")
    store.add_event(repository["id"], 7, None, None, None)
    event = store.next_event()
    assert event is not None
    sha = "a" * 40
    store.finish_event(event["id"], [sha], {sha: ("snapshot", "")}, None)
    job = store.next_job()
    assert job is not None
    store.finish_job(job["id"], "complete", "runs/1/1/result.json",
                     {"comments": []}, None)
    with store.connection() as db:
        db.execute("UPDATE review_jobs SET finished_at='2020-01-01 00:00:00' WHERE id=?",
                   (job["id"],))
    directory = settings.data_dir / "runs" / str(job["id"])
    directory.mkdir(parents=True)
    (directory / "result.json").write_text("old artifact", encoding="utf-8")
    assert client.get("/api/operations").status_code == 401
    snapshot = client.get("/api/operations", headers=headers)
    assert snapshot.status_code == 200
    assert snapshot.json()["jobs"]["complete"] == 1
    assert snapshot.json()["backup"]["healthy"] is False
    # 待投递的结果不能清理；发送结束后才进入候选范围。
    assert client.get("/api/maintenance/preview", headers=headers).json()["count"] == 0
    delivery = store.next_delivery()
    assert delivery is not None
    store.finish_delivery(delivery["id"], None)
    assert client.get("/api/maintenance/preview", headers=headers).json()["count"] == 1
    result = client.post("/api/maintenance/prune", headers=headers)
    assert result.json()["count"] == 1
    assert not directory.exists()
    assert store.get_job(job["id"])["status"] == "complete"


def test_prune_rejects_symlink_and_short_retention(
    client: TestClient, settings: Settings, tmp_path: Path,
) -> None:
    """清理范围不可被符号链接引向数据目录外，保留期至少七天。"""

    headers = {"X-Admin-Token": settings.admin_token}
    assert client.post("/api/maintenance/prune?days=1", headers=headers).status_code == 422
    external = tmp_path / "external"
    external.mkdir()
    (external / "keep").write_text("safe", encoding="utf-8")
    runs = settings.data_dir / "runs"
    runs.mkdir()
    (runs / "1").symlink_to(external, target_is_directory=True)
    assert client.post("/api/maintenance/prune", headers=headers).json()["count"] == 0
    assert (external / "keep").is_file()
