"""验证历史结果不被重审覆盖、安全导出与不同提交对比拒绝。"""

from __future__ import annotations

from fastapi.testclient import TestClient
from ocr_manager.attempt_history import save_snapshot
from ocr_manager.config import Settings
from ocr_manager.worker import configuration_snapshot
from test_task_operations import populate

ADMIN = {"X-Admin-Token": "test-admin-token"}


def test_attempt_reports_and_comparison(client: TestClient, settings: Settings) -> None:
    """旧发现仍可下载，新尝试独立比较；快照和报告没有凭据或 thinking。"""

    store, _ = populate(client, settings, 2)
    assert store.next_job()
    save_snapshot(store, 1, configuration_snapshot(store, settings))
    store.finish_job(1, "partial", "/private/result.json", {
        "comments": [{"path": "a.py", "content": "旧发现", "thinking": "private-reasoning"}],
    }, None)
    assert store.retry_job(1) == 1
    assert store.next_job()
    store.finish_job(1, "complete", None, {"comments": [{"path": "b.py", "content": "新发现"}]},
                     None)
    report = client.get("/api/jobs/1/report?attempt=1", headers=ADMIN)
    assert "旧发现" in report.text and "新发现" not in report.text
    for secret in (settings.ocr_api_key, "private-reasoning", "/private/"):
        assert secret not in report.text
    assert report.json()["configuration"]["model"] == settings.ocr_model
    changes = client.get("/api/jobs/1/comparison?before=1&after=2", headers=ADMIN).json()
    assert changes["added"][0]["content"] == "新发现"
    assert changes["removed"][0]["content"] == "旧发现"
    assert client.get("/api/jobs/1/report?attempt=999", headers=ADMIN).status_code == 404
    assert client.get("/api/jobs/1/comparison?before=1&after=1&other_job_id=2",
                      headers=ADMIN).status_code == 409
