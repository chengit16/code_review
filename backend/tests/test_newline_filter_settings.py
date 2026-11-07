"""验证过滤开关的默认值、快照、合并前冻结与第 37 版迁移；不接触业务库。"""

from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient
from ocr_manager import storage
from ocr_manager.config import Settings
from ocr_manager.premerge import enqueue_premerge, next_premerge
from ocr_manager.worker import config_hash, configuration_snapshot, review_premerge, review_settings
from schema_fixtures import remove_improvement_maintenance_schema
from test_task_operations import populate

ADMIN = {"X-Admin-Token": "test-admin-token"}


def test_switch_defaults_and_snapshot(client: TestClient, settings: Settings) -> None:
    """开关独立按项目保存，配置摘要变化，未授权请求不能写入。"""

    store, repository_id = populate(client, settings, 0)
    url = f"/api/repositories/{repository_id}/limits"
    assert client.get(url, headers=ADMIN).json()["newline_filter_enabled"] is False
    before = config_hash(store, settings, repository_id=repository_id)
    assert client.put(url, json={"newline_filter_enabled": True}).status_code == 401
    response = client.put(url, headers=ADMIN, json={"newline_filter_enabled": True})
    assert response.status_code == 200 and response.json()["newline_filter_enabled"] is True
    assert config_hash(store, settings, repository_id=repository_id) != before
    snapshot = configuration_snapshot(store, settings, repository_id=repository_id)
    assert snapshot["input_policy"]["filter_enabled"] is True
    assert snapshot["input_policy"]["newline_mode"] == "exclude_verified_paths"
    assert review_settings(store, settings, repository_id)[0].ocr_newline_filter_enabled
    assert client.put(url, headers=ADMIN, json={}).json()["newline_filter_enabled"] is False
    assert config_hash(store, settings, repository_id=repository_id) == before


def test_premerge_queue_blocks_changes_and_freezes_switch(
    client: TestClient, settings: Settings,
) -> None:
    """合并前排队与执行时拒绝修改；旧快照不能被当前开关静默升级。"""

    store, repository_id = populate(client, settings, 0)
    url = f"/api/repositories/{repository_id}/limits"
    assert client.put(url, headers=ADMIN, json={"newline_filter_enabled": True}).status_code == 200
    with store.connection() as db:
        db.execute("INSERT INTO premerge_settings(repository_id,enabled) VALUES(?,1)",
                   (repository_id,))
    assert enqueue_premerge(store, repository_id, 7, "a" * 40)
    assert client.put(url, headers=ADMIN, json={}).status_code == 409
    review = next_premerge(store)
    assert review is not None
    policy = json.loads(review["execution_policy"])
    assert policy["input_policy"]["filter_enabled"] is True
    assert client.put(url, headers=ADMIN, json={}).status_code == 409
    # 模拟本机维护绕过接口改变参数，Worker 必须在 GitLab 调用前拒绝旧策略。
    with store.connection() as db:
        db.execute("UPDATE project_review_limits SET newline_filter_enabled=0")
    review_premerge(store, settings, review)
    with store.connection() as db:
        row = db.execute("SELECT status,error FROM premerge_reviews WHERE id=?",
                         (review["id"],)).fetchone()
    assert row["status"] == "failed" and "策略已变化" in row["error"]


def test_schema37_defaults_and_transactional_recovery(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """独立迁移只追加默认关闭；模拟后续 DDL 故障时整版回滚并能再次执行。"""

    store, repository_id = populate(client, settings, 0)
    with store.connection() as db:
        db.execute("INSERT INTO project_review_limits(repository_id,max_files) VALUES(?,200)",
                   (repository_id,))
        db.execute("ALTER TABLE project_review_limits DROP COLUMN newline_filter_enabled")
        remove_improvement_maintenance_schema(db)
        db.execute("DROP TABLE improvement_theme_revisions")
        db.execute("DROP TABLE improvement_theme_links")
        db.execute("DROP TABLE improvement_theme_phases")
        db.execute("DROP TABLE improvement_themes")
        db.execute("DROP TABLE project_improvement_revisions")
        db.execute("DROP TABLE project_improvements")
        db.execute("DROP TABLE worker_execution_slots")
        db.execute("PRAGMA user_version=36")
    migration = storage.NEWLINE_FILTER_MIGRATION
    monkeypatch.setattr(storage, "NEWLINE_FILTER_MIGRATION",
                        migration + "\nINVALID SYNTHETIC SQL;")
    with pytest.raises(sqlite3.OperationalError):
        store.migrate()
    with store.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 36
        assert "newline_filter_enabled" not in {
            row["name"] for row in db.execute("PRAGMA table_info(project_review_limits)")}
    monkeypatch.setattr(storage, "NEWLINE_FILTER_MIGRATION", migration)
    store.migrate()
    with store.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == storage.SCHEMA_VERSION
        row = db.execute("SELECT * FROM project_review_limits WHERE repository_id=?",
                         (repository_id,)).fetchone()
        assert row["newline_filter_enabled"] == 0 and row["max_files"] == 200
    store.migrate()
