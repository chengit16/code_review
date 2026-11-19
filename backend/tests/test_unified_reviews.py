"""合成数据库与网络替身验证统一任务、版本复用、分支分页和凭据主机隔离。"""

from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from ocr_manager import repository_discovery, storage
from ocr_manager.config import Settings
from ocr_manager.merge_review_reuse import push_ranges, reuse_merge
from ocr_manager.premerge import enqueue_premerge
from ocr_manager.repository_discovery import claim_discovery, execute_discovery
from ocr_manager.storage import Store
from schema_fixtures import remove_unified_schema
from test_premerge import ADMIN, WEBHOOK, create_repository, payload

A, B, C, D = (letter * 40 for letter in "abcd")


def source(client: TestClient, settings: Settings) -> tuple[Store, int, int]:
    """建立合并前版本，任务尚未执行也必须可被后续合并事件关联。"""

    rid = create_repository(client)
    assert (
        client.post(
            f"/api/repositories/{rid}",
            headers=ADMIN,
            json={"gitlab_token": "synthetic-token", "enable_default_branch_pushes": True},
        ).status_code
        == 200
    )
    client.put(f"/api/repositories/{rid}/premerge", headers=ADMIN, json={"enabled": True})
    store = Store(settings.data_dir / "app.db")
    assert enqueue_premerge(store, rid, 7, B)
    return store, rid, int(store.list_jobs()[0]["id"])


class Git:
    """模拟精确相同的差异和包含额外直接提交的第一父链。"""

    def fetch_mr_head(self, *_: Any) -> None:
        """不调用 Git。"""

    def first_parent(self, sha: str) -> str:
        """合并产物 C 的第一父节点固定为 A。"""

        assert sha == C
        return A

    def is_on_target(self, _: str) -> bool:
        """固定目标可达。"""

        return True

    def is_range_base(self, *_: str) -> bool:
        """固定连续范围。"""

        return True

    def range_signature(self, *_: str) -> str:
        """二进制和文本差异已由适配器精确比较。"""

        return "same-exact-diff"

    def first_parent_range(self, _: str, after: str) -> list[str]:
        """D 是合并后的独立直接提交。"""

        return [C, D] if after == D else [C]


class Client:
    """返回可信 merged MR；提交关联索引为空也不妨碍已知版本复用。"""

    def get_merge_request(self, *_: Any) -> dict[str, Any]:
        """同版本 MR 身份和 diff refs。"""

        return {
            "iid": 7,
            "state": "merged",
            "target_project_id": 42,
            "target_branch": "main",
            "sha": B,
            "merge_commit_sha": C,
            "diff_refs": {"base_sha": A, "head_sha": B},
        }

    def commit_merge_requests(self, *_: Any) -> list[int]:
        """异步提交索引暂未更新。"""

        return []


@pytest.mark.parametrize(
    "status", ["queued", "running", "complete", "partial", "failed", "cancelled", "skipped"]
)
def test_merge_and_push_reuse_original_state(
    client: TestClient, settings: Settings, status: str
) -> None:
    """不同执行状态均复用原任务；Push 不重跑失败，不把其改为完成。"""

    store, rid, jid = source(client, settings)
    with store.connection() as db:
        db.execute("UPDATE review_jobs SET status=?,base_sha=? WHERE id=?", (status, A, jid))
    assert store.add_event(rid, 7, "merge", C, None)
    event = store.next_event()
    assert event
    repository = store.get_repository(rid)
    assert repository
    assert reuse_merge(store, event, repository, Client().get_merge_request(), Git(), Client())
    ranges, reused = push_ranges(store, {}, repository, Git(), Client(), A, C)
    assert ranges == [] and reused == [jid]
    job = store.get_job(jid)
    assert job and job["status"] == status and job["mr_state"] == "merged"
    assert len(store.list_jobs()) == 1
    assert job["event_links"][-1]["relation"] == "reused"
    assert client.get("/api/task-search?source=premerge", headers=ADMIN).json()["total"] == 1


