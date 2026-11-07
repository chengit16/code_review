"""显式预览或导入全部旧任务的安全诊断；独立运维进程读取工件，不重跑模型或改写初审。"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import sqlite3
import stat
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from ocr_manager.artifact_lock import artifact_lock
from ocr_manager.config import load_settings
from ocr_manager.ocr import classify_result
from ocr_manager.review_diagnostics import failure_analysis
from ocr_manager.review_failures import ReviewFailure
from ocr_manager.review_recovery_domain import coverage_items
from ocr_manager.review_results import project_review_result

MAX_BYTES = 16 * 1024 * 1024


class ImportRejected(ValueError):
    """仅携带固定原因码，避免工件异常正文泄露到运维输出。"""


@contextmanager
def _database(path: Path, *, write: bool = False) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(path.resolve(strict=True).as_uri() +
                                 ("?mode=rw" if write else "?mode=ro"), uri=True, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _candidates(db: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = db.execute("""SELECT j.id AS job_id,a.attempt_number,'attempt' AS source_kind,
        a.status,a.result_path,a.result_json,j.commit_sha,j.base_sha FROM review_attempts a
        JOIN review_jobs j ON j.id=a.job_id WHERE a.status IN ('partial','failed')
        UNION ALL SELECT j.id,j.attempts,'job',j.status,j.result_path,j.result_json,
        j.commit_sha,j.base_sha FROM review_jobs j WHERE j.status IN ('partial','failed')
        AND j.attempts>0 AND NOT EXISTS (SELECT 1 FROM review_attempts a
        WHERE a.job_id=j.id AND a.attempt_number=j.attempts)
        ORDER BY job_id,attempt_number LIMIT 100001""").fetchall()
    if len(rows) > 100000:
        raise ImportRejected("candidate_limit")
    return [dict(row) for row in rows]


def _read_artifact(data_dir: Path, candidate: dict[str, Any]) -> bytes:
    root = data_dir.resolve(strict=True) / "runs" / str(candidate["job_id"])
    path = Path(candidate["result_path"] or "")
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root)
        # macOS 的系统 /var 可链接到 /private/var；仅检查受控任务目录内的链接。
        lexical_root = data_dir.absolute() / "runs" / str(candidate["job_id"])
        if not path.absolute().is_relative_to(lexical_root):
            lexical_root = root
        if (resolved.name != "result.json" or path.is_symlink() or
                any(parent.is_symlink() for parent in path.absolute().parents
                    if parent == lexical_root or lexical_root in parent.parents)):
            raise ImportRejected("artifact_path_invalid")
        descriptor = os.open(resolved, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as source:
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                raise ImportRejected("artifact_path_invalid")
            content = source.read(MAX_BYTES + 1)
        if len(content) > MAX_BYTES:
            raise ImportRejected("artifact_too_large")
        return content
    except FileNotFoundError as error:
        raise ImportRejected("artifact_missing") from error
    except (OSError, ValueError) as error:
        if isinstance(error, ImportRejected):
            raise
        raise ImportRejected("artifact_path_invalid") from error


def _analysis(data_dir: Path, candidate: dict[str, Any]) -> tuple[str, str]:
    try:
        stored = json.loads(candidate["result_json"] or "null")
        if not isinstance(stored, dict):
            raise ImportRejected("source_result_missing")
        if stored.get("failure_analysis") is not None:
            raise ImportRejected("native_diagnostic_present")
        content = _read_artifact(data_dir, candidate)
        raw = json.loads(content)
        if not isinstance(raw, dict):
            raise ImportRejected("artifact_invalid")
        state = classify_result(raw, candidate["commit_sha"], candidate["base_sha"])
        coverage_items(raw)
        projected = project_review_result(raw)
        if (state != candidate["status"] or
                any(projected[key] != stored.get(key) for key in ("manifest", "comments"))):
            raise ImportRejected("source_result_mismatch")
        analysis = failure_analysis(raw)
        if analysis is None:
            raise ImportRejected("diagnostic_unavailable")
        return json.dumps(analysis, ensure_ascii=False), hashlib.sha256(content).hexdigest()
    except (ValueError, TypeError, KeyError, AttributeError, ReviewFailure) as error:
        if isinstance(error, ImportRejected):
            raise
        raise ImportRejected("artifact_invalid") from error


def _source_matches(db: sqlite3.Connection, candidate: dict[str, Any]) -> bool:
    row = db.execute("SELECT * FROM review_jobs WHERE id=?", (candidate["job_id"],)).fetchone()
    if (row is None or row["commit_sha"] != candidate["commit_sha"] or
            row["base_sha"] != candidate["base_sha"]):
        return False
    if candidate["source_kind"] == "attempt":
        row = db.execute("SELECT * FROM review_attempts WHERE job_id=? AND attempt_number=?",
                         (candidate["job_id"], candidate["attempt_number"])).fetchone()
    elif row["attempts"] != candidate["attempt_number"]:
        return False
    return row is not None and all(row[key] == candidate[key] for key in (
        "result_json", "result_path", "status"))


def _save(path: Path, candidate: dict[str, Any], analysis: str,
          artifact_digest: str, actor: str) -> str:
    with _database(path, write=True) as db:
        db.execute("BEGIN IMMEDIATE")
        if not _source_matches(db, candidate):
            raise ImportRejected("source_changed")
        cursor = db.execute("""INSERT OR IGNORE INTO review_historical_diagnostics
            (job_id,attempt_number,source_kind,source_status,head_sha,base_sha,
            source_result_json,artifact_digest,analysis_json,imported_by)
            VALUES(?,?,?,?,?,?,?,?,?,?)""", (candidate["job_id"], candidate["attempt_number"],
            candidate["source_kind"], candidate["status"], candidate["commit_sha"],
            candidate["base_sha"], candidate["result_json"], artifact_digest, analysis, actor))
        if not cursor.rowcount:
            return "already_imported"
        # 独立诊断与审计同事务；不触碰会使有效结论失效的初审结果列。
        db.execute("""INSERT INTO audit_log(action,object_type,object_id,outcome,actor_name)
            VALUES('historical_diagnostic_import','review_job',?,'success',?)""",
            (candidate["job_id"], actor))
    return "imported"


def import_diagnostics(data_dir: Path, *, apply: bool = False) -> dict[str, Any]:
    """默认预览，显式 apply 才落库；逐任务锁与源快照复核保护并发，失败项不覆盖已有结果。"""

    path = data_dir / "app.db"
    # 1. 候选来自同一只读快照；允许预览 45 版，执行前要求已完成 46 版独立迁移。
    with _database(path) as db:
        db.execute("BEGIN")
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version < 45 or apply and version < 46:
            raise ImportRejected("schema_upgrade_required")
        candidates = _candidates(db)
        existing = ({(row[0], row[1]) for row in db.execute(
            "SELECT job_id,attempt_number FROM review_historical_diagnostics")}
            if version >= 46 else set())
    counts: Counter[str] = Counter()
    items: list[dict[str, Any]] = []
    actor = getpass.getuser()[:128]
    for candidate in candidates:
        outcome = "already_imported"
        try:
            if (candidate["job_id"], candidate["attempt_number"]) not in existing:
                # 2. 与工件清理/重审共用锁；解析和输入核验不占 SQLite 写锁。
                with artifact_lock(data_dir, candidate["job_id"]) as acquired:
                    if not acquired:
                        raise ImportRejected("artifacts_busy")
                    analysis, artifact_digest = _analysis(data_dir, candidate)
                    # 3. 预览不落库；执行逐项短事务复核，崩溃重跑由主键保证幂等。
                    outcome = (_save(path, candidate, analysis, artifact_digest, actor)
                               if apply else "ready")
        except ImportRejected as error:
            outcome = str(error)
        counts[outcome] += 1
        items.append({"job_id": candidate["job_id"],
                      "attempt_number": candidate["attempt_number"], "outcome": outcome})
    return {"mode": "apply" if apply else "preview", "counts": dict(counts), "items": items}


def main() -> None:
    """本机显式运维入口，不启动 API、不隐式迁移、不调用模型；只打印固定原因码和任务编号。"""

    parser = argparse.ArgumentParser(description="预览或导入历史失败诊断，不重跑评审")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--preview", action="store_true")
    group.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    settings = load_settings()
    try:
        result = import_diagnostics(settings.data_dir, apply=args.apply)
    except (ImportRejected, sqlite3.Error, OSError):
        parser.exit(1, "历史诊断导入未完成，请核对数据库版本、路径与可用性；未隐式迁移。\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
