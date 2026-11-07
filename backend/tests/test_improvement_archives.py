"""归档只在临时库执行，保护权限、版本、完整快照、独立状态与旧库迁移边界。"""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from ocr_manager import storage
from ocr_manager.config import Settings
from ocr_manager.improvement_archive_contracts import ArchiveChange
from ocr_manager.improvement_archives import change_archive
from ocr_manager.improvement_contracts import ImprovementCreate, ImprovementUpdate
from ocr_manager.improvements import create_improvement, update_improvement
from ocr_manager.storage import Store
from schema_fixtures import remove_improvement_archive_schema
from test_auth import create_user, enable_users, login

ADMIN = {"X-Admin-Token": "test-admin-token"}
RESOURCES = ["improvements", "improvement-themes"]


def _create(client: TestClient, resource: str) -> tuple[str, dict[str, object]]:
    payload: dict[str, object] = {"client_key": str(uuid4()), "title": "归档合成事项",
                                  "category": "security"}
    if resource == "improvements":
        payload.update(description="尚未解决，等待部署", code_state="modified",
                       verification_state="passed", validation_evidence="仅合成检查")
    else:
        payload.update(objective="保留优化过程", phases=[{"title": "待实施", "goal": "边界验证"}])
    response = client.post(f"/api/{resource}", headers=ADMIN, json=payload)
    assert response.status_code == 201, response.text
    return f"/api/{resource}/{response.json()['id']}", payload


def _archive(client: TestClient, path: str, version: int = 1,
             archived: bool = True) -> dict[str, object]:
    response = client.post(path + "/archive", headers=ADMIN, json={
        "expected_version": version, "archived": archived, "reason": "合成归档或恢复原因"})
    assert response.status_code == 200, response.text
    return dict(response.json())


@pytest.mark.parametrize("resource", RESOURCES)
def test_archive_restore_keeps_content_history_and_creation_replay(
    client: TestClient, resource: str,
) -> None:
    """任意进展可收纳，但不解决问题；历史记录动作、原因、操作者和当时归档事实。"""

    path, payload = _create(client, resource)
    before = client.get(path, headers=ADMIN).json()
    archived = _archive(client, path)
    metadata = {"version", "updated_at", "archived_at", "archived_by", "archive_reason"}
    assert archived["version"] == 2 and archived["archived_at"]
    assert archived["archived_by"] and archived["archive_reason"] == "合成归档或恢复原因"
    assert {k: v for k, v in before.items() if k not in metadata} == {
        k: v for k, v in archived.items() if k not in metadata}
    replay = client.post(f"/api/{resource}", headers=ADMIN, json=payload)
    assert replay.json()["version"] == 2 and replay.json()["archived_at"]
    history = client.get(path + "/history?page_size=1", headers=ADMIN).json()
    assert history["total"] == 2 and history["items"][0]["action"] == "archive"
    assert history["items"][0]["archived_at"] == archived["archived_at"]
    restored = _archive(client, path, 2, False)
    assert restored["version"] == 3 and restored["archived_at"] is None
    assert restored["archived_by"] == restored["archive_reason"] == ""
    histories = client.get(path + "/history", headers=ADMIN).json()["items"]
    assert [row["action"] for row in histories] == ["restore", "archive", "create"]
    assert histories[0]["note"] == "合成归档或恢复原因"
    assert histories[0]["snapshot"] == histories[1]["snapshot"] == histories[2]["snapshot"]
    audit = client.get("/api/audit-logs", headers=ADMIN).json()["items"]
    identifier = "record_id" if resource == "improvements" else "theme_id"
    assert any(row["action"] == f"POST /api/{resource}/{{{identifier}}}/archive" for row in audit)
    assert "合成归档或恢复原因" not in str(audit)


@pytest.mark.parametrize("resource", RESOURCES)
def test_archived_readonly_and_shared_version_prevent_old_drafts(
    client: TestClient, resource: str,
) -> None:
    """归档中不能编辑；恢复不让归档前草稿重新变得有效；重复转换不留重复历史。"""

    path, payload = _create(client, resource)
    update = {k: v for k, v in payload.items() if k != "client_key"}
    update.update(expected_version=1, progress_note="旧草稿", title="不能静默覆盖")
    _archive(client, path)
    assert client.put(path, headers=ADMIN, json=update).status_code == 409
    for version in [1, 2]:
        duplicate = client.post(path + "/archive", headers=ADMIN, json={
            "expected_version": version, "archived": True, "reason": "重复请求"})
        assert duplicate.status_code == 409
    _archive(client, path, 2, False)
    assert client.put(path, headers=ADMIN, json=update).status_code == 409
    update["expected_version"] = 3
    assert client.put(path, headers=ADMIN, json=update).status_code == 200
    assert client.get(path + "/history", headers=ADMIN).json()["total"] == 4


