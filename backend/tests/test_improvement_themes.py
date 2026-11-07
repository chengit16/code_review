"""验证优化主题、阶段快照和问题关系；仅使用合成内容与临时 SQLite。"""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from ocr_manager import storage
from ocr_manager.config import Settings
from ocr_manager.improvement_theme_contracts import ImprovementThemeCreate, ImprovementThemeUpdate
from ocr_manager.improvement_themes import create_theme, update_theme
from ocr_manager.storage import Store
from schema_fixtures import remove_improvement_theme_schema
from test_auth import create_user, enable_users, login

ADMIN = {"X-Admin-Token": "test-admin-token"}


def _phase(**changes: object) -> dict[str, object]:
    return {"title": "阶段一：明确问题", "goal": "记录并量化合成故障",
            "status": "planned", **changes}


def _theme(**changes: object) -> dict[str, object]:
    return {"client_key": str(uuid4()), "title": "评审稳定性优化",
            "category": "stability", "status": "active", "scope": "评审调度",
            "objective": "降低任务阻塞并保留失败证据", "rationale": "多种任务竞争单 Worker",
            "next_steps": "观察试点队列数据", "phases": [_phase()], **changes}


def _record_issue(client: TestClient, title: str) -> int:
    response = client.post("/api/improvements", headers=ADMIN, json={
        "client_key": str(uuid4()), "title": title, "description": f"合成问题：{title}",
    })
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def test_theme_create_link_stage_history_and_search(client: TestClient) -> None:
    """主题和多阶段有序保存；显式关联可检索，每个完整版本保留原快照。"""

    issue_a = _record_issue(client, "模型长任务阻塞")
    issue_b = _record_issue(client, "通知发送等待")
    payload = _theme(improvement_ids=[issue_a, issue_b])
    created = client.post("/api/improvement-themes", headers=ADMIN, json=payload)
    assert created.status_code == 201, created.text
    original = created.json()
    theme_id = original["id"]
    assert original["version"] == 1
    assert [phase["title"] for phase in original["phases"]] == ["阶段一：明确问题"]
    assert original["improvement_ids"] == [issue_a, issue_b]
    replay = client.post("/api/improvement-themes", headers=ADMIN, json=payload)
    assert replay.json()["id"] == theme_id and replay.json()["version"] == 1
    changed = {key: value for key, value in original.items()
               if key not in {"id", "version", "created_at", "updated_at",
                   "archived_at", "archived_by", "archive_reason", "improvement_ids"}}
    changed.update({"title": "有界调度和投递解耦", "status": "active",
        "phases": [_phase(status="completed", solution="分离投递槽", verification_state="passed",
            validation_evidence="合成调度用例通过，未调用真实飞书"),
            _phase(title="阶段二：观察队列", status="active", goal="建立试点观察口径")],
        "expected_version": 1, "progress_note": "完成隔离阶段并开始观察",
        "improvement_ids": [issue_b]})
    updated = client.put(f"/api/improvement-themes/{theme_id}", headers=ADMIN, json=changed)
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] == 2 and updated.json()["improvement_ids"] == [issue_b]
    assert [phase["title"] for phase in updated.json()["phases"]] == [
        "阶段一：明确问题", "阶段二：观察队列"]
    history = client.get(f"/api/improvement-themes/{theme_id}/history?page_size=1",
                         headers=ADMIN).json()
    assert history["total"] == 2 and history["items"][0]["version"] == 2
    old = client.get(f"/api/improvement-themes/{theme_id}/history?page=2&page_size=1",
                     headers=ADMIN).json()["items"][0]
    assert old["snapshot"]["title"] == payload["title"]
    assert old["snapshot"]["phases"][0]["status"] == "planned"
    assert old["improvement_ids"] == [issue_a, issue_b]
    linked = client.get(f"/api/improvement-themes?improvement_id={issue_b}", headers=ADMIN).json()
    assert linked["total"] == 1 and linked["items"][0]["id"] == theme_id
    excluded = client.get(f"/api/improvement-themes?improvement_id={issue_a}",
                          headers=ADMIN).json()
    assert excluded["total"] == 0
    assert client.get(f"/api/improvement-themes/{theme_id}", headers=ADMIN).json()["version"] == 2


