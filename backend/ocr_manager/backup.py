"""在服务运行期间使用 SQLite 在线备份 API 保存一致的数据库快照。"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import stat
import tempfile
from datetime import datetime
from pathlib import Path

from ocr_manager.storage import SCHEMA_VERSION


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
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
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
        for file in stage.iterdir():
            os.chmod(file, 0o600)
        stage.replace(destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return destination


def main() -> None:
    """从部署脚本或计划任务调用，不依赖管理服务是否正在运行。"""

    parser = argparse.ArgumentParser(description="备份 Open Code Review 的 SQLite 数据库")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--config-file", type=Path)
    parser.add_argument("--retain-days", type=int, default=90)
    parser.add_argument("--restore-from", type=Path)
    parser.add_argument("--restore-to", type=Path)
    args = parser.parse_args()
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
