"""使用隔离数据库及网络替身验证目标版本、异步资料获取和凭据边界。"""
from __future__ import annotations

import sqlite3
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from ocr_manager import checks, storage, worker
from ocr_manager.config import Settings
from ocr_manager.repository_discovery import claim_discovery, discovery_source
from ocr_manager.storage import Store
from schema_fixtures import remove_onboarding_schema

ADMIN = {"X-Admin-Token": "test-admin-token"}


def model(client: TestClient, name: str) -> int:
    """保存合成模型，不激活也不调用外部服务。"""

    response = client.post("/api/model-profiles", headers=ADMIN, json={
        "name": name, "model": name, "provider": "openai", "api_key": "synthetic-secret"})
    assert response.status_code == 201
    return int(response.json()["id"])


def test_explicit_model_target_and_version_races(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """非默认目标可测试；前后配置变化拒绝错误通过，默认切换不影响独立身份。"""

    first, second = model(client, "first"), model(client, "second")
    client.post(f"/api/model-profiles/{first}/activate", headers=ADMIN)
    store = Store(settings.data_dir / "app.db")
    calls: list[str] = []

    def probe(config: Settings, _: Any) -> None:
        calls.append(config.ocr_model)

    monkeypatch.setattr(checks, "check_model_connection", probe)
    payload = {"kind": "model", "model_profile_id": second}
    assert client.post("/api/connection-checks", json=payload).status_code == 401
    assert client.post("/api/connection-checks", headers=ADMIN, json=payload).status_code == 202
    assert calls == []
    assert client.post("/api/connection-checks", headers=ADMIN, json=payload).status_code == 409
    worker.run_once(store, settings)
    assert calls == ["second"]
    assert store.list_connection_checks()[0]["config_current"]
    assert store.get_model_profile()["id"] == first
    client.post(f"/api/model-profiles/{second}/activate", headers=ADMIN)
    assert store.list_connection_checks()[0]["config_current"]
    client.post(f"/api/model-profiles/{second}", headers=ADMIN, json={"model": "changed"})
    assert not store.list_connection_checks()[0]["config_current"]
    client.post("/api/connection-checks", headers=ADMIN, json=payload)
    client.post(f"/api/model-profiles/{second}", headers=ADMIN, json={"model": "again"})
    worker.run_once(store, settings)
    assert calls == ["second"]
    assert store.list_connection_checks()[0]["status"] == "failed"

    def racing_probe(_: Settings, __: Any) -> None:
        client.post(f"/api/model-profiles/{second}", headers=ADMIN, json={"model": "late"})

    monkeypatch.setattr(checks, "check_model_connection", racing_probe)
    client.post("/api/connection-checks", headers=ADMIN, json=payload)
    worker.run_once(store, settings)
    result = store.list_connection_checks()[0]
    assert result["status"] == "failed" and not result["config_current"]
    assert "synthetic-secret" not in client.get("/api/connection-checks", headers=ADMIN).text


def test_independent_notification_target_and_deleted_target(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """未绑定仓库的通道仍可测试，删除后不得发出排队中的消息。"""

    target = client.post("/api/notification-targets", headers=ADMIN, json={
        "name": "合成通知", "webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/fake"})
    assert target.status_code == 201
    calls: list[str] = []
    monkeypatch.setattr(checks, "send_connection_test", lambda url: calls.append(url))
    payload = {"kind": "feishu", "notification_target_id": target.json()["id"]}
    store = Store(settings.data_dir / "app.db")
    assert client.post("/api/connection-checks", headers=ADMIN, json=payload).status_code == 202
    assert calls == []
    worker.run_once(store, settings)
    assert len(calls) == 1 and store.list_connection_checks()[0]["status"] == "passed"
    client.post("/api/connection-checks", headers=ADMIN, json=payload)
    client.delete(f"/api/notification-targets/{target.json()['id']}", headers=ADMIN)
    worker.run_once(store, settings)
    assert len(calls) == 1 and store.list_connection_checks()[0]["status"] == "failed"


@pytest.mark.parametrize("url", ["https://[invalid/a/b", "https://localhost./a/b",
    "https://gitlab.test:0/a/b", "https://gitlab.test:wrong/a/b", "http://gitlab.test/a/b",
    "https://user:pass@gitlab.test/a/b",
    "https://localhost/a/b", "https://127.0.0.1/a/b", "https://[::1]/a/b",
    "https://gitlab.test/a/../b", "https://gitlab.test/a/b?token=fake"])
def test_discovery_rejects_unsafe_source(url: str) -> None:
    """不接受隐含凭据、本地目标、路径穿越或非 HTTPS。"""

    with pytest.raises(ValueError):
        discovery_source(url)


@pytest.mark.parametrize("scenario", ["passed", "redirect", "wrong_project", "large", "error"])
def test_discovery_worker_only_bounded_and_redacted(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch, scenario: str,
) -> None:
    """HTTP 仅加密入队，Worker 固定同源路径、禁止跳转且仅保存安全字段。"""

    calls: list[str] = []
    real_client = httpx.Client

    def response(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        assert request.headers["PRIVATE-TOKEN"] == "synthetic-token"
        if scenario == "redirect":
            return httpx.Response(302, headers={"location": "https://other.test/steal"})
        if scenario == "error":
            return httpx.Response(401, text="synthetic-token private-response")
        if scenario == "large":
            return httpx.Response(200, content=b"x" * (1024 * 1024 + 1))
        return httpx.Response(200, json={"id": 22, "name": "合成项目", "default_branch": "develop",
            "path_with_namespace": "team/repo" if scenario == "passed" else "other/repo",
            "http_url_to_repo": "https://other.test/untrusted", "private": "private-response"})

    def fake_client(**kwargs: Any) -> httpx.Client:
        assert kwargs["follow_redirects"] is False
        return real_client(transport=httpx.MockTransport(response), **kwargs)

    store = Store(settings.data_dir / "app.db")
    monkeypatch.setattr("ocr_manager.repository_discovery.httpx.Client", fake_client)
    payload = {"remote_url": "https://gitlab.test/team/repo", "gitlab_token": "synthetic-token"}
    assert client.post("/api/repository-discoveries", json=payload).status_code == 401
    queued = client.post("/api/repository-discoveries", headers=ADMIN, json=payload)
    assert queued.status_code == 202 and calls == []
    task_id = queued.json()["id"]
    assert worker.run_once(store, settings)[0]
    result = client.get(f"/api/repository-discoveries/{task_id}", headers=ADMIN)
    assert result.json()["status"] == ("passed" if scenario == "passed" else "failed")
    assert len(calls) == 1 and "/api/v4/projects/team%2Frepo" in calls[0]
    assert "synthetic-token" not in result.text and "private-response" not in result.text
    with store.connection() as db:
        assert db.execute("SELECT token_ciphertext FROM repository_discoveries").fetchone()[0] == ""
    if scenario == "passed":
        assert result.json()["result"]["remote_url"] == "https://gitlab.test/team/repo.git"


def test_discovery_cancel_expiry_and_recovery(client: TestClient, settings: Settings) -> None:
    """取消及过期立即清除临时令牌；中断不重复读取，迟到结果不能覆盖取消。"""

    store = Store(settings.data_dir / "app.db")
    payload = {"remote_url": "https://gitlab.test/team/repo", "gitlab_token": "synthetic-token"}
    first = client.post("/api/repository-discoveries", headers=ADMIN, json=payload).json()["id"]
    client.delete(f"/api/repository-discoveries/{first}", headers=ADMIN)
    assert claim_discovery(store) is None
    second = client.post("/api/repository-discoveries", headers=ADMIN, json=payload).json()["id"]
    task = claim_discovery(store)
    assert task
    store.recover()
    with store.connection() as db:
        rows = db.execute("SELECT token_ciphertext FROM repository_discoveries")
        assert all(row[0] == "" for row in rows)
        db.execute("INSERT INTO repository_discoveries(remote_url,token_ciphertext,created_at) "
                   "VALUES('https://gitlab.test/a/b','cipher','2000-01-01')")
    assert claim_discovery(store) is None
    response = client.get(f"/api/repository-discoveries/{second}", headers=ADMIN)
    assert response.json()["status"] == "failed"


def test_migration_preserves_history_and_rolls_back(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """升级不补造历史版本证明，失败回滚结构与版本，重复迁移不改变数据。"""

    store = Store(settings.data_dir / "app.db")
    with store.connection() as db:
        remove_onboarding_schema(db)
        db.execute("INSERT INTO connection_checks(kind,status) VALUES('model','passed')")
        db.execute("PRAGMA user_version=51")
    script = storage.ONBOARDING_MIGRATION
    monkeypatch.setattr(storage, "ONBOARDING_MIGRATION", script + "INVALID;")
    with pytest.raises(sqlite3.OperationalError):
        store.migrate()
    with store.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 51
        columns = {row[1] for row in db.execute("PRAGMA table_info(connection_checks)")}
        assert "config_fingerprint" not in columns
    monkeypatch.setattr(storage, "ONBOARDING_MIGRATION", script)
    store.migrate()
    store.migrate()
    assert store.list_connection_checks()[0]["status"] == "passed"
    assert not store.list_connection_checks()[0]["config_current"]
    with store.connection() as db:
        assert not db.execute("PRAGMA foreign_key_check").fetchall()
    assert client.get("/api/deployment-summary").status_code == 401
    safe = client.get("/api/deployment-summary", headers=ADMIN)
    assert safe.status_code == 200
    assert settings.master_key not in safe.text and "synthetic-secret" not in safe.text