def test_mixed_push_new_version_and_concurrent_events(
    client: TestClient, settings: Settings
) -> None:
    """混合 Push 仅排未审尾段；并发重复 webhook 和新版输入不串用旧结果。"""

    store, rid, jid = source(client, settings)
    repository = store.get_repository(rid)
    assert repository
    ranges, reused = push_ranges(store, {}, repository, Git(), Client(), A, D)
    assert ranges == [(C, D)] and reused == [jid]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: enqueue_premerge(store, rid, 7, D), range(8)))
    assert sum(results) == 1
    assert store.get_job(jid)["superseded"] == 1
    assert len(store.list_jobs()) == 2
    assert not enqueue_premerge(store, rid, 7, D)
    response = client.post(f"/api/webhooks/gitlab/{rid}", headers=WEBHOOK, json=payload(D, "merge"))
    assert response.status_code == 200
    assert store.get_job(store.list_jobs()[0]["id"])["superseded"] == 0


def test_legacy_migration_is_atomic_and_never_notifies(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """模拟 schema 52 的终态预审；迁移回滚、旧映射及重复迁移均可验证。"""

    store, rid, _ = source(client, settings)
    with store.connection() as db:
        remove_unified_schema(db)
        db.execute(
            "UPDATE premerge_reviews SET status='complete',attempts=1,result_json=?",
            (json.dumps({"comments": []}),),
        )
        db.execute("PRAGMA user_version=52")
    script = storage.UNIFIED_REVIEW_MIGRATION
    monkeypatch.setattr(storage, "UNIFIED_REVIEW_MIGRATION", script + "INVALID;")
    with pytest.raises(sqlite3.OperationalError):
        store.migrate()
    with store.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 52
        assert "source" not in {row[1] for row in db.execute("PRAGMA table_info(review_jobs)")}
    monkeypatch.setattr(storage, "UNIFIED_REVIEW_MIGRATION", script)
    store.migrate()
    store.migrate()
    assert len(store.list_jobs()) == 1
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM notification_deliveries").fetchone()[0] == 0
        assert not db.execute("PRAGMA foreign_key_check").fetchall()
    assert (
        client.get("/api/premerge-reviews/1", headers=ADMIN).json()["job_id"]
        == store.list_jobs()[0]["id"]
    )


def test_query_sessions_remote_pagination_and_saved_credentials(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HTTP 仅入队；Worker 分页搜索，隐藏身份来自引用；换主机不能挪用旧 Token。"""

    store, rid, _ = source(client, settings)
    calls: list[httpx.Request] = []
    real = httpx.Client

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.headers["PRIVATE-TOKEN"] == "synthetic-token"
        if "/repository/branches" in request.url.path:
            return httpx.Response(200, json=[{"name": "release/second", "default": False}])
        return httpx.Response(
            200,
            json={
                "id": 42,
                "name": "自动识别名称",
                "path_with_namespace": "team/repo",
                "default_branch": "main",
            },
        )

    monkeypatch.setattr(
        repository_discovery.httpx,
        "Client",
        lambda **kw: real(transport=httpx.MockTransport(respond), **kw),
    )
    queued = client.post(
        "/api/repository-query-sessions",
        headers=ADMIN,
        json={"remote_url": "https://gitlab.example.test/team/repo.git", "repository_id": rid},
    )
    assert queued.status_code == 202 and calls == []
    session = queued.json()["session_id"]
    task = claim_discovery(store)
    assert task
    execute_discovery(store, settings, task)
    branch = client.post(
        f"/api/repository-query-sessions/{session}/branches",
        headers=ADMIN,
        json={"search": "second", "page": 2},
    )
    assert branch.status_code == 202
    task = claim_discovery(store)
    assert task
    execute_discovery(store, settings, task)
    assert calls[-1].url.params["page"] == "2" and calls[-1].url.params["search"] == "second"
    saved = client.post(
        f"/api/repositories/{rid}",
        headers=ADMIN,
        json={
            "query_session_id": session,
            "remote_url": "https://gitlab.example.test/team/repo.git",
            "target_branch": "release/second",
            "name": "伪造名称",
        },
    )
    # 在途任务保护仍有效，不能因为持有识别引用而绕过。
    assert saved.status_code == 409
    unsafe = client.post(
        "/api/repository-query-sessions",
        headers=ADMIN,
        json={"remote_url": "https://other.example.test/team/repo.git", "repository_id": rid},
    )
    assert unsafe.status_code == 422
    with store.connection() as db:
        db.execute("UPDATE repository_query_sessions SET expires_at='2000-01-01'")
    assert (
        client.post(
            f"/api/repository-query-sessions/{session}/branches", headers=ADMIN, json={}
        ).status_code
        == 409
    )
    with store.connection() as db:
        assert (
            db.execute("SELECT token_ciphertext FROM repository_query_sessions").fetchone()[0] == ""
        )


def test_manual_new_configuration_stays_current_and_reuses_merged_range(
    client: TestClient,
    settings: Settings,
) -> None:
    """人工按新配置重审后，重复 MR 事件和后续 Push 不得复活旧任务。"""

    store, rid, jid = source(client, settings)
    repository = store.get_repository(rid)
    assert repository
    from ocr_manager.merge_review_reuse import merged_range

    assert merged_range(store, repository, Client().get_merge_request(), Git(), Client())
    store.finish_job(jid, "failed", None, None, "合成故障")
    new_id = store.retry_job(jid, "manual-current-config")
    assert new_id and new_id != jid
    assert not enqueue_premerge(store, rid, 7, B)
    ranges, reused = push_ranges(store, {}, repository, Git(), Client(), A, C)
    assert ranges == [] and reused == [new_id]
    assert store.get_job(jid)["superseded"] == 1
    assert store.get_job(new_id)["superseded"] == 0
    with store.connection() as db:
        db.execute("DELETE FROM review_jobs WHERE id=?", (new_id,))
    assert not enqueue_premerge(store, rid, 7, B)
    with pytest.raises(ValueError, match="已删除"):
        push_ranges(store, {}, repository, Git(), Client(), A, C)


def test_saved_query_reference_is_authoritative_and_credentials_rotate(
    client: TestClient,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """真正执行合成 Worker 查询后保存；引用不能跨会话或沿用轮换后的旧凭据。"""

    from ocr_manager.secrets import SecretBox

    store = Store(settings.data_dir / "app.db")
    real = httpx.Client

    def respond(request: httpx.Request) -> httpx.Response:
        if "/repository/branches" in request.url.path:
            return httpx.Response(200, json=[{"name": "release/second"}])
        return httpx.Response(
            200,
            json={
                "id": 99,
                "name": "可信名称",
                "path_with_namespace": "team/new",
                "default_branch": "main",
            },
        )

    monkeypatch.setattr(
        repository_discovery.httpx,
        "Client",
        lambda **kw: real(transport=httpx.MockTransport(respond), **kw),
    )
    queued = client.post(
        "/api/repository-query-sessions",
        headers=ADMIN,
        json={"remote_url": "https://gitlab.example.test/team/new", "gitlab_token": "secret"},
    )
    assert queued.status_code == 202
    sid = queued.json()["session_id"]
    execute_discovery(store, settings, claim_discovery(store))
    client.post(
        f"/api/repository-query-sessions/{sid}/branches",
        headers=ADMIN,
        json={"search": "second", "page": 2},
    )
    execute_discovery(store, settings, claim_discovery(store))
    saved = client.post(
        "/api/repositories",
        headers=ADMIN,
        json={
            "query_session_id": sid,
            "remote_url": "https://gitlab.example.test/team/new.git",
            "gitlab_token": "secret",
            "name": "伪造",
            "project_id": 111,
            "path_with_namespace": "other/project",
            "gitlab_url": "https://other.test",
            "target_branch": "release/second",
            "auth_kind": "secret",
            "premerge_enabled": True,
        },
    )
    assert saved.status_code == 201, saved.text
    rid = saved.json()["id"]
    assert saved.json()["name"] == "可信名称" and saved.json()["project_id"] == 99
    edit = client.post(
        "/api/repository-query-sessions",
        headers=ADMIN,
        json={"repository_id": rid, "remote_url": "https://gitlab.example.test/team/new.git"},
    )
    assert edit.status_code == 202
    edit_sid = edit.json()["session_id"]
    with store.connection() as db:
        db.execute(
            "UPDATE repositories SET gitlab_token_ciphertext=? WHERE id=?",
            (SecretBox(settings.master_key).encrypt("rotated"), rid),
        )
    assert (
        client.post(
            f"/api/repository-query-sessions/{edit_sid}/branches", headers=ADMIN, json={}
        ).status_code
        == 409
    )
    # 轮换后仍可取消当前所有者自己的会话，并立即清除队列副本中的临时凭据。
    assert (
        client.delete(f"/api/repository-query-sessions/{edit_sid}", headers=ADMIN).status_code
        == 200
    )
    with store.connection() as db:
        assert not db.execute(
            "SELECT token_ciphertext FROM repository_query_sessions WHERE id=?", (edit_sid,)
        ).fetchone()[0]
        assert not db.execute(
            "SELECT token_ciphertext FROM repository_discoveries WHERE query_session_id=?",
            (edit_sid,),
        ).fetchone()[0]


@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/api/repository-query-sessions"),
        ("post", "/api/repository-query-sessions/unknown/branches"),
        ("delete", "/api/repository-query-sessions/unknown"),
        ("post", "/api/events/1/full-review"),
    ],
)
def test_unified_management_routes_require_authorization(
    client: TestClient,
    method: str,
    path: str,
) -> None:
    """新增管理写入不可绕过现有管理鉴权。"""

    response = client.request(method.upper(), path, json={})
    assert response.status_code in {401, 403}


def test_late_version_verification_does_not_invalidate_newer_task(
    client: TestClient,
    settings: Settings,
) -> None:
    """旧 OCR 完成后的迟到核验只撤销自身及更旧版本，不取消已入队的新版本。"""

    from ocr_manager.unified_premerge import verify_version

    store, rid, jid = source(client, settings)
    old = store.get_job(jid)
    repository = store.get_repository(rid)
    assert old and repository
    assert enqueue_premerge(store, rid, 7, D)
    newest = store.list_jobs()[0]["id"]

    class NewClient:
        """返回可信的当前新头。"""

        def get_merge_request(self, *_: Any) -> dict[str, Any]:
            return {"state": "opened", "sha": D, "target_project_id": 42, "target_branch": "main"}

    with pytest.raises(ValueError, match="输入已变化"):
        verify_version(store, repository, old, NewClient())
    assert store.get_job(newest)["superseded"] == 0
    assert store.get_job(newest)["status"] == "queued"
    assert len(store.list_jobs()) == 2


def test_disabled_premerge_queue_does_not_block_other_sources(
    client: TestClient,
    settings: Settings,
) -> None:
    """关闭合并前领取后，保留历史排队不会阻塞同仓库后来的普通任务。"""

    store, rid, _ = source(client, settings)
    assert store.update_repository(rid, {"premerge_enabled": False})
    assert store.add_event(rid, 9, "later-merge", D, None)
    event = store.next_event()
    assert event
    store.finish_event(event["id"], [D], {D: ("config", "")}, None)
    task = store.next_job()
    assert task and task["source"] == "mr" and task["commit_sha"] == D
