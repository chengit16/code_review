"""在服务运行期间使用 SQLite 在线备份 API 保存一致的数据库快照。"""

from __future__ import annotations

import argparse
import os
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path


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


def main() -> None:
    """从部署脚本或计划任务调用，不依赖管理服务是否正在运行。"""

    parser = argparse.ArgumentParser(description="备份 Open Code Review 的 SQLite 数据库")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    destination = backup_database(args.data_dir / "app.db", args.output_dir)
    print(destination)


if __name__ == "__main__":
    main()
