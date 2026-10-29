"""验证项目模型隔离、执行预算、文件上限和在途不可变约束。"""

from __future__ import annotations

from fastapi.testclient import TestClient
from ocr_manager.attempt_history import save_snapshot
from ocr_manager.config import Settings
from ocr_manager.secrets import SecretBox
from ocr_manager.worker import config_hash, configuration_snapshot, review_settings
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


def test_bailian_pricing_estimate_uses_run_snapshot(
    client: TestClient, settings: Settings,
) -> None:
    """百练模型的输入、输出单价按本次快照计费，后续改单价不改历史金额。"""

    store, repository_id = populate(client, settings, 1)
    created = client.post("/api/model-profiles", headers=ADMIN, json={
        "name": "百练测试", "provider": "dashscope", "model": "qwen-test",
        "api_key": "synthetic-key", "price_currency": "CNY",
        "input_price_per_million": "2", "output_price_per_million": "8",
    })
    assert created.status_code == 201
    profile_id = created.json()["id"]
    assert created.json()["input_price_per_million"] == "2"
    assert client.post(
        f"/api/model-profiles/{profile_id}/activate", headers=ADMIN,
    ).status_code == 200
    original_hash = config_hash(store, settings, repository_id=repository_id)
    job = store.next_job()
    assert job is not None
    snapshot = configuration_snapshot(store, settings, repository_id=repository_id)
    save_snapshot(store, job["id"], snapshot)
    store.finish_job(job["id"], "complete", None, {
        "summary": {"input_tokens": 500_000, "output_tokens": 250_000,
                    "total_tokens": 750_000}, "comments": [],
    }, None)
    detail = client.get(f"/api/jobs/{job['id']}", headers=ADMIN).json()
    assert detail["result"]["usage"] == {
        "input_tokens": 500_000, "output_tokens": 250_000, "total_tokens": 750_000,
    }
    assert detail["result"]["estimated_cost"] == {
        "currency": "CNY", "input": "1", "output": "2", "total": "3",
    }
    listed = client.get("/api/task-search", headers=ADMIN).json()["items"][0]
    assert listed["usage"] == detail["result"]["usage"]
    assert listed["estimated_cost"] == detail["result"]["estimated_cost"]
    response = client.patch(f"/api/model-profiles/{profile_id}", headers=ADMIN, json={
        "input_price_per_million": "20", "output_price_per_million": "80",
    })
    assert response.status_code == 200
    assert config_hash(store, settings, repository_id=repository_id) == original_hash
    assert client.get(f"/api/jobs/{job['id']}", headers=ADMIN).json()["result"][
        "estimated_cost"]["total"] == "3"
    report = client.get(f"/api/jobs/{job['id']}/report", headers=ADMIN).json()
    assert report["estimated_cost"]["total"] == "3"


def test_pricing_allows_one_rate_but_requires_full_usage_for_estimate(
    client: TestClient, settings: Settings,
) -> None:
    """单边报价可保存，只有合计 Token 时不推断输入/输出费用。"""

    store, _ = populate(client, settings, 1)
    response = client.post("/api/model-profiles", headers=ADMIN, json={
        "name": "缺少输出价", "provider": "dashscope", "model": "qwen-test",
        "api_key": "synthetic-key", "input_price_per_million": "2",
    })
    assert response.status_code == 201
    job = store.next_job()
    assert job is not None
    store.finish_job(job["id"], "complete", None, {
        "summary": {"total_tokens": 99}, "comments": [],
    }, None)
    detail = client.get(f"/api/jobs/{job['id']}", headers=ADMIN).json()
    assert detail["result"]["usage"] == {"total_tokens": 99}
    assert detail["result"]["estimated_cost"] is None


def test_pricing_change_is_audited_and_restorable(
    client: TestClient, settings: Settings,
) -> None:
    """单价更新留下可恢复版本，恢复旧版报价不会改变模型执行版本。"""

    response = client.post("/api/model-profiles", headers=ADMIN, json={
        "name": "百练测试", "provider": "dashscope", "model": "qwen-test",
        "api_key": "synthetic-key", "input_price_per_million": "2",
        "output_price_per_million": "8",
    })
    assert response.status_code == 201
    profile_id = response.json()["id"]
    old_version = response.json()["version"]
    initial_revision = client.get("/api/config-history/model_profile", headers=ADMIN).json()[0]
    changed = client.patch(f"/api/model-profiles/{profile_id}", headers=ADMIN, json={
        "input_price_per_million": "3", "output_price_per_million": "9",
    })
    assert changed.status_code == 200
    assert changed.json()["version"] == old_version
    history = client.get("/api/config-history/model_profile", headers=ADMIN).json()
    assert {item["field"] for item in history[0]["changes"]} == {
        "input_price_per_million", "output_price_per_million",
    }
    restored = client.post(
        f"/api/config-history/model_profile/{profile_id}/{initial_revision['id']}/restore",
        headers=ADMIN,
    )
    assert restored.status_code == 200
    current = client.get("/api/model-profiles", headers=ADMIN).json()[0]
    assert current["input_price_per_million"] == "2"
    assert current["output_price_per_million"] == "8"
    assert current["version"] == old_version
