"""验证连接诊断只由 Worker 执行，失败不泄露凭据且重启不重复发送。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from ocr_manager import checks, worker
from ocr_manager.config import Settings
from ocr_manager.ocr import check_model_connection
from ocr_manager.storage import Store

ADMIN = {"X-Admin-Token": "test-admin-token"}


def add_repository(client: TestClient) -> int:
    """使用管理接口保存加密的合成仓库凭据。"""

    response = client.post(
        "/api/repositories",
        headers=ADMIN,
        json={
            "name": "诊断项目",
            "gitlab_url": "https://gitlab.example.test",
            "project_id": 42,
            "remote_url": "git@gitlab.example.test:team/repo.git",
            "target_branch": "release/main",
            "auth_kind": "secret",
            "webhook_token": "test-webhook-token-123",
            "feishu_webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/private-test-token",
        },
    )
    assert response.status_code == 201
    return int(response.json()["id"])


def test_git_check_is_queued_then_run_by_worker(
    client: TestClient, settings: Settings, monkeypatch: Any
) -> None:
    """HTTP 只写队列，同一仓库的未完成测试不能重复启动。"""

    repository_id = add_repository(client)
    calls: list[str] = []

    class FakeGit:
        """记录 Worker 到 Git 的调用，拒绝 HTTP 阶段偷偷访问外部系统。"""

        def __init__(self, _root: Path, _repo: dict[str, Any]) -> None:
            pass

        def check_access(self) -> None:
            calls.append("git")

    monkeypatch.setattr(checks, "GitRepository", FakeGit)
    payload = {"kind": "git", "repository_id": repository_id}
    response = client.post("/api/connection-checks", headers=ADMIN, json=payload)
    assert response.status_code == 202
    assert calls == []
    assert client.post("/api/connection-checks", headers=ADMIN, json=payload).status_code == 409
    store = Store(settings.data_dir / "app.db")
    assert worker.run_once(store, settings)[0]
    assert calls == ["git"]
    rows = client.get("/api/connection-checks", headers=ADMIN).json()
    assert rows[0]["status"] == "passed"
    assert rows[0]["repository_id"] == repository_id
    assert client.post("/api/connection-checks", headers=ADMIN, json=payload).status_code == 202


def test_model_check_uses_saved_secret_without_returning_it(
    client: TestClient, settings: Settings, monkeypatch: Any
) -> None:
    """测试读取最新加密模型配置，诊断表与 API 均不保存明文密钥。"""

    saved = client.post(
        "/api/model-profiles",
        headers=ADMIN,
        json={
            "name": "连接测试模型",
            "provider": "dashscope",
            "model": "qwen-test",
            "api_key": "private-model-key",
        },
    )
    assert saved.status_code == 201
    assert (
        client.post(f"/api/model-profiles/{saved.json()['id']}/activate", headers=ADMIN).status_code
        == 200
    )
    captured: list[tuple[str, str, Path]] = []

    def fake_model_check(model_settings: Settings, run_dir: Path) -> None:
        captured.append((model_settings.ocr_model, model_settings.ocr_api_key, run_dir))

    monkeypatch.setattr(checks, "check_model_connection", fake_model_check)
    assert (
        client.post(
            "/api/connection-checks", headers=ADMIN, json={"kind": "model", "repository_id": 1}
        ).status_code
        == 422
    )
    response = client.post("/api/connection-checks", headers=ADMIN, json={"kind": "model"})
    assert response.status_code == 202
    assert worker.run_once(Store(settings.data_dir / "app.db"), settings)[0]
    assert captured[0][0:2] == ("qwen-test", "private-model-key")
    assert captured[0][2].parent == settings.data_dir / "checks"
    assert "private-model-key" not in client.get("/api/connection-checks", headers=ADMIN).text


def test_feishu_error_is_redacted_and_interrupted_check_is_not_replayed(
    client: TestClient, settings: Settings, monkeypatch: Any
) -> None:
    """失败信息不能含 webhook，重启不重发可能已到群里的测试消息。"""

    repository_id = add_repository(client)

    def fail_send(url: str) -> None:
        raise httpx.ConnectError(f"failed for {url}")

    monkeypatch.setattr(checks, "send_connection_test", fail_send)
    payload = {"kind": "feishu", "repository_id": repository_id}
    assert client.post("/api/connection-checks", headers=ADMIN, json=payload).status_code == 202
    store = Store(settings.data_dir / "app.db")
    assert worker.run_once(store, settings)[0]
    rows = client.get("/api/connection-checks", headers=ADMIN).json()
    assert rows[0]["status"] == "failed"
    assert rows[0]["error"] == "feishu 网络连接失败"
    assert "private-test-token" not in str(rows)

    assert client.post("/api/connection-checks", headers=ADMIN, json=payload).status_code == 202
    running = store.next_connection_check()
    assert running is not None
    store.recover()
    assert store.list_connection_checks()[0]["status"] == "failed"
    assert store.next_connection_check() is None


def test_model_probe_uses_isolated_config_and_only_exposes_http_status(
    settings: Settings, tmp_path: Path, monkeypatch: Any
) -> None:
    """模型密钥只进入子进程环境，CLI 错误响应只提取可展示的状态码。"""

    from ocr_manager import ocr

    calls: list[tuple[list[str], dict[str, str], Path]] = []

    def fake_command(
        command: list[str], env: dict[str, str], checkout: Path, _timeout: int
    ) -> tuple[int, str]:
        calls.append((command, env, checkout))
        if command[-2:] == ["llm", "test"]:
            return 1, '401 Unauthorized {"token":"private-model-key"}'
        return 0, ""

    monkeypatch.setattr(ocr, "run_ocr_command", fake_command)
    model_settings = Settings(**(settings.__dict__ | {"ocr_api_key": "private-model-key"}))
    with pytest.raises(RuntimeError, match="HTTP 401") as error:
        check_model_connection(model_settings, tmp_path / "check")
    assert len(calls) == 3
    assert all("private-model-key" not in " ".join(command) for command, _, _ in calls)
    assert all(env["HOME"] == str(tmp_path / "check" / "home") for _, env, _ in calls)
    assert calls[-1][1]["OCR_LLM_TOKEN"] == "private-model-key"
    assert "private-model-key" not in str(error.value)
