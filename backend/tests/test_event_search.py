"""验证事件分页、关联任务与时间补审仅由 Worker 调用 GitLab。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from ocr_manager.config import Settings
from ocr_manager.secrets import SecretBox
from ocr_manager.worker import process_backfill
from test_task_operations import populate

ADMIN = {"X-Admin-Token": "test-admin-token"}


def test_event_page_and_backfill(client: TestClient, settings: Settings,
                                 monkeypatch: pytest.MonkeyPatch) -> None:
    """旧事件仍可分页访问，补审申请不立即发网络请求，重复 MR 不重复入队。"""

    store, repository_id = populate(client, settings, 3)
    listing = client.get("/api/event-search?page_size=2&page=2", headers=ADMIN).json()
    assert listing["total"] == 3
    assert [item["id"] for item in listing["items"]] == [1]
    assert listing["items"][0]["job_count"] == 1
    assert listing["items"][0]["latest_job_id"] == 1
    assert listing["items"][0]["repository_name"] == "检索项目"
    assert client.get("/api/event-search?mr_iid=2", headers=ADMIN).json()["total"] == 1
    assert client.get("/api/event-search?status=needs_attention",
                      headers=ADMIN).json()["total"] == 0
    assert client.get("/api/event-search?status=unknown", headers=ADMIN).status_code == 422
    assert client.get("/api/event-search?mr_iid=0", headers=ADMIN).status_code == 422
    assert client.get("/api/event-search", headers=ADMIN).json()["items"][0]["repository_name"]
    with store.connection() as db:
        db.execute("UPDATE merge_events SET created_at='2026-09-01 12:34:59' WHERE id=1")
    minute = client.get("/api/event-search?until=2026-09-01T12:34:00Z",
                        headers=ADMIN).json()
    assert any(item["id"] == 1 for item in minute["items"])

    with store.connection() as db:
        db.execute("UPDATE repositories SET gitlab_token_ciphertext=? WHERE id=?",
                   (SecretBox(settings.master_key).encrypt("synthetic-token"), repository_id))
    called: list[tuple[int, datetime, datetime]] = []

    def list_mrs(_self: Any, project_id: int, since: datetime, until: datetime) -> list[int]:
        called.append((project_id, since, until))
        return [2, 4]

    monkeypatch.setattr("ocr_manager.gitlab.GitLabClient.list_merged_requests", list_mrs)
    payload = {"since": "2026-09-01T00:00:00Z", "until": "2026-09-03T00:00:00Z"}
    path = f"/api/repositories/{repository_id}/mrs/backfill"
    response = client.post(path, headers=ADMIN, json=payload)
    assert response.status_code == 200 and called == []
    assert process_backfill(store, settings)
    assert called[0][0] == 42 and called[0][1].tzinfo == UTC
    backfill = client.get("/api/mr-backfills", headers=ADMIN).json()[0]
    assert backfill["status"] == "done"
    assert (backfill["scanned"], backfill["enqueued"]) == (2, 1)
    invalid = {"since": "2026-09-03T00:00:00Z", "until": "2026-09-01T00:00:00Z"}
    assert client.post(path, headers=ADMIN, json=invalid).status_code == 422


def test_event_search_rejects_oversized_utc_range(client: TestClient) -> None:
    """跨时区的区间也按真实 UTC 时长限制为 31 天。"""

    payload = {"since": "2026-09-01T00:00:00+14:00", "until": "2026-10-02T01:00:00-12:00"}
    response = client.post("/api/repositories/1/mrs/backfill", headers=ADMIN, json=payload)
    assert response.status_code == 422
