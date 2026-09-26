"""验证在线备份包含已提交数据，并且缺失源数据库不会产生伪快照。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from ocr_manager.backup import backup_database
from ocr_manager.storage import SCHEMA_VERSION, Store


def test_backup_copies_committed_wal_data(tmp_path: Path) -> None:
    """服务使用 WAL 时在线备份仍保留最新事件和 schema 版本。"""

    source = tmp_path / "data" / "app.db"
    store = Store(source)
    store.migrate()
    with store.connection() as db:
        db.execute(
            """INSERT INTO repositories
            (name, gitlab_url, project_id, remote_url, target_branch, auth_kind,
             webhook_secret, feishu_webhook)
            VALUES ('示例', 'https://gitlab.example.test', 42,
                    'git@gitlab.example.test:team/repo.git', 'main', 'secret',
                    'cipher', 'cipher')"""
        )
    destination = backup_database(source, tmp_path / "backups")
    assert destination.is_file()
    assert destination.stat().st_mode & 0o777 == 0o600
    with sqlite3.connect(destination) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert db.execute("SELECT name FROM repositories").fetchone()[0] == "示例"


def test_backup_rejects_missing_source(tmp_path: Path) -> None:
    """源数据库缺失时不能悄悄创建空数据库作为备份。"""

    with pytest.raises(FileNotFoundError):
        backup_database(tmp_path / "missing.db", tmp_path / "backups")
    assert not (tmp_path / "backups").exists()
