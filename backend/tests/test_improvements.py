"""验证平台台账的持久化、鉴权、证据、并发与迁移；只操作合成临时数据库。"""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from ocr_manager import storage
from ocr_manager.api import create_app
from ocr_manager.config import Settings
from ocr_manager.improvement_contracts import ImprovementCreate, ImprovementUpdate
from ocr_manager.improvements import create_improvement, update_improvement
from ocr_manager.storage import Store
from schema_fixtures import remove_improvement_schema
from test_auth import create_user, enable_users, login
from test_task_operations import populate

ADMIN = {"X-Admin-Token": "test-admin-token"}


def _payload(**changes: object) -> dict[str, object]:
    return {"client_key": str(uuid4()), "title": "长任务导致通知等待", "kind": "problem",
            "category": "stability", "description": "合成任务运行期间通知未推进",
            "analysis": "待确认", "next_steps": "检查执行槽", **changes}


def test_persistence_search_history_and_audit(client: TestClient, settings: Settings) -> None:
    """重建 API 后数据仍在；每次编辑追加旧快照，审计不保存请求正文。"""

    payload = _payload()
    response = client.post("/api/improvements", headers=ADMIN, json=payload)
    assert response.status_code == 201, response.text
    record = response.json()
    record_id = record["id"]
    assert record["code_state"] == "unchanged"
    assert record["verification_state"] == "not_run"
    assert record["deployment_state"] == "not_deployed"
    assert "client_key" not in record
    changed = {key: value for key, value in record.items()
               if key not in {"id", "version", "created_at", "updated_at",
                   "archived_at", "archived_by", "archive_reason"}}
    changed.update({"title": "通知已解耦", "status": "resolved", "solution": "隔离投递执行槽",
                    "code_state": "modified", "verification_state": "passed",
                    "validation_evidence": "合成用例通过，未调用真实飞书",
                    "expected_version": 1, "progress_note": "完成本地修复，未部署"})
    saved = client.put(f"/api/improvements/{record_id}", headers=ADMIN, json=changed)
    assert saved.status_code == 200, saved.text
    assert saved.json()["version"] == 2 and saved.json()["deployment_state"] == "not_deployed"
    history = client.get(f"/api/improvements/{record_id}/history?page_size=1", headers=ADMIN).json()
    assert history["total"] == 2 and history["items"][0]["version"] == 2
    old = client.get(f"/api/improvements/{record_id}/history?page_size=1&page=2",
                     headers=ADMIN).json()["items"][0]
    assert old["snapshot"]["title"] == payload["title"]
    assert old["snapshot"]["verification_state"] == "not_run"
    assert old["actor"] == "共享管理员"
    with TestClient(create_app(settings)) as restarted:
        current = restarted.get(f"/api/improvements/{record_id}", headers=ADMIN)
        assert current.json()["title"] == "通知已解耦"
        filtered = restarted.get("/api/improvements?q=执行槽&status=resolved&kind=problem"
                                 "&category=stability", headers=ADMIN).json()
        assert filtered["total"] == 1
    audit = client.get("/api/audit-logs", headers=ADMIN).json()["items"]
    update = next(item for item in audit if item["action"] == "PUT /api/improvements/{record_id}")
    assert update["object_type"] == "project_improvement" and update["object_id"] == record_id
    assert "隔离投递执行槽" not in str(audit)


def test_creation_replay_and_version_conflict(client: TestClient) -> None:
    """重复创建不增加记录；错误复用创建键及旧版本保存均保留原事实。"""

    payload = _payload()
    first = client.post("/api/improvements", headers=ADMIN, json=payload).json()
    replay = client.post("/api/improvements", headers=ADMIN, json=payload).json()
    assert replay["id"] == first["id"]
    assert client.get("/api/improvements", headers=ADMIN).json()["total"] == 1
    assert client.post("/api/improvements", headers=ADMIN,
                       json={**payload, "title": "不同事项"}).status_code == 409
    update = {key: value for key, value in payload.items() if key != "client_key"}
    update.update({"expected_version": 1, "progress_note": "追加尚未解决的进展",
                   "status": "investigating"})
    endpoint = f"/api/improvements/{first['id']}"
    assert client.put(endpoint, headers=ADMIN, json=update).status_code == 200
    assert client.put(endpoint, headers=ADMIN, json=update).status_code == 409
    replay_after_update = client.post("/api/improvements", headers=ADMIN, json=payload).json()
    assert replay_after_update["version"] == 2
    assert client.get(endpoint + "/history", headers=ADMIN).json()["total"] == 2