@pytest.mark.parametrize("changes", [
    {"improvement_ids": [1, 1]}, {"improvement_ids": [99999]},
    {"status": "completed"}, {"phases": [_phase(status="completed")]},
    {"phases": [_phase(status="completed", solution="已实现", verification_state="passed")]},
    {"phases": [_phase(verification_state="passed")]},
    {"phases": [_phase(deployment_state="confirmed")]},
    {"phases": [_phase(status="unknown")]},
    {"phases": [_phase() for _ in range(51)]},
])
def test_invalid_theme_phase_and_links_are_rejected(client: TestClient,
                                                    changes: dict[str, object]) -> None:
    """阶段结论不能凭状态下拉伪造；错误关联和超量阶段不写入数据库。"""

    response = client.post("/api/improvement-themes", headers=ADMIN, json=_theme(**changes))
    expected_status = 409 if changes.get("improvement_ids") == [99999] else 422
    assert response.status_code == expected_status, response.text
    assert client.get("/api/improvement-themes", headers=ADMIN).json()["total"] == 0


def test_theme_conflict_idempotency_and_atomic_revision(client: TestClient) -> None:
    """创建重放不覆写，版本冲突或无效关联不增加主题、阶段和历史。"""

    issue = _record_issue(client, "待关联记录")
    payload = _theme(improvement_ids=[issue])
    created = client.post("/api/improvement-themes", headers=ADMIN, json=payload).json()
    payload_update = {
        key: value for key, value in created.items()
        if key not in {"id", "version", "created_at", "updated_at",
                   "archived_at", "archived_by", "archive_reason", "improvement_ids"}
    }
    payload_update.update({"expected_version": 1, "progress_note": "已增加阶段",
        "phases": [_phase(), _phase(title="阶段二", goal="合成验证")], "improvement_ids": []})
    endpoint = f"/api/improvement-themes/{created['id']}"
    assert client.put(endpoint, headers=ADMIN, json=payload_update).status_code == 200
    assert client.put(endpoint, headers=ADMIN, json=payload_update).status_code == 409
    replay = client.post("/api/improvement-themes", headers=ADMIN, json=payload)
    assert replay.json()["version"] == 2
    invalid = {**payload_update, "expected_version": 2, "improvement_ids": [99999]}
    assert client.put(endpoint, headers=ADMIN, json=invalid).status_code == 409
    current = client.get(endpoint, headers=ADMIN).json()
    assert current["version"] == 2 and current["improvement_ids"] == []
    assert len(current["phases"]) == 2
    assert client.get(endpoint + "/history", headers=ADMIN).json()["total"] == 2


def test_theme_auth_not_found_and_filter_validation(client: TestClient) -> None:
    """管理员鉴权覆盖列表、详情和历史；筛选值与分页上限有明确边界。"""

    assert client.get("/api/improvement-themes").status_code == 401
    assert client.post("/api/improvement-themes", json=_theme()).status_code == 401
    assert client.get("/api/improvement-themes/999", headers=ADMIN).status_code == 404
    assert client.get("/api/improvement-themes/999/history", headers=ADMIN).status_code == 404
    for query in ["status=bad", "category=bad", "page=0", "page_size=101", "improvement_id=0"]:
        assert client.get(f"/api/improvement-themes?{query}", headers=ADMIN).status_code == 422
    create_user(client, "admin", "admin")
    create_user(client, "reader", "reader")
    enable_users(client)
    session = login(client, "reader")
    headers = {"Authorization": f"Bearer {session['token']}"}
    for path in ["/api/improvement-themes", "/api/improvement-themes/1",
                 "/api/improvement-themes/1/history"]:
        assert client.get(path, headers=headers).status_code == 403
    assert client.post("/api/improvement-themes", headers=headers, json=_theme()).status_code == 403
    assert client.put("/api/improvement-themes/1", headers=headers, json={}).status_code == 403


def test_completed_theme_does_not_claim_deployment_or_resolve_issue(client: TestClient) -> None:
    """阶段本地验收不提升为已部署；主题完成不修改关联问题的处理状态。"""

    issue = _record_issue(client, "尚未确认生产效果")
    payload = _theme(status="completed", outcome="完成合成隔离测试", improvement_ids=[issue],
        phases=[_phase(status="completed", solution="添加边界检查", code_state="modified",
            verification_state="passed", validation_evidence="仅合成验证")])
    response = client.post("/api/improvement-themes", headers=ADMIN, json=payload)
    assert response.status_code == 201, response.text
    assert response.json()["phases"][0]["deployment_state"] == "not_deployed"
    assert client.get(f"/api/improvements/{issue}", headers=ADMIN).json()["status"] == "open"
    conflict = client.post("/api/improvement-themes", headers=ADMIN,
                           json={**payload, "title": "不能复用同键覆盖"})
    assert conflict.status_code == 409
    audit = client.get("/api/audit-logs", headers=ADMIN).json()["items"]
    assert any(item["object_type"] == "improvement_theme" for item in audit)
    assert "完成合成隔离测试" not in str(audit)