@pytest.mark.parametrize("resource", RESOURCES)
def test_archive_range_search_and_pagination(client: TestClient, resource: str) -> None:
    """默认只显示未归档；归档及全量范围与原筛选、稳定分页共同生效。"""

    first, _ = _create(client, resource)
    _create(client, resource)
    _archive(client, first)
    base = f"/api/{resource}"
    assert client.get(base, headers=ADMIN).json()["total"] == 1
    archived = client.get(base + "?archive=archived&q=归档&category=security",
                          headers=ADMIN).json()
    assert archived["total"] == 1 and str(archived["items"][0]["id"]) == first.split("/")[-1]
    assert client.get(base + "?archive=archived&category=other", headers=ADMIN).json()["total"] == 0
    pages = [client.get(base + f"?archive=all&page_size=1&page={page}", headers=ADMIN).json()
             for page in [1, 2]]
    assert all(page["total"] == 2 for page in pages)
    assert pages[0]["items"][0]["id"] > pages[1]["items"][0]["id"]
    assert client.get(base + "?archive=bad", headers=ADMIN).status_code == 422


@pytest.mark.parametrize("resource", RESOURCES)
def test_archive_auth_and_validation(client: TestClient, resource: str) -> None:
    """归档与恢复的权限由服务端拒绝，严格校验原因、版本和目标状态。"""

    path, _ = _create(client, resource)
    payload = {"expected_version": 1, "archived": True, "reason": "合成原因"}
    assert client.post(path + "/archive", json=payload).status_code == 401
    for changes in [{"reason": "  "}, {"reason": "字" * 2001}, {"expected_version": 0},
                    {"expected_version": True}, {"archived": "true"}, {"title": "越权字段"}]:
        assert client.post(path + "/archive", headers=ADMIN,
                           json={**payload, **changes}).status_code == 422
    assert client.post(f"/api/{resource}/999/archive", headers=ADMIN,
                       json=payload).status_code == 404
    create_user(client, "admin", "admin")
    create_user(client, "reader", "reader")
    enable_users(client)
    token = login(client, "reader")["token"]
    assert client.post(path + "/archive", headers={"Authorization": f"Bearer {token}"},
                       json=payload).status_code == 403
    assert client.get(path + "/history", headers={"Authorization": f"Bearer {token}"}
                      ).status_code == 403


def test_archiving_either_side_keeps_links_and_summary_attention(client: TestClient) -> None:
    """主题归档不级联问题，所有归档对象继续纳入累计与待办，活动明确按历史次数计数。"""

    issue_path, _ = _create(client, "improvements")
    issue_id = int(issue_path.split("/")[-1])
    theme_path, theme_payload = _create(client, "improvement-themes")
    update = {k: v for k, v in theme_payload.items() if k != "client_key"}
    update.update(expected_version=1, progress_note="建立关联", improvement_ids=[issue_id])
    assert client.put(theme_path, headers=ADMIN, json=update).status_code == 200
    _archive(client, theme_path, 2)
    assert client.get(issue_path, headers=ADMIN).json()["archived_at"] is None
    assert client.get(f"/api/improvement-themes?archive=all&improvement_id={issue_id}",
                      headers=ADMIN).json()["total"] == 1
    _archive(client, issue_path)
    assert client.get(theme_path, headers=ADMIN).json()["improvement_ids"] == [issue_id]
    summary = client.get("/api/improvement-summary?category=security", headers=ADMIN).json()
    assert summary["archived_records"] == summary["archived_themes"] == 1
    assert summary["records"]["total"] == summary["records"]["linked_records"] == 1
    assert summary["themes"]["total"] == summary["themes"]["phases"]["total"] == 1
    assert summary["unresolved"]["total"] == summary["deployment_pending"]["total"] == 1
    assert summary["unresolved"]["items"][0]["archived_at"]
    assert summary["unfinished_themes"]["items"][0]["archived_at"]
    assert sum(day["record_updates"] for day in summary["activity"]) == 1
    assert sum(day["theme_updates"] for day in summary["activity"]) == 2
    assert client.get("/api/improvement-summary?category=other", headers=ADMIN
                      ).json()["archived_records"] == 0