@pytest.mark.parametrize("changes", [
    {"title": "   "}, {"description": "\n "}, {"kind": "unknown"}, {"category": "unknown"},
    {"status": "resolved"}, {"verification_state": "passed"},
    {"verification_state": "failed"}, {"verification_state": "blocked"},
    {"verification_state": "not_applicable"}, {"deployment_state": "confirmed"},
    {"deployment_state": "not_applicable"}, {"api_key": "不应接收的字段"},
])
def test_rejects_invalid_or_unproven_claims(client: TestClient, changes: dict[str, object]) -> None:
    """不能把缺失的验证证据或部署证据保存为成功结论。"""

    response = client.post("/api/improvements", headers=ADMIN, json=_payload(**changes))
    assert response.status_code == 422, response.text
    assert client.get("/api/improvements", headers=ADMIN).json()["total"] == 0


def test_auth_not_found_and_filter_validation(client: TestClient) -> None:
    """管理员专用读写；直接访问接口也不能绕过菜单权限。"""

    assert client.get("/api/improvements").status_code == 401
    assert client.post("/api/improvements", json=_payload()).status_code == 401
    for path in ["/api/improvements/999", "/api/improvements/999/history"]:
        assert client.get(path, headers=ADMIN).status_code == 404
    for query in ["page=0", "page_size=101", "status=bad", "kind=bad", "category=bad"]:
        assert client.get(f"/api/improvements?{query}", headers=ADMIN).status_code == 422
    assert client.get("/api/improvements?q=%25' OR 1=1", headers=ADMIN).json()["total"] == 0
    create_user(client, "admin", "admin")
    create_user(client, "reader", "reader")
    enable_users(client)
    session = login(client, "reader")
    headers = {"Authorization": f"Bearer {session['token']}"}
    assert client.get("/api/improvements", headers=headers).status_code == 403
    assert client.get("/api/improvements/1", headers=headers).status_code == 403
    assert client.get("/api/improvements/1/history", headers=headers).status_code == 403
    assert client.post("/api/improvements", headers=headers, json=_payload()).status_code == 403
    assert client.put("/api/improvements/1", headers=headers, json={}).status_code == 403


def test_concurrent_creation_and_updates_are_atomic(tmp_path: Path) -> None:
    """独立连接同时写入只接受一份版本，冲突不增加历史。"""

    store = Store(tmp_path / "app.db")
    store.migrate()
    payload = ImprovementCreate.model_validate(_payload())
    with ThreadPoolExecutor(max_workers=2) as pool:
        created = list(pool.map(
            lambda _: create_improvement(store, payload, "合成操作者"), range(2)))
    assert created[0].id == created[1].id
    content = payload.model_dump(exclude={"client_key"})
    update = ImprovementUpdate.model_validate({**content, "expected_version": 1,
                                               "progress_note": "并发保存"})

    def save(_: int) -> str:
        try:
            update_improvement(store, created[0].id, update, "合成操作者")
        except ValueError:
            return "conflict"
        return "saved"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(save, range(2))) == ["conflict", "saved"]
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM project_improvement_revisions").fetchone()[0] == 2


