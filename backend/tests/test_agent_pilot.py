"""验证页面授权与实际入队独立，Worker 复用正确档案，关闭后历史仍可读。"""

from __future__ import annotations

import json

import httpx
import pytest
from agent_comparison_fixture import seed_task
from fastapi.testclient import TestClient
from ocr_manager import agent_review_store as queue
from ocr_manager.agent_pilot import repository_agent_config
from ocr_manager.agent_review_profile import resolve_model
from ocr_manager.agent_review_worker import execute
from ocr_manager.api import create_app
from ocr_manager.config import Settings
from ocr_manager.secrets import SecretBox
from ocr_manager.storage import Store
from test_agent_comparison_api import PATH, comparison_app, submit
from test_auth import ADMIN, create_user, enable_users, login


def test_managed_pilot_reuses_project_model_without_enqueuing_on_enable(
    settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """完整走过默认拒绝、管理员授权、独立入队、模型回执与退出试点。"""

    app = create_app(settings)
    store = Store(settings.data_dir / "app.db")
    assert seed_task(store, settings.data_dir) == 1
    profile = store.add_model_profile("项目模型", "openai", "fixture-project",
        "https://models.example.invalid/v1", SecretBox(settings.master_key).encrypt("fixture-key"))
    calls: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        assert request.headers["authorization"] == "Bearer fixture-key"
        assert json.loads(request.content)["model"] == "fixture-project"
        body = {"model": "fixture-project", "choices": [{"finish_reason": "stop",
            "message": {"content": '{"findings":[]}'}}],
            "usage": {"prompt_tokens": 40, "completion_tokens": 10, "total_tokens": 50}}
        return httpx.Response(200, stream=httpx.ByteStream(json.dumps(body).encode()))

    monkeypatch.setattr("ocr_manager.agent_review_worker.httpx.HTTPTransport",
                        lambda **_kwargs: httpx.MockTransport(respond))
    with TestClient(app) as client:
        pilot = f"{PATH}/pilot"
        data = {"source_attempt": 1, "previous_id": None, "request_key": "blocked"}
        rejected = client.post(PATH, headers=ADMIN, json=data)
        assert rejected.json()["detail"]["code"] == "agent_disabled"
        assert client.put(pilot, headers=ADMIN, json={"enabled": True}).json()[
            "detail"]["code"] == "pilot_model_unavailable"
        with store.connection() as db:
            db.execute("""INSERT INTO project_review_limits(repository_id,model_profile_id)
                VALUES(1,?)""", (profile,))
        assert client.put(pilot, headers=ADMIN, json={"enabled": True}).status_code == 204
        assert client.put(pilot, headers=ADMIN, json={"enabled": True}).status_code == 204
        result = client.get(PATH, headers=ADMIN).json()
        assert result["pilot"]["enabled"] and result["unavailable_reason"] is None
        assert result["items"] == [] and not calls
        assert client.get("/api/jobs/2/agent-comparisons", headers=ADMIN).json()["pilot"]["enabled"]
        run_id = submit(client, "manual")
        assert client.put(pilot, headers=ADMIN, json={"enabled": False}).json()[
            "detail"]["code"] == "pilot_active_runs"
        assert queue.claim(store)
        execute(store, settings, run_id)
        assert calls == ["https://models.example.invalid/v1/chat/completions"]
        assert client.get(f"{PATH}/{run_id}", headers=ADMIN).json()["status"] == "complete"
        with store.connection() as db:
            active = repository_agent_config(db, settings, 1)
        assert active is not None
        stale = resolve_model(store, active, 1)
        assert client.put(pilot, headers=ADMIN, json={"enabled": False}).status_code == 204
        with pytest.raises(ValueError, match="试点已关闭"):
            queue.enqueue(store, stale, 1, "after-revocation", run_id)
        assert client.get(f"{PATH}/{run_id}", headers=ADMIN).status_code == 200
        assert client.post(
            PATH, headers=ADMIN, json=data | {"previous_id": run_id},
        ).status_code == 409
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM agent_review_pilots").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM notification_deliveries").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM gitlab_publications").fetchone()[0] == 0


def test_pilot_write_is_admin_only_and_preserves_file_config(settings: Settings) -> None:
    """拒绝未认证、只读账号和超出契约的写入，私有配置仍按原方式管理。"""

    client, _store = comparison_app(settings)
    with client:
        pilot = f"{PATH}/pilot"
        assert client.put(pilot, json={"enabled": False}).status_code == 401
        assert client.put(pilot, headers=ADMIN, json={
            "enabled": False, "repository_id": 2,
        }).status_code == 422
        assert client.put(pilot, headers=ADMIN, json={"enabled": False}).json()[
            "detail"]["code"] == "pilot_config_managed"
        create_user(client, "admin", "admin")
        create_user(client, "reader", "reader")
        enable_users(client)
        reader = {"Authorization": f"Bearer {login(client, 'reader')['token']}"}
        assert client.put(pilot, headers=reader, json={"enabled": True}).status_code == 403
        assert client.get(PATH, headers=reader).json()["pilot"]["manageable"] is False
