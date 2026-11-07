"""从受控补审工件补充历史预算数字；默认只预览，不改写旧结果、状态、费用或额度。"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from ocr_manager.ocr import classify_result
from ocr_manager.recovery_budget import budget_gate, save_gate
from ocr_manager.review_recovery_domain import RecoveryConflict, coverage_items, digest
from ocr_manager.review_results import project_review_result
from ocr_manager.storage import SCHEMA_VERSION, Store


def _identity(row: dict[str, Any]) -> str:
    return digest(
        {
            key: row[key]
            for key in (
                "id",
                "job_id",
                "status",
                "result_path",
                "result_json",
                "token_budget",
                "config_snapshot",
            )
        }
    )


def import_budget_evidence(data_dir: Path, *, apply: bool = False) -> dict[str, Any]:
    """限定实例既有终态工件，核验输入、覆盖、用量和字节；提交前再次核对数据库版本事实。"""

    # 1. 只读既有实例，迁移和业务执行必须由独立发布流程负责。
    database = (data_dir / "app.db").resolve(strict=True)
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        if db.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
            raise ValueError("请先备份并迁移数据库，不允许隐式创建或升级")
        rows = [
            dict(row)
            for row in db.execute("""SELECT r.*,j.commit_sha,j.base_sha
            FROM review_recoveries r JOIN review_jobs j ON j.id=r.job_id
            WHERE r.status NOT IN ('queued','running') AND r.result_path IS NOT NULL""")
        ]
    report: dict[str, Any] = {
        "apply": apply,
        "scanned": len(rows),
        "eligible": 0,
        "inserted": 0,
        "unchanged": 0,
        "skipped": [],
    }
    for row in rows:
        try:
            # 2. 原始工件必须与数据库安全投影吻合；未知内容不推断、不透传。
            path = Path(row["result_path"])
            expected = (
                data_dir.resolve()
                / "runs"
                / str(row["job_id"])
                / "recoveries"
                / str(row["id"])
                / "result.json"
            )
            if (
                path.is_symlink()
                or any(parent.is_symlink() for parent in path.parents)
                or path.resolve(strict=True) != expected
                or not path.is_file()
                or path.stat().st_size > 16 * 1024 * 1024
            ):
                raise ValueError("artifact_invalid")
            with path.open("rb") as file:
                content = file.read(16 * 1024 * 1024 + 1)
            if len(content) > 16 * 1024 * 1024:
                raise ValueError("artifact_invalid")
            raw = json.loads(content)
            if not isinstance(raw, dict):
                raise ValueError("artifact_invalid")
            classify_result(raw, row["commit_sha"], row["base_sha"])
            projection = project_review_result(raw)
            coverage_items(projection)
            original = json.loads(row["result_json"])
            if not isinstance(original, dict):
                raise ValueError("result_mismatch")
            if any(
                projection[key] != original.get(key) for key in ("manifest", "comments", "usage")
            ):
                raise ValueError("result_mismatch")
            gate = budget_gate(raw)
            if gate is None or gate.budget_tokens != row["token_budget"]:
                raise ValueError("no_verified_gate")
            report["eligible"] += 1
            if not apply:
                continue
            # 3. 写锁内再次核对来源，仅追加数字证据，绝不修补旧批次或自动授权。
            store = Store(database)
            with store.connection() as db:
                db.execute("BEGIN IMMEDIATE")
                current = db.execute(
                    "SELECT * FROM review_recoveries WHERE id=?", (row["id"],)
                ).fetchone()
                if current is None or _identity(dict(current)) != _identity(row):
                    raise ValueError("source_changed")
                known = db.execute(
                    "SELECT 1 FROM review_recovery_budget_evidence WHERE recovery_id=?",
                    (row["id"],),
                ).fetchone()
                save_gate(db, row["id"], gate, hashlib.sha256(content).hexdigest())
                report["unchanged" if known else "inserted"] += 1
        except (OSError, ValueError, TypeError, KeyError, RecoveryConflict):
            # 工件和外部异常正文不进入摘要；遗漏候选明确留编号供维护者复核。
            report["skipped"].append({"recovery_id": row["id"], "code": "evidence_unverified"})
    return report


def main() -> None:
    """显式实例路径及 --apply 才写入独立诊断表；不提供修改预算或重试入口。"""

    parser = argparse.ArgumentParser(description="受控导入历史补审预算证据（默认只预览）")
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(import_budget_evidence(args.data_dir, apply=args.apply), ensure_ascii=False))


if __name__ == "__main__":
    main()