def test_history_failure_rolls_back_current_record(tmp_path: Path) -> None:
    """历史快照写入失败时，当前摘要和版本也必须回滚。"""

    store = Store(tmp_path / "app.db")
    store.migrate()
    payload = ImprovementCreate.model_validate(_payload())
    record = create_improvement(store, payload, "合成操作者")
    with store.connection() as db:
        db.execute("""CREATE TRIGGER reject_revision BEFORE INSERT ON project_improvement_revisions
            BEGIN SELECT RAISE(ABORT,'synthetic history failure'); END""")
    update = ImprovementUpdate.model_validate({**payload.model_dump(exclude={"client_key"}),
        "title": "不能半保存", "expected_version": 1, "progress_note": "合成失败"})
    with pytest.raises(sqlite3.IntegrityError):
        update_improvement(store, record.id, update, "合成操作者")
    with store.connection() as db:
        current = db.execute("SELECT title,version FROM project_improvements").fetchone()
        assert current["version"] == 1 and current["title"] == payload.title
        assert db.execute("SELECT COUNT(*) FROM project_improvement_revisions").fetchone()[0] == 1


def test_schema39_upgrade_rolls_back_and_preserves_existing_state(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """旧库独立迁移失败整版回滚，重试及重复升级不会导入或改写历史任务。"""

    store, _ = populate(client, settings, 1)
    with store.connection() as db:
        before = [tuple(row) for row in db.execute("SELECT * FROM review_jobs ORDER BY id")]
        assert before
        remove_improvement_schema(db)
        db.execute("PRAGMA user_version=38")
    script = storage.IMPROVEMENT_MIGRATION
    monkeypatch.setattr(storage, "IMPROVEMENT_MIGRATION", script + "INVALID SYNTHETIC SQL;")
    with pytest.raises(sqlite3.OperationalError):
        store.migrate()
    with store.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 38
        assert not db.execute("SELECT name FROM sqlite_master WHERE name LIKE 'project_improv%'")\
            .fetchall()
    monkeypatch.setattr(storage, "IMPROVEMENT_MIGRATION", script)
    store.migrate()
    store.migrate()
    with store.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == storage.SCHEMA_VERSION
        assert db.execute("SELECT COUNT(*) FROM project_improvements").fetchone()[0] == 0
        assert [tuple(row) for row in db.execute("SELECT * FROM review_jobs ORDER BY id")] == before


def test_list_pagination_and_literal_search(client: TestClient) -> None:
    """分页稳定、不跨页重复；搜索中的百分号按文字而非 SQL 通配符处理。"""

    for index in range(26):
        response = client.post("/api/improvements", headers=ADMIN, json=_payload(
            title=f"合成记录 {index}", description="等待 100% 核验" if index == 0 else "普通记录",
            kind="improvement" if index == 0 else "problem"))
        assert response.status_code == 201
    first = client.get("/api/improvements", headers=ADMIN).json()
    second = client.get("/api/improvements?page=2", headers=ADMIN).json()
    assert first["total"] == 26 and len(first["items"]) == 25
    assert len(second["items"]) == 1
    assert not ({item["id"] for item in first["items"]} &
                {item["id"] for item in second["items"]})
    literal = client.get("/api/improvements?q=%25&kind=improvement", headers=ADMIN).json()
    assert literal["total"] == 1 and literal["items"][0]["title"] == "合成记录 0"


def test_document_only_resolution_and_independent_deployment(client: TestClient) -> None:
    """纯文档可以说明验证不适用；确认部署也不会自动冒充本地验证通过。"""

    document = client.post("/api/improvements", headers=ADMIN, json=_payload(
        status="resolved", code_state="not_applicable", solution="补充执行约定",
        verification_state="not_applicable", validation_evidence="纯文档说明，无业务代码执行",
        deployment_state="not_applicable", deployment_evidence="仓库文档，不涉及服务部署"))
    assert document.status_code == 201, document.text
    deployed = client.post("/api/improvements", headers=ADMIN, json=_payload(
        deployment_state="confirmed", deployment_evidence="合成环境核对版本和健康状态"))
    assert deployed.status_code == 201
    assert deployed.json()["verification_state"] == "not_run"
