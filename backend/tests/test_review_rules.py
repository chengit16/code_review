"""验证页面规则的持久化、队列保护与 OCR 执行优先级。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from ocr_manager import ocr
from ocr_manager.config import Settings
from ocr_manager.ocr import run_review
from ocr_manager.storage import Store
from ocr_manager.worker import config_hash

ADMIN = {"X-Admin-Token": "test-admin-token"}
RULE = {
    "include": ["**/*.test.ts"],
    "exclude": ["**/generated/**"],
    "rules": [{"path": "src/**/*.ts", "rule": "检查输入校验", "merge_system_rule": True}],
}


def add_repository(client: TestClient) -> int:
    """只创建规则测试需要的仓库身份，不接触真实 GitLab。"""

    response = client.post(
        "/api/repositories",
        headers=ADMIN,
        json={
            "name": "测试仓库",
            "gitlab_url": "https://gitlab.example.test",
            "project_id": 42,
            "remote_url": "https://gitlab.example.test/team/app.git",
            "path_with_namespace": "team/app",
            "target_branch": "main",
            "gitlab_token": "test-token",
        },
    )
    assert response.status_code == 201
    return int(response.json()["id"])


def test_rule_configuration_is_scoped_and_changes_review_snapshot(
    client: TestClient, settings: Settings
) -> None:
    """全局与项目规则各自保存；修改后新评审必须获得不同快照。"""

    repository_id = add_repository(client)
    store = Store(settings.data_dir / "app.db")
    original = config_hash(store, settings, repository_id=repository_id)
    assert client.get("/api/review-rules").status_code == 401
    global_result = client.put("/api/review-rules/global", headers=ADMIN, json=RULE)
    assert global_result.status_code == 200, global_result.text
    global_hash = config_hash(store, settings, repository_id=repository_id)
    assert global_hash != original
    project_rule = {**RULE, "rules": [{**RULE["rules"][0], "rule": "检查授权"}]}
    project_result = client.put(
        f"/api/review-rules/repositories/{repository_id}", headers=ADMIN, json=project_rule
    )
    assert project_result.status_code == 200, project_result.text
    assert config_hash(store, settings, repository_id=repository_id) != global_hash
    listed = client.get("/api/review-rules", headers=ADMIN).json()
    assert {item["repository_id"] for item in listed} == {None, repository_id}
    saved_project = next(item for item in listed if item["repository_id"] == repository_id)
    assert saved_project["content"] == project_rule
    assert client.delete(
        f"/api/review-rules/repositories/{repository_id}", headers=ADMIN
    ).status_code == 200
    assert store.get_review_rule(repository_id) is None
    assert store.get_review_rule(None) is not None
    assert client.delete("/api/review-rules/global", headers=ADMIN).status_code == 200
    assert store.get_review_rule(None) is None


def test_rule_validation_and_pending_job_protection(
    client: TestClient, settings: Settings
) -> None:
    """畸形规则不能保存；排队任务的快照不能被页面修改。"""

    repository_id = add_repository(client)
    for invalid in ({"rules": [{}]}, {"rules": []}, {"include": [""]}):
        assert client.put(
            "/api/review-rules/global", headers=ADMIN, json=invalid
        ).status_code == 422
    assert client.put(
        f"/api/review-rules/repositories/{repository_id}", headers=ADMIN, json=RULE
    ).status_code == 200
    store = Store(settings.data_dir / "app.db")
    assert store.enqueue_mr(repository_id, 7)
    event = store.next_event()
    assert event is not None
    sha = "a" * 40
    snapshot = config_hash(store, settings, repository_id=repository_id)
    store.finish_event(event["id"], [sha], {sha: (snapshot, "")}, None)
    assert client.put(
        f"/api/review-rules/repositories/{repository_id}", headers=ADMIN, json=RULE
    ).status_code == 409
    assert client.put("/api/review-rules/global", headers=ADMIN, json=RULE).status_code == 409


def test_ocr_receives_global_fallback_and_project_override(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """全局规则写入隔离 HOME；项目规则同时传给预览和正式评审。"""

    commands: list[list[str]] = []

    def fake_run(command: list[str], *_args: Any) -> tuple[int, str]:
        commands.append(command)
        output = Path(command[command.index("--output") + 1])
        if "--preview" in command:
            output.write_text(json.dumps({"reviewable_count": 1, "files": [{}]}), encoding="utf-8")
        else:
            output.write_text(json.dumps({
                "manifest": {
                    "schema_version": "ocr.run-manifest/v1",
                    "terminal_state": "complete",
                    "input": {"mode": "commit", "resolved_head": "a" * 40},
                    "coverage": {
                        "selected": [], "completed": [], "reused": [], "failed": [], "waived": []
                    },
                },
                "comments": [],
            }), encoding="utf-8")
        return 0, ""

    monkeypatch.setattr(ocr, "run_ocr_command", fake_run)
    content = json.dumps(RULE, ensure_ascii=False)
    status, _ = run_review(
        settings, tmp_path, tmp_path / "run", "a" * 40,
        global_rule=content, project_rule=content,
    )
    assert status == "complete"
    assert (tmp_path / "run/home/.opencodereview/rule.json").read_text() == content
    assert (tmp_path / "run/managed-rule.json").read_text() == content
    assert len(commands) == 2
    assert all("--rule" in command for command in commands)
    assert all(str(tmp_path / "run/managed-rule.json") in command for command in commands)
    commands.clear()
    assert run_review(
        settings, tmp_path, tmp_path / "fallback", "a" * 40, global_rule=content
    )[0] == "complete"
    assert all("--rule" not in command for command in commands)
    assert (tmp_path / "fallback/home/.opencodereview/rule.json").read_text() == content


def test_deleting_repository_removes_its_managed_rule(
    client: TestClient, settings: Settings
) -> None:
    """项目规则随仓库清理，全局配置继续供其他项目使用。"""

    repository_id = add_repository(client)
    assert client.put("/api/review-rules/global", headers=ADMIN, json=RULE).status_code == 200
    assert client.put(
        f"/api/review-rules/repositories/{repository_id}", headers=ADMIN, json=RULE
    ).status_code == 200
    assert client.delete(f"/api/repositories/{repository_id}", headers=ADMIN).status_code == 200
    store = Store(settings.data_dir / "app.db")
    assert store.get_review_rule(repository_id) is None
    assert store.get_review_rule(None) is not None


def test_rule_history_restores_saved_and_deleted_versions(
    client: TestClient, settings: Settings
) -> None:
    """历史回滚保留旧版本、创建新版本，并重新影响评审快照。"""

    repository_id = add_repository(client)
    endpoint = f"/api/review-rules/repositories/{repository_id}"
    changed = {**RULE, "rules": [{**RULE["rules"][0], "rule": "检查授权"}]}
    assert client.get(f"{endpoint}/revisions").status_code == 401
    assert client.put(endpoint, headers=ADMIN, json=RULE).status_code == 200
    store = Store(settings.data_dir / "app.db")
    initial_hash = config_hash(store, settings, repository_id=repository_id)
    assert client.put(endpoint, headers=ADMIN, json=changed).status_code == 200
    assert client.delete(endpoint, headers=ADMIN).status_code == 200
    revisions = client.get(f"{endpoint}/revisions", headers=ADMIN).json()
    assert [item["action"] for item in revisions] == ["deleted", "saved", "saved"]
    first_id = revisions[-1]["id"]
    restored = client.post(f"{endpoint}/revisions/{first_id}/restore", headers=ADMIN)
    assert restored.status_code == 200
    assert json.loads(store.get_review_rule(repository_id) or "null") == RULE
    assert config_hash(store, settings, repository_id=repository_id) == initial_hash
    assert client.get(f"{endpoint}/revisions", headers=ADMIN).json()[0]["restored_from"] == first_id
    assert client.post(f"{endpoint}/revisions/9999/restore", headers=ADMIN).status_code == 404
    global_endpoint = "/api/review-rules/global"
    wrong_scope = client.post(f"{global_endpoint}/revisions/{first_id}/restore", headers=ADMIN)
    assert wrong_scope.status_code == 404


def test_rule_restore_respects_pending_job_lock(client: TestClient, settings: Settings) -> None:
    """恢复历史不能绕过已有排队评审的配置快照锁。"""

    repository_id = add_repository(client)
    endpoint = f"/api/review-rules/repositories/{repository_id}"
    assert client.put(endpoint, headers=ADMIN, json=RULE).status_code == 200
    revision_id = client.get(f"{endpoint}/revisions", headers=ADMIN).json()[0]["id"]
    store = Store(settings.data_dir / "app.db")
    assert store.enqueue_mr(repository_id, 7)
    event = store.next_event()
    assert event is not None
    sha = "a" * 40
    snapshot = config_hash(store, settings, repository_id=repository_id)
    store.finish_event(event["id"], [sha], {sha: (snapshot, "")}, None)
    assert client.post(
        f"{endpoint}/revisions/{revision_id}/restore", headers=ADMIN
    ).status_code == 409
    assert len(client.get(f"{endpoint}/revisions", headers=ADMIN).json()) == 1
