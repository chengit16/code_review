"""在服务运行期间使用 SQLite 在线备份 API 保存一致的数据库快照。"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import stat
import tempfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from ocr_manager.secrets import SecretBox
from ocr_manager.storage import SCHEMA_VERSION, Store


def backup_database(source: Path, output_dir: Path) -> Path:
    """备份 WAL 数据库并验证副本；失败时不留下被误认为成功的文件。"""

    if not source.is_file():
        raise FileNotFoundError("SQLite 数据库不存在")
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    name = f"app-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.db"
    descriptor, temporary_name = tempfile.mkstemp(prefix=".app-backup-", dir=output_dir)
    os.close(descriptor)
    temporary = Path(temporary_name)
    destination = output_dir / name
    try:
        with sqlite3.connect(source) as input_db, sqlite3.connect(temporary) as output_db:
            input_db.backup(output_db)
            check = output_db.execute("PRAGMA quick_check").fetchone()
            if check is None or check[0] != "ok":
                raise RuntimeError("SQLite 备份完整性检查失败")
        os.chmod(temporary, 0o600)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def backup_private_config(source: Path, database_snapshot: Path) -> Path:
    """同批保存解密主密钥配置；权限校验失败时绝不留下不完整备份。"""

    metadata = source.stat()
    if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) & 0o077:
        raise RuntimeError("私有配置文件必须由当前用户持有且权限不超过 0600")
    content = source.read_bytes()
    values = json.loads(content)
    if not isinstance(values, dict) or not isinstance(values.get("OCR_APP_MASTER_KEY"), str):
        raise ValueError("私有配置文件缺少加密主密钥")
    destination = database_snapshot.with_suffix(".private.json")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".private-backup-", dir=database_snapshot.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as target:
            target.write(content)
            target.flush()
            os.fsync(target.fileno())
        os.chmod(temporary, 0o600)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def prune_backups(output_dir: Path, retain_days: int = 90) -> int:
    """只清理已配对且通过完整性检查的过期备份，始终保留最近两份。"""

    if not 7 <= retain_days <= 3650:
        raise ValueError("备份保留天数须在 7 至 3650 之间")
    snapshots = sorted(output_dir.glob("app-*.db"), key=lambda item: item.stat().st_mtime,
                       reverse=True)
    cutoff = datetime.now().timestamp() - retain_days * 86400
    removed = 0
    for snapshot in snapshots[2:]:
        private = snapshot.with_suffix(".private.json")
        if not private.is_file() or snapshot.stat().st_mtime >= cutoff:
            continue
        with sqlite3.connect(f"file:{snapshot}?mode=ro", uri=True) as db:
            if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                continue
        snapshot.unlink()
        private.unlink()
        removed += 1
    return removed


def restore_backup(snapshot: Path, destination: Path) -> Path:
    """验证数据库与主密钥配对后恢复到新目录，绝不覆盖运行中的数据。"""

    private = snapshot.with_suffix(".private.json")
    if not snapshot.is_file() or not private.is_file():
        raise FileNotFoundError("数据库与私有配置必须成对存在")
    if destination.exists():
        raise FileExistsError("恢复目标必须是不存在的新目录")
    with sqlite3.connect(f"file:{snapshot}?mode=ro", uri=True) as db:
        integrity = str(db.execute("PRAGMA quick_check").fetchone()[0])
        if integrity != "ok":
            raise RuntimeError("备份数据库完整性检查失败")
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise RuntimeError("备份数据库版本高于当前程序")
    metadata = private.stat()
    if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) & 0o077:
        raise RuntimeError("私有配置备份权限必须不超过 0600")
    values = json.loads(private.read_text(encoding="utf-8"))
    if not isinstance(values, dict) or not isinstance(values.get("OCR_APP_MASTER_KEY"), str):
        raise ValueError("私有配置备份缺少加密主密钥")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".ocr-restore-", dir=destination.parent))
    try:
        shutil.copyfile(snapshot, stage / "app.db")
        shutil.copyfile(private, stage / "private.json")
        manifest = {
            "backup_id": snapshot.name,
            "database_version": version,
            "integrity_check": integrity,
            "operation": "restore_to_new_directory",
            "operation_at": datetime.now(UTC).isoformat(),
        }
        manifest_path = stage / "restore-manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        )
        for file in stage.iterdir():
            os.chmod(file, 0o600)
        stage.replace(destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return destination


def recovery_drill(snapshot: Path, output_dir: Path) -> Path:
    """在隔离副本上执行恢复与凭据解密校验，并保存脱敏演练记录。"""

    started = time.monotonic()
    operation_at = datetime.now(UTC).isoformat()
    checks = {
        "integrity": "not_run", "schema_migration": "not_run",
        "encrypted_credentials": "not_run",
    }
    active_check = "integrity"
    database_version: int | None = None
    restored_version: int | None = None
    outcome = "failed"
    try:
        with sqlite3.connect(f"file:{snapshot}?mode=ro", uri=True) as source_db:
            database_version = int(source_db.execute("PRAGMA user_version").fetchone()[0])
            checks["integrity"] = (
                "passed" if source_db.execute("PRAGMA quick_check").fetchone()[0] == "ok"
                else "failed"
            )
        if checks["integrity"] != "passed":
            raise RuntimeError("integrity")
        active_check = "encrypted_credentials"
        private_snapshot = snapshot.with_suffix(".private.json")
        metadata = private_snapshot.stat()
        if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) & 0o077:
            raise RuntimeError("私有配置备份权限必须不超过 0600")
        private = json.loads(private_snapshot.read_text(encoding="utf-8"))
        if not isinstance(private, dict) or not isinstance(private.get("OCR_APP_MASTER_KEY"), str):
            raise RuntimeError("私有配置备份缺少加密主密钥")
        box = SecretBox(private["OCR_APP_MASTER_KEY"])
        if database_version is not None and database_version > SCHEMA_VERSION:
            active_check = "schema_migration"
            raise RuntimeError("备份数据库版本高于当前程序")
        output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(output_dir, 0o700)
        active_check = "schema_migration"
        with tempfile.TemporaryDirectory(prefix=".recovery-drill-", dir=output_dir) as temporary:
            restored = restore_backup(snapshot, Path(temporary) / "restored")
            store = Store(restored / "app.db")
            store.migrate()
            with store.connection() as db:
                restored_version = int(db.execute("PRAGMA user_version").fetchone()[0])
            checks["schema_migration"] = (
                "passed" if restored_version == SCHEMA_VERSION else "failed"
            )
            if checks["schema_migration"] != "passed":
                raise RuntimeError("schema_migration")
            active_check = "encrypted_credentials"
            _validate_encrypted_credentials(store, box)
            checks["encrypted_credentials"] = "passed"
            outcome = "passed"
    except Exception:
        checks[active_check] = "failed"

    record = {
        "backup_id": snapshot.name,
        "database_version": database_version,
        "restored_database_version": restored_version,
        "checks": checks,
        "outcome": outcome,
        "isolated_copy_only": True,
        "operation_at": operation_at,
        "duration_seconds": round(time.monotonic() - started, 3),
    }
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(output_dir, 0o700)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    name = f"recovery-drill-{timestamp}-{uuid.uuid4().hex[:8]}.json"
    descriptor, temporary_name = tempfile.mkstemp(prefix=".recovery-drill-", dir=output_dir)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as target:
            json.dump(record, target, ensure_ascii=False, indent=2)
            target.write("\n")
            target.flush()
            os.fsync(target.fileno())
        os.chmod(temporary_name, 0o600)
        Path(temporary_name).replace(output_dir / name)
    finally:
        Path(temporary_name).unlink(missing_ok=True)
    if outcome != "passed":
        raise RuntimeError(f"恢复演练未通过；脱敏记录已保存：{output_dir / name}")
    return output_dir / name


def _validate_encrypted_credentials(store: Store, box: SecretBox) -> None:
    """在恢复副本上解密已保存凭据，绝不返回或记录明文。"""

    protected = {
        "repositories": ("webhook_secret", "feishu_webhook", "gitlab_token_ciphertext"),
        "model_profile": ("api_key_ciphertext",),
        "model_profiles": ("api_key_ciphertext",),
        "notification_targets": ("webhook_ciphertext", "signing_secret_ciphertext"),
    }
    with store.connection() as db:
        tables = {row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'",
        )}
        for table, columns in protected.items():
            if table not in tables:
                continue
            available = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
            selected = [column for column in columns if column in available]
            if not selected:
                continue
            query = f"SELECT {', '.join(selected)} FROM {table}"
            for row in db.execute(query):
                for value in row:
                    if value:
                        box.decrypt(str(value))


def main() -> None:
    """从部署脚本或计划任务调用，不依赖管理服务是否正在运行。"""

    parser = argparse.ArgumentParser(description="备份 Open Code Review 的 SQLite 数据库")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--config-file", type=Path)
    parser.add_argument("--retain-days", type=int, default=90)
    parser.add_argument("--restore-from", type=Path)
    parser.add_argument("--restore-to", type=Path)
    parser.add_argument("--drill-from", type=Path)
    args = parser.parse_args()
    if args.drill_from:
        if args.restore_from or args.restore_to or args.data_dir:
            parser.error("恢复演练不能与恢复或备份参数同时使用")
        if args.output_dir is None:
            parser.error("恢复演练必须指定 --output-dir 保存脱敏记录")
        print(recovery_drill(args.drill_from, args.output_dir))
        return
    if args.restore_from or args.restore_to:
        if not args.restore_from or not args.restore_to:
            parser.error("恢复时必须同时指定 --restore-from 与 --restore-to")
        print(restore_backup(args.restore_from, args.restore_to))
        return
    if args.data_dir is None or args.output_dir is None:
        parser.error("备份时必须指定 --data-dir 与 --output-dir")
    if args.config_file:
        # 先验证私有配置，再启动数据库备份，避免计划任务写出无用的孤立快照。
        config = args.config_file
        metadata = config.stat()
        if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) & 0o077:
            raise RuntimeError("私有配置文件必须由当前用户持有且权限不超过 0600")
    destination = backup_database(args.data_dir / "app.db", args.output_dir)
    if args.config_file:
        try:
            backup_private_config(args.config_file, destination)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
    if args.config_file:
        prune_backups(args.output_dir, args.retain_days)
    print(destination)


if __name__ == "__main__":
    main()
