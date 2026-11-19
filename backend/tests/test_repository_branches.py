"""多分支的订阅、版本身份和迁移测试；只用隔离数据库与合成远程响应。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from ocr_manager import repository_discovery
from ocr_manager.config import Settings
from ocr_manager.premerge import enqueue_premerge
from ocr_manager.repository_discovery import claim_discovery, execute_discovery
from ocr_manager.storage import SCHEMA_VERSION, Store
from test_webhook import merge_payload

ADMIN = {"X-Admin-Token": "test-admin-token"}
SECRET = "synthetic-webhook-secret-123"
A, B = "a" * 40, "b" * 40


def create(client: TestClient, **overrides: Any) -> httpx.Response:
    """通过真实接口创建多分支配置，不发远程请求。"""

    return client.post(
        "/api/repositories",
        headers=ADMIN,
        json={
            "name": "多分支合成项目",
            "gitlab_url": "https://gitlab.example.test",
            "project_id": 42,
            "remote_url": "git@gitlab.example.test:team/repo.git",
            "target_branches": ["main", "release/test"],
            "webhook_token": SECRET,
            "enable_merge_requests": False,
            "enable_default_branch_pushes": True,
            "premerge_enabled": True,
            **overrides,
        },
    )


def test_multibranch_push_and_mr_use_actual_branch(client: TestClient, settings: Settings) -> None:
    """相同提交 Push 到不同订阅分支分别入队；预审保留实际分支，不跨分支去重。"""

    response = create(client)
    assert response.status_code == 201, response.text
    rid = response.json()["id"]
    assert response.json()["target_branches"] == ["main", "release/test"]
    store = Store(settings.data_dir / "app.db")
    headers = {"X-Gitlab-Token": SECRET, "X-Gitlab-Event": "Push Hook"}
    for branch in ["main", "release/test"]:
        payload = {
            "object_kind": "push",
            "project": {"id": 42},
            "ref": f"refs/heads/{branch}",
            "before": A,
            "after": B,
        }
        assert (
            client.post("/api/webhooks/gitlab", headers=headers, json=payload).json()["status"]
            == "queued"
        )
        assert (
            client.post("/api/webhooks/gitlab", headers=headers, json=payload).json()["status"]
            == "duplicate"
        )
    for event in store.list_events():
        store.finish_event(event["id"], [B], {B: ("snapshot", "rule")}, None, base_sha=A)
    jobs = [store.get_job(job["id"]) for job in store.list_jobs()]
    assert len(jobs) == 2 and {job["target_branch"] for job in jobs} == {"main", "release/test"}
    mr = merge_payload("open", "release/test")
    mr["object_attributes"]["last_commit"] = {"id": A}
    mr_headers = {"X-Gitlab-Token": SECRET, "X-Gitlab-Event": "Merge Request Hook"}
    assert (
        client.post("/api/webhooks/gitlab", headers=mr_headers, json=mr).json()["status"]
        == "queued"
    )
    latest = store.get_job(store.list_jobs()[0]["id"])
    assert latest["source"] == "premerge" and latest["target_branch"] == "release/test"
    assert not enqueue_premerge(store, rid, 7, A, target_branch="release/test")
    assert enqueue_premerge(store, rid, 7, A, target_branch="main")
    assert store.get_job(store.list_jobs()[0]["id"])["target_branch"] == "main"
    mr["object_attributes"]["target_branch"] = "not-subscribed"
    assert client.post("/api/webhooks/gitlab", headers=mr_headers, json=mr).status_code == 204


def test_selection_validation_overlap_and_active_protection(
    client: TestClient, settings: Settings
) -> None:
    """拒绝空集合、非法分支、跨记录重叠及在途修改；取消选择不能丢失既有任务证据。"""

    assert create(client, target_branches=[]).status_code == 422
    assert create(client, target_branches=["main", "bad..branch"]).status_code == 422
    response = create(client)
    rid = response.json()["id"]
    assert create(client, target_branches=["release/test", "other"]).status_code == 409
    assert create(client, target_branches=["other"]).status_code == 201
    store = Store(settings.data_dir / "app.db")
    assert enqueue_premerge(store, rid, 7, B, target_branch="release/test")
    saved = client.post(
        f"/api/repositories/{rid}", headers=ADMIN, json={"target_branches": ["main"]}
    )
    assert saved.status_code == 409
    assert json.loads(store.get_repository(rid)["target_branches"]) == ["main", "release/test"]


def test_context_only_save_preserves_trigger(client: TestClient) -> None:
    """背景接口省略 enabled 时保留基础接入刚保存的开关，避免隐藏重复草稿覆盖。"""

    rid = create(client).json()["id"]
    result = client.put(
        f"/api/repositories/{rid}/premerge",
        headers=ADMIN,
        json={"include_description": True, "context_paths": []},
    )
    assert result.status_code == 200 and result.json()["enabled"] is True
    assert (
        client.post(
            f"/api/repositories/{rid}", headers=ADMIN, json={"premerge_enabled": False}
        ).status_code
        == 200
    )
    result = client.put(
        f"/api/repositories/{rid}/premerge",
        headers=ADMIN,
        json={"include_description": False, "context_paths": []},
    )
    assert result.json()["enabled"] is False


def test_all_selected_branches_require_worker_evidence(
    client: TestClient,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """不能用核验过的一条分支给另一条伪造分支背书；查询和保存都不在 HTTP 发网络。"""

    real = httpx.Client

    def respond(request: httpx.Request) -> httpx.Response:
        if "/repository/branches" in request.url.path:
            return httpx.Response(200, json=[{"name": "main"}, {"name": "release/test"}])
        return httpx.Response(
            200,
            json={
                "id": 42,
                "name": "可信项目",
                "path_with_namespace": "team/repo",
                "default_branch": "main",
            },
        )

    monkeypatch.setattr(
        repository_discovery.httpx,
        "Client",
        lambda **kw: real(transport=httpx.MockTransport(respond), **kw),
    )
    store = Store(settings.data_dir / "app.db")
    queued = client.post(
        "/api/repository-query-sessions",
        headers=ADMIN,
        json={
            "remote_url": "https://gitlab.example.test/team/repo.git",
            "gitlab_token": "synthetic",
        },
    )
    sid = queued.json()["session_id"]
    execute_discovery(store, settings, claim_discovery(store))
    client.post(f"/api/repository-query-sessions/{sid}/branches", headers=ADMIN, json={})
    execute_discovery(store, settings, claim_discovery(store))
    payload = {
        "name": "伪造名称",
        "gitlab_url": "https://gitlab.example.test",
        "project_id": 42,
        "remote_url": "https://gitlab.example.test/team/repo.git",
        "gitlab_token": "synthetic",
        "query_session_id": sid,
        "target_branches": ["main", "unverified"],
    }
    assert client.post("/api/repositories", headers=ADMIN, json=payload).status_code == 409
    payload["target_branches"] = ["main", "release/test"]
    saved = client.post("/api/repositories", headers=ADMIN, json=payload)
    assert saved.status_code == 201 and saved.json()["name"] == "可信项目"
    assert saved.json()["target_branches"] == ["main", "release/test"]


def test_v53_migration_keeps_history_and_moves_merge_subscription(tmp_path: Path) -> None:
    """从真实 53 版备份副本升级，只迁移配置，不创建任务或历史投递。"""

    # 直接重放迁移序列得到 53 版合成库，不依赖运行库或私有配置。
    from ocr_manager import storage

    original = storage.MULTIBRANCH_MIGRATION
    storage.MULTIBRANCH_MIGRATION = ""
    store = Store(tmp_path / "migration.db")
    try:
        store.migrate()
    finally:
        storage.MULTIBRANCH_MIGRATION = original
    with store.connection() as db:
        db.execute("PRAGMA user_version=53")
        db.execute(
            "INSERT INTO repositories(name,gitlab_url,project_id,remote_url,target_branch,"
            "auth_kind,webhook_secret,feishu_webhook,enable_merge_requests) "
            "VALUES('合成','https://gitlab.test',42,'git@gitlab.test:t/r.git','release/test',"
            "'secret','','',1)"
        )
    store.migrate()
    repo = store.get_repository(1)
    assert repo["target_branch"] == "release/test"
    assert json.loads(repo["target_branches"]) == ["release/test"]
    assert repo["enable_merge_requests"] == 0 and repo["enable_default_branch_pushes"] == 1
    with store.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not db.execute("PRAGMA foreign_key_check").fetchall()
        assert db.execute("SELECT COUNT(*) FROM review_jobs").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM notification_deliveries").fetchone()[0] == 0
    store.migrate()


def test_reuse_cannot_cross_target_branch(client: TestClient, settings: Settings) -> None:
    """相同 MR 和 SHA 改投另一分支时，旧范围不得成为当前分支的去重证据。"""

    from ocr_manager.merge_review_reuse import merged_range
    from test_unified_reviews import Client, Git

    rid = create(client).json()["id"]
    store = Store(settings.data_dir / "app.db")
    assert enqueue_premerge(store, rid, 7, B, target_branch="release/test")
    repository = store.get_repository(rid)
    mr = Client().get_merge_request()
    assert merged_range(store, repository, mr, Git(), Client()) is None
    mr["target_branch"] = "release/test"
    matched = merged_range(
        store, {**repository, "target_branch": "release/test"}, mr, Git(), Client()
    )
    assert matched is not None
    with store.connection() as db:
        assert (
            db.execute("SELECT target_branch FROM merged_review_ranges").fetchone()[0]
            == "release/test"
        )


def test_branch_array_edit_has_audit_and_invalidates_checks(
    client: TestClient, settings: Settings
) -> None:
    """新增第二分支不改变首分支也必须有配置版本，旧连接成功不再代表全部分支。"""

    rid = create(client, target_branches=["main"]).json()["id"]
    store = Store(settings.data_dir / "app.db")
    check = store.enqueue_connection_check("gitlab", rid)
    store.next_connection_check()
    store.finish_connection_check(check, None)
    assert store.list_connection_checks()[0]["config_current"]
    result = client.post(
        f"/api/repositories/{rid}",
        headers=ADMIN,
        json={"target_branches": ["main", "release/test"]},
    )
    assert result.status_code == 200
    assert not store.list_connection_checks()[0]["config_current"]
    with store.connection() as db:
        after = json.loads(
            db.execute(
                "SELECT after_json FROM config_revisions WHERE object_type="
                "'repository' AND object_id=? ORDER BY id DESC LIMIT 1",
                (rid,),
            ).fetchone()[0]
        )
        assert json.loads(after["target_branches"]) == ["main", "release/test"]
