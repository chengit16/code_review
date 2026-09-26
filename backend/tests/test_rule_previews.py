"""验证规则预览的路径边界、Worker 调用及配置优先级。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from ocr_manager import ocr, worker
from ocr_manager.config import Settings
from ocr_manager.storage import Store

ADMIN = {"X-Admin-Token": "test-admin-token"}
RULE = json.dumps({
    "include": [], "exclude": [],
    "rules": [{"path": "src/*.py", "rule": "检查输入", "merge_system_rule": True}],
}, ensure_ascii=False)


def add_repository(client: TestClient) -> int:
    """使用合成 GitLab 项目测试管理接口，不连接外部服务。"""

    result = client.post("/api/repositories", headers=ADMIN, json={
        "name": "预览项目",
        "gitlab_url": "https://gitlab.example.test",
        "project_id": 42,
        "remote_url": "https://gitlab.example.test/team/repo.git",
        "path_with_namespace": "team/repo",
        "target_branch": "main",
        "gitlab_token": "synthetic-gitlab-token",
    })
    assert result.status_code == 201, result.text
    return int(result.json()["id"])


def test_rule_preview_is_queued_and_path_is_confined(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HTTP 只校验相对路径和入库；实际 Git 与 OCR 在 Worker 中执行。"""

    repository_id = add_repository(client)
    endpoint = f"/api/repositories/{repository_id}/rule-previews"
    for path in ("../secret", "/etc/passwd", "src/../secret", "-help", "src\\file.py", "a\n.py"):
        assert client.post(endpoint, headers=ADMIN, json={"file_path": path}).status_code == 422
    assert client.get(endpoint).status_code == 401
    assert client.post(endpoint, json={"file_path": "src/main.py"}).status_code == 401

    calls: list[str] = []

    class FakeGit:
        """模拟固定提交工作目录，记录 HTTP 与 Worker 的副作用边界。"""

        def __init__(self, _root: Path, _repository: dict[str, Any]) -> None:
            pass

        def fetch(self) -> None:
            calls.append("fetch")

        def target_head(self) -> str:
            return "a" * 40

        def checkout(self, _sha: str, target: Path) -> None:
            calls.append("checkout")
            target.mkdir(parents=True)

        def remove_checkout(self, _target: Path) -> None:
            calls.append("remove")

    def fake_check(
        _settings: Settings, _checkout: Path, _run_dir: Path, path: str,
        _global: str | None, _project: str | None,
    ) -> str:
        calls.append(path)
        return "File: src/main.py\nSource: System built-in\n"

    monkeypatch.setattr(worker, "GitRepository", FakeGit)
    monkeypatch.setattr(worker, "check_rule", fake_check)
    response = client.post(endpoint, headers=ADMIN, json={"file_path": "src/main.py"})
    assert response.status_code == 202
    assert calls == []
    store = Store(settings.data_dir / "app.db")
    assert worker.run_once(store, settings)[0]
    assert calls == ["fetch", "checkout", "src/main.py", "remove"]
    result = client.get(endpoint, headers=ADMIN).json()[0]
    assert result["status"] == "passed"
    assert result["commit_sha"] == "a" * 40
    assert result["output"].startswith("File: src/main.py")


def test_rule_preview_matches_review_rule_layers(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """预览使用隔离 HOME 的全局规则，并由 --rule 显式覆盖项目规则。"""

    captured: list[tuple[list[str], dict[str, str], Path]] = []

    def fake_command(
        command: list[str], env: dict[str, str], checkout: Path, _timeout: float
    ) -> tuple[int, str, str]:
        captured.append((command, env, checkout))
        return 0, "File: src/main.py\nSource: --rule\n", ""

    monkeypatch.setattr(ocr, "_execute_ocr_command", fake_command)
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    output = ocr.check_rule(settings, checkout, tmp_path / "preview", "src/main.py", RULE, RULE)
    assert "Source: --rule" in output
    command, env, cwd = captured[0]
    assert command[:3] == [settings.ocr_command, "rules", "check"]
    assert command[-1] == "src/main.py"
    assert "--rule" in command
    assert Path(command[command.index("--rule") + 1]).read_text(encoding="utf-8") == RULE
    assert (Path(env["HOME"]) / ".opencodereview/rule.json").read_text(encoding="utf-8") == RULE
    assert cwd == checkout


def test_interrupted_rule_preview_is_visible_and_repository_delete_cleans_history(
    client: TestClient, settings: Settings
) -> None:
    """重启不伪装预览成功，删除仓库不留下孤立诊断记录。"""

    repository_id = add_repository(client)
    endpoint = f"/api/repositories/{repository_id}/rule-previews"
    created = client.post(endpoint, headers=ADMIN, json={"file_path": "src/main.py"})
    assert created.status_code == 202
    store = Store(settings.data_dir / "app.db")
    assert store.next_rule_preview() is not None
    store.recover()
    result = client.get(endpoint, headers=ADMIN).json()[0]
    assert result["status"] == "failed"
    assert result["error"] == "Worker 中断，预览结果未确认"
    assert client.delete(f"/api/repositories/{repository_id}", headers=ADMIN).status_code == 200
    assert client.get(endpoint, headers=ADMIN).status_code == 404
