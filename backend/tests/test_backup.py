"""验证在线备份包含已提交数据，并且缺失源数据库不会产生伪快照。"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from ocr_manager.backup import (
    backup_database,
    backup_private_config,
    main,
    prune_backups,
    recovery_drill,
    restore_backup,
)
from ocr_manager.secrets import SecretBox
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


def test_backup_pairs_database_with_private_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """每日快照包含同一批主密钥配置，两个文件权限均限制为当前用户。"""

    data = tmp_path / "data"
    Store(data / "app.db").migrate()
    config = tmp_path / "private.json"
    config.write_text('{"OCR_APP_MASTER_KEY":"synthetic-key"}', encoding="utf-8")
    os.chmod(config, 0o600)
    output_dir = tmp_path / "backups"
    monkeypatch.setattr("sys.argv", [
        "backup", "--data-dir", str(data), "--output-dir", str(output_dir),
        "--config-file", str(config),
    ])
    main()
    snapshot = Path(capsys.readouterr().out.strip())
    private_snapshot = snapshot.with_suffix(".private.json")
    assert snapshot.is_file()
    assert private_snapshot.read_text(encoding="utf-8") == config.read_text(encoding="utf-8")
    assert private_snapshot.stat().st_mode & 0o777 == 0o600
    assert output_dir.stat().st_mode & 0o777 == 0o700


def test_backup_rejects_insecure_private_config_before_database_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """主密钥文件权限错误时不能产出看似可恢复的数据库副本。"""

    data = tmp_path / "data"
    Store(data / "app.db").migrate()
    config = tmp_path / "private.json"
    config.write_text('{"OCR_APP_MASTER_KEY":"synthetic-key"}', encoding="utf-8")
    os.chmod(config, 0o644)
    output_dir = tmp_path / "backups"
    monkeypatch.setattr("sys.argv", [
        "backup", "--data-dir", str(data), "--output-dir", str(output_dir),
        "--config-file", str(config),
    ])
    with pytest.raises(RuntimeError, match="0600"):
        main()
    assert not output_dir.exists()


def test_restore_to_new_directory_and_retention(tmp_path: Path) -> None:
    """配对恢复可再次迁移，历史副本保留最近两份且不覆盖现有目录。"""

    source = tmp_path / "app.db"
    Store(source).migrate()
    backups = tmp_path / "backups"
    snapshots = []
    for _ in range(3):
        snapshot = backup_database(source, backups)
        private = snapshot.with_suffix(".private.json")
        private.write_text('{"OCR_APP_MASTER_KEY":"synthetic-key"}', encoding="utf-8")
        os.chmod(private, 0o600)
        snapshots.append(snapshot)
    restored = restore_backup(snapshots[-1], tmp_path / "restored")
    assert restored.joinpath("app.db").is_file()
    assert restored.joinpath("private.json").stat().st_mode & 0o777 == 0o600
    manifest = json.loads(restored.joinpath("restore-manifest.json").read_text(encoding="utf-8"))
    assert manifest["backup_id"] == snapshots[-1].name
    assert manifest["database_version"] == SCHEMA_VERSION
    assert manifest["integrity_check"] == "ok"
    assert manifest["operation"] == "restore_to_new_directory"
    assert manifest["operation_at"].endswith("+00:00")
    assert restored.joinpath("restore-manifest.json").stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        restore_backup(snapshots[-1], restored)
    old = 100 * 86400
    os.utime(snapshots[0], (old, old))
    os.utime(snapshots[0].with_suffix(".private.json"), (old, old))
    assert prune_backups(backups, 7) == 1
    assert not snapshots[0].exists()


def test_recovery_drill_validates_isolated_restore_and_credentials(tmp_path: Path) -> None:
    """演练在临时隔离副本校验迁移与密文，记录只包含结果元数据。"""

    data = tmp_path / "data"
    store = Store(data / "app.db")
    store.migrate()
    key = Fernet.generate_key().decode("ascii")
    box = SecretBox(key)
    with store.connection() as db:
        db.execute(
            """INSERT INTO repositories
            (name, gitlab_url, project_id, remote_url, target_branch, auth_kind,
             webhook_secret, feishu_webhook) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("合成项目", "https://gitlab.example.test", 61,
             "https://gitlab.example.test/team/repo.git", "main", "secret",
             box.encrypt("synthetic-webhook-secret"), ""),
        )
    private = tmp_path / "private.json"
    private.write_text(json.dumps({"OCR_APP_MASTER_KEY": key}), encoding="utf-8")
    os.chmod(private, 0o600)
    backups = tmp_path / "backups"
    snapshot = backup_database(data / "app.db", backups)
    backup_private_config(private, snapshot)

    record_path = recovery_drill(snapshot, tmp_path / "drill-records")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["backup_id"] == snapshot.name
    assert record["database_version"] == SCHEMA_VERSION
    assert record["restored_database_version"] == SCHEMA_VERSION
    assert record["checks"] == {
        "integrity": "passed", "schema_migration": "passed",
        "encrypted_credentials": "passed",
    }
    assert record["isolated_copy_only"] is True
    assert record_path.stat().st_mode & 0o777 == 0o600
    assert "synthetic-webhook-secret" not in record_path.read_text(encoding="utf-8")