@pytest.mark.parametrize("resource", RESOURCES)
def test_archive_history_failure_rolls_back(
    client: TestClient, settings: Settings, resource: str,
) -> None:
    """注入历史写入失败时不留下元数据、版本或关系的局部更新。"""

    path, _ = _create(client, resource)
    store = Store(settings.data_dir / "app.db")
    table = "project_improvement_revisions" if resource == "improvements" else \
        "improvement_theme_revisions"
    with store.connection() as db:
        db.execute(f"""CREATE TRIGGER reject_archive BEFORE INSERT ON {table}
            BEGIN SELECT RAISE(ABORT,'synthetic archive failure'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        client.post(path + "/archive", headers=ADMIN, json={
            "expected_version": 1, "archived": True, "reason": "失败不可部分提交"})
    current = client.get(path, headers=ADMIN).json()
    assert current["version"] == 1 and current["archived_at"] is None
    assert client.get(path + "/history", headers=ADMIN).json()["total"] == 1


def test_concurrent_archives_share_version(tmp_path: Path) -> None:
    """跨连接归档只能成功一次；响应在同一事务读取自己的已提交版本。"""

    store = Store(tmp_path / "archive.db")
    store.migrate()
    record = create_improvement(store, ImprovementCreate(
        client_key=uuid4(), title="并发归档", description="合成竞争"), "合成用户")
    payload = ArchiveChange(expected_version=1, archived=True, reason="并发原因")

    def save(_: int) -> str:
        try:
            result = change_archive(store, "record", record.id, payload, "合成用户")
            assert result.version == 2 and result.archived_at
            return "saved"
        except ValueError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(save, range(2))) == ["conflict", "saved"]
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM project_improvement_revisions").fetchone()[0] == 2


def test_concurrent_archive_and_edit_cannot_both_commit(tmp_path: Path) -> None:
    """编辑与归档同时使用旧版本时，仅一个提交，失败方不能留下独立历史。"""

    store = Store(tmp_path / "mixed.db")
    store.migrate()
    payload = ImprovementCreate(client_key=uuid4(), title="原始标题", description="并发合成内容")
    record = create_improvement(store, payload, "合成用户")
    update = ImprovementUpdate.model_validate({
        **payload.model_dump(exclude={"client_key"}), "title": "编辑后标题",
        "expected_version": 1, "progress_note": "编辑竞争"})

    def save(operation: str) -> str:
        try:
            if operation == "edit":
                update_improvement(store, record.id, update, "合成用户")
            else:
                change_archive(store, "record", record.id, ArchiveChange(
                    expected_version=1, archived=True, reason="归档竞争"), "合成用户")
            return operation
        except ValueError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save, ["edit", "archive"]))
    assert results.count("conflict") == 1
    with store.connection() as db:
        current = db.execute(
            "SELECT title,version,archived_at FROM project_improvements").fetchone()
        assert current["version"] == 2
        assert (current["archived_at"] is not None) == ("archive" in results)
        assert current["title"] == ("原始标题" if "archive" in results else "编辑后标题")
        assert db.execute("SELECT COUNT(*) FROM project_improvement_revisions").fetchone()[0] == 2


@pytest.mark.parametrize("resource", RESOURCES)
def test_missing_current_snapshot_rejects_archive(
    client: TestClient, settings: Settings, resource: str,
) -> None:
    """已有数据损坏缺失当前历史时，拒绝归档而不提交无快照的新版本。"""

    path, _ = _create(client, resource)
    store = Store(settings.data_dir / "app.db")
    table = "project_improvement_revisions" if resource == "improvements" else \
        "improvement_theme_revisions"
    with store.connection() as db:
        db.execute(f"DELETE FROM {table}")
    response = client.post(path + "/archive", headers=ADMIN, json={
        "expected_version": 1, "archived": True, "reason": "不能掩盖缺失历史"})
    assert response.status_code == 409 and "历史缺失" in response.json()["detail"]
    current = client.get(path, headers=ADMIN).json()
    assert current["version"] == 1 and current["archived_at"] is None


def test_archive_migration_preserves_old_data_and_rolls_back(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """40 版代表性库升级保留内容、关系及旧快照，失败不留下半成品列。"""

    issue_path, _ = _create(client, "improvements")
    theme_path, _ = _create(client, "improvement-themes")
    current = client.get(issue_path, headers=ADMIN).json()
    content = {k: v for k, v in current.items() if k not in {
        "id", "version", "created_at", "updated_at",
        "archived_at", "archived_by", "archive_reason"}}
    content.update(expected_version=1, progress_note="旧版已追加进展", analysis="保留旧版排查")
    assert client.put(issue_path, headers=ADMIN, json=content).status_code == 200
    store = Store(settings.data_dir / "app.db")
    with store.connection() as db:
        db.execute("INSERT INTO improvement_theme_links(theme_id,improvement_id) VALUES(?,?)",
                   (int(theme_path.split("/")[-1]), int(issue_path.split("/")[-1])))
        remove_improvement_archive_schema(db)
        db.execute("PRAGMA user_version=40")
        previous = [tuple(row) for row in db.execute("SELECT * FROM project_improvements")]
    script = storage.IMPROVEMENT_ARCHIVE_MIGRATION
    monkeypatch.setattr(storage, "IMPROVEMENT_ARCHIVE_MIGRATION", script + "INVALID ARCHIVE SQL;")
    with pytest.raises(sqlite3.OperationalError):
        store.migrate()
    with store.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 40
        assert [tuple(row) for row in db.execute("SELECT * FROM project_improvements")] == previous
        columns = {row[1] for row in db.execute("PRAGMA table_info(improvement_themes)")}
        assert "archived_at" not in columns
    monkeypatch.setattr(storage, "IMPROVEMENT_ARCHIVE_MIGRATION", script)
    store.migrate()
    store.migrate()
    assert client.get(issue_path, headers=ADMIN).json()["archived_at"] is None
    assert client.get(theme_path, headers=ADMIN).json()["improvement_ids"]
    history = client.get(issue_path + "/history", headers=ADMIN).json()["items"]
    assert [item["action"] for item in history] == ["update", "create"]
    assert history[0]["snapshot"]["analysis"] == "保留旧版排查"
    assert history[0]["archived_at"] is None
