"""保护模型草稿自由保存、凭据保留与执行端安全边界；只使用合成配置。"""

from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from ocr_manager import worker
from ocr_manager.config import Settings
from ocr_manager.model_pricing import estimate_cost
from ocr_manager.ocr import check_model_connection
from test_task_operations import populate

ADMIN = {"X-Admin-Token": "test-admin-token"}


def test_empty_and_incomplete_model_drafts_can_be_saved(client: TestClient) -> None:
    """空草稿和不完整字段均落库，原文不因保存而丢失。"""

    created = client.post("/api/model-profiles", headers=ADMIN, json={})
    assert created.status_code == 201
    assert created.json()["has_api_key"] is False
    url = f"/api/model-profiles/{created.json()['id']}"
    draft = {"name": "", "model": "", "provider": "待填写 provider",
             "base_url": "尚未填写完整", "api_key": "", "input_price_per_million": "待确认",
             "output_price_per_million": None}
    updated = client.patch(url, headers=ADMIN, json=draft)
    assert updated.status_code == 200
    for field, value in draft.items():
        if field != "api_key":
            assert updated.json()[field] == value
    assert client.patch(url, headers=ADMIN, json={}).status_code == 200
    assert client.post("/api/model-profiles", headers=ADMIN, json=draft).status_code == 201
    numeric = client.patch(url, headers=ADMIN, json={"input_price_per_million": 2.5})
    assert numeric.status_code == 200
    assert numeric.json()["input_price_per_million"] == "2.5"
    assert estimate_cost({"input_tokens": 1, "output_tokens": 1}, {"pricing": {
        "price_currency": "CNY", "input_price_per_million": "待确认",
        "output_price_per_million": "-1",
    }}) is None


@pytest.mark.parametrize("endpoint", ["尚未完成", "http://example.test/v1",
                                     "https://user:secret@example.test/v1", "https://["])
def test_invalid_saved_endpoint_is_rejected_only_at_execution(
    settings: Settings, tmp_path: Path, endpoint: str,
) -> None:
    """保存不校验端点，但真正执行前仍阻止不安全地址进入命令参数。"""

    with pytest.raises(ValueError, match="Base URL"):
        check_model_connection(replace(settings, ocr_base_url=endpoint), tmp_path / "check")


def test_project_model_edit_saves_but_queued_job_keeps_snapshot_protection(
    client: TestClient, settings: Settings,
) -> None:
    """项目专属模型在队列中仍可保存，旧任务不得改用新模型执行。"""

    store, repository_id = populate(client, settings, 0)
    created = client.post("/api/model-profiles", headers=ADMIN, json={
        "name": "专属模型", "model": "old-model", "api_key": "synthetic-key",
    }).json()
    assert client.put(f"/api/repositories/{repository_id}/limits", headers=ADMIN,
                      json={"model_profile_id": created["id"]}).status_code == 200
    assert store.add_event(repository_id, 1, None, None, None)
    event = store.next_event()
    assert event is not None
    sha = "a" * 40
    original_hash = worker.config_hash(store, settings, repository_id=repository_id)
    store.finish_event(event["id"], [sha], {sha: (original_hash, "")}, None)
    response = client.patch(f"/api/model-profiles/{created['id']}", headers=ADMIN,
                            json={"model": "new-model"})
    assert response.status_code == 200
    job = store.next_job()
    assert job is not None
    worker.review_job(store, settings, job)
    detail = store.get_job(job["id"])
    assert detail is not None
    assert detail["status"] == "failed"
    assert "配置已变化" in detail["error"]


@pytest.mark.parametrize("rate", ["待确认", "-1", "NaN", "Infinity", "1e999999999"])
def test_invalid_or_extreme_price_does_not_break_cost_display(rate: str) -> None:
    """任意已保存单价不能让任务详情费用估算抛出异常。"""

    assert estimate_cost({"input_tokens": 1, "output_tokens": 1}, {"pricing": {
        "price_currency": "CNY", "input_price_per_million": rate,
        "output_price_per_million": "2",
    }}) is None
