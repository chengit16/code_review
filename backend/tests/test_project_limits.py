"""验证项目模型隔离、执行预算、文件上限和在途不可变约束。"""

from __future__ import annotations

from fastapi.testclient import TestClient
from ocr_manager.config import Settings
from ocr_manager.secrets import SecretBox
from ocr_manager.worker import config_hash, review_settings
from test_task_operations import populate

ADMIN = {"X-Admin-Token": "test-admin-token"}


def test_project_limits_override_model_and_hash(client: TestClient, settings: Settings) -> None:
    """专属模型及限额进入快照，空值回到全局配置。"""

    store, repository_id = populate(client, settings, 0)
    profile_id = store.add_model_profile("专属", "custom", "project-model", "",
                                         SecretBox(settings.master_key).encrypt("synthetic-key"))
    before = config_hash(store, settings, repository_id=repository_id)
    payload = {"model_profile_id": profile_id, "timeout_seconds": 120,
               "max_files": 10, "max_tokens_budget": 1000}
    url = f"/api/repositories/{repository_id}/limits"
    assert client.put(url, headers=ADMIN, json=payload).status_code == 200
    assert client.get(url, headers=ADMIN).json() == payload
    active, version = review_settings(store, settings, repository_id)
    assert active.ocr_model == "project-model" and active.ocr_timeout_seconds == 120
    assert active.ocr_max_files == 10 and active.ocr_max_tokens_budget == 1000
    assert version == 1 and config_hash(store, settings, repository_id=repository_id) != before
    assert client.put(url, headers=ADMIN, json={"max_files": 0}).status_code == 422
    store.add_event(repository_id, 1, None, None, None)
    assert client.put(url, headers=ADMIN, json=payload).status_code == 409


def test_usage_whitelist(client: TestClient, settings: Settings) -> None:
    """数据库只记录数值用量和预算事实，不保存供应商原始元数据。"""

    store, _ = populate(client, settings, 1)
    job = store.next_job()
    assert job
    store.finish_job(job["id"], "partial", None, {
        "summary": {"input_tokens": 12, "output_tokens": 8, "total_tokens": 20,
                    "budget_exceeded": True, "secret": "must-not-persist"},
        "comments": [],
    }, None)
    detail = client.get(f"/api/jobs/{job['id']}", headers=ADMIN).json()
    assert detail["result"]["usage"]["total_tokens"] == 20
    assert detail["result"]["summary"]["budget_exceeded"]
    assert "must-not-persist" not in str(detail)
