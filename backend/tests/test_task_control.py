"""保护取消竞态、重启、批量幂等与真实子进程停止；全部使用合成数据。"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from ocr_manager.cancellation import ReviewCancelled, cancellation_scope
from ocr_manager.config import Settings
from ocr_manager.ocr import run_ocr_command
from ocr_manager.task_control import cancel_job
from test_task_operations import populate

ADMIN = {"X-Admin-Token": "test-admin-token"}


def test_cancel_queued_and_running(client: TestClient, settings: Settings) -> None:
    """排队取消不消耗尝试；运行停止在写回时优先于晚到结果。"""

    store, _ = populate(client, settings, 2)
    assert client.post("/api/jobs/1/cancel").status_code == 401
    assert client.post("/api/jobs/1/cancel", headers=ADMIN).json()["status"] == "cancelled"
    job = store.next_job()
    assert job is not None and job["id"] == 2
    assert cancel_job(store, 2) == "stopping"
    store.finish_job(2, "complete", None, {"comments": []}, None)
    finished = store.get_job(2)
    assert finished and finished["status"] == "cancelled" and finished["delivery"] is None
    assert store.retry_job(2) == 2
    retried = store.get_job(2)
    assert retried and retried["cancel_requested"] == 0


def test_recover_respects_stop(client: TestClient, settings: Settings) -> None:
    """重启不会把持久化停止请求重新排队。"""

    store, _ = populate(client, settings, 1)
    assert store.next_job()
    cancel_job(store, 1)
    store.recover()
    assert store.next_job() is None
    job = store.get_job(1)
    assert job and job["status"] == "cancelled"


def test_batch_reports_conflicts(client: TestClient, settings: Settings) -> None:
    """重复 ID 只执行一次；缺失和运行中的任务逐项拒绝。"""

    store, repository_id = populate(client, settings, 1)
    assert store.next_job()
    store.finish_job(1, "failed", None, None, "合成失败")
    result = client.post("/api/jobs/batch-retry", headers=ADMIN,
                         json={"ids": [1, 1, 999]}).json()
    assert [item["status"] for item in result] == ["queued", "rejected"]
    result = client.post(f"/api/repositories/{repository_id}/mrs/batch-enqueue",
                         headers=ADMIN, json={"ids": [7, 7, -1]}).json()
    assert [item["status"] for item in result] == ["queued", "rejected"]


def test_child_process_stops_before_timeout(tmp_path: Path) -> None:
    """停止在命令执行中发生，必须结束进程组并清理检查上下文。"""

    start = time.monotonic()
    with pytest.raises(ReviewCancelled), cancellation_scope(
        lambda: time.monotonic() - start > 0.2
    ):
        run_ocr_command([sys.executable, "-c", "import time; time.sleep(20)"], {}, tmp_path, 30)
    assert time.monotonic() - start < 5