def test_theme_list_pagination_and_literal_search(client: TestClient) -> None:
    """稳定分页保留阶段顺序，文字查询与组合筛选不解释 SQL 通配符。"""

    for index in range(26):
        response = client.post("/api/improvement-themes", headers=ADMIN, json=_theme(
            title=f"合成主题 {index}", objective="等待 100% 核验" if index == 0 else "普通目标"))
        assert response.status_code == 201
    first = client.get("/api/improvement-themes", headers=ADMIN).json()
    second = client.get("/api/improvement-themes?page=2", headers=ADMIN).json()
    assert first["total"] == 26 and len(first["items"]) == 25
    assert len(second["items"]) == 1
    assert not ({item["id"] for item in first["items"]} &
                {item["id"] for item in second["items"]})
    literal = client.get("/api/improvement-themes?q=%25&status=active&category=stability",
                         headers=ADMIN).json()
    assert literal["total"] == 1 and literal["items"][0]["title"] == "合成主题 0"
    assert client.get("/api/improvement-themes?q=%25' OR 1=1", headers=ADMIN).json()["total"] == 0


def test_theme_migration_transaction_preserves_preexisting_problem_data(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """40 版迁移失败整版回滚，既有问题保留且不自动推断主题归属。"""

    issue_id = _record_issue(client, "迁移前存在的问题")
    from ocr_manager.improvement_theme_migration import IMPROVEMENT_THEME_MIGRATION

    store = Store(settings.data_dir / "app.db")
    with store.connection() as db:
        remove_improvement_theme_schema(db)
        db.execute("PRAGMA user_version=39")
    script = storage.IMPROVEMENT_THEME_MIGRATION
    monkeypatch.setattr(storage, "IMPROVEMENT_THEME_MIGRATION", script + "INVALID THEME SQL;")
    with pytest.raises(sqlite3.OperationalError):
        store.migrate()
    with store.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 39
        assert not db.execute("SELECT name FROM sqlite_master WHERE name='improvement_themes'")\
            .fetchone()
        assert db.execute("SELECT id FROM project_improvements WHERE id=?", (issue_id,)).fetchone()
    monkeypatch.setattr(storage, "IMPROVEMENT_THEME_MIGRATION", IMPROVEMENT_THEME_MIGRATION)
    store.migrate()
    store.migrate()
    with store.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == storage.SCHEMA_VERSION
        assert db.execute("SELECT COUNT(*) FROM improvement_themes").fetchone()[0] == 0
        assert db.execute("SELECT id FROM project_improvements WHERE id=?", (issue_id,)).fetchone()


def test_theme_concurrent_update_and_history_failure_rollback(tmp_path: Path) -> None:
    """相同创建键与阶段版本并发保护；写历史失败不留下局部阶段替换。"""

    store = Store(tmp_path / "app.db")
    store.migrate()
    payload = ImprovementThemeCreate.model_validate(_theme())
    with ThreadPoolExecutor(max_workers=2) as pool:
        created = list(pool.map(lambda _: create_theme(store, payload, "合成操作者"), range(2)))
    assert created[0].id == created[1].id
    update = ImprovementThemeUpdate.model_validate({
        **payload.model_dump(exclude={"client_key"}), "expected_version": 1,
        "progress_note": "并发阶段更新", "improvement_ids": [],
        "phases": [_phase(title="并发版本")],
    })

    def save(_: int) -> str:
        try:
            update_theme(store, created[0].id, update, "合成操作者")
        except ValueError:
            return "conflict"
        return "saved"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(save, range(2))) == ["conflict", "saved"]
    with store.connection() as db:
        db.execute("""CREATE TRIGGER reject_theme_revision
            BEFORE INSERT ON improvement_theme_revisions
            BEGIN SELECT RAISE(ABORT,'synthetic history failure'); END""")
    version_two = update.model_copy(update={"expected_version": 2, "progress_note": "事务回滚"})
    with pytest.raises(sqlite3.IntegrityError):
        update_theme(store, created[0].id, version_two, "合成操作者")
    with store.connection() as db:
        theme = db.execute("SELECT title,version FROM improvement_themes").fetchone()
        phase = db.execute("SELECT title FROM improvement_theme_phases").fetchone()
        assert theme["version"] == 2 and phase["title"] == "并发版本"
        assert db.execute("SELECT COUNT(*) FROM improvement_theme_revisions").fetchone()[0] == 2
