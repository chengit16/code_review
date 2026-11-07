"""交付前只读核验指定事项的来源与页面；不抓取聊天、不迁移、不代写或覆盖事实。"""

from __future__ import annotations

import argparse
import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from ocr_manager.improvement_log_parser import entry_content, read_log

_STATES = ("kind", "category", "status", "code_state", "verification_state", "deployment_state")


def check_log(database: Path, source: Path, source_ids: list[str], minimum_entries: int = 1,
              *, now: datetime | None = None) -> list[dict[str, object]]:
    """返回指定编号的脱敏检查结果；条数下限防止把受理记录误当成已追加收尾进展。"""

    if not source_ids or minimum_entries < 1:
        raise ValueError("必须指定本次编号，条数下限须为正数")
    groups = read_log(source)
    results: list[dict[str, object]] = []
    # 1. 只读事务取得一致的页面与游标；显式关闭连接，不创建缺失数据库。
    with closing(sqlite3.connect(database.resolve(strict=True).as_uri() + "?mode=ro",
                                uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute("BEGIN")
        maintenance = db.execute("SELECT * FROM improvement_maintenance WHERE id=1").fetchone()
        monitor_ok = False
        if maintenance is not None and not maintenance["last_error_code"]:
            checked = maintenance["last_checked_at"]
            if checked:
                last_check = datetime.fromisoformat(checked.replace("Z", "+00:00"))
                if last_check.tzinfo is None:
                    last_check = last_check.replace(tzinfo=UTC)
                age = ((now or datetime.now(UTC)) - last_check).total_seconds()
                monitor_ok = 0 <= age <= 120
        # 2. 对照来源完整摘要、导入版本及页面状态；人工修改或历史变动必须人工核对。
        for source_id in dict.fromkeys(source_ids):
            entries = groups.get(source_id, [])
            errors: list[str] = []
            result: dict[str, object] = {"source_id": source_id, "entries": len(entries)}
            if len(entries) < minimum_entries:
                errors.append("source_missing_or_progress_incomplete")
            imported = db.execute("SELECT * FROM improvement_log_imports WHERE source_id=?",
                                  (source_id,)).fetchone()
            if imported is None:
                errors.append("not_imported")
            else:
                known = json.loads(imported["entry_digests_json"])
                digests = [entry.digest for entry in entries]
                if known != digests:
                    errors.append("sync_pending" if digests[:len(known)] == known
                                  else "source_history_conflict")
                page = db.execute("SELECT * FROM project_improvements WHERE id=?",
                                  (imported["improvement_id"],)).fetchone()
                if page is None:
                    errors.append("page_missing")
                else:
                    result.update(page_id=page["id"], page_version=page["version"])
                    if page["version"] != imported["applied_version"] or page["archived_at"]:
                        errors.append("page_changed_or_archived")
                    content = None
                    for entry in entries:
                        content = entry_content(entry, content)
                    if content and any(page[key] != getattr(content, key) for key in _STATES):
                        errors.append("state_mismatch")
            if not monitor_ok:
                errors.append("monitor_not_recent_or_error")
            result.update(passed=not errors, errors=errors)
            results.append(result)
    return results


def main() -> None:
    """显式指定业务数据库与事项；不打印正文、私有配置或异常外部响应。"""

    parser = argparse.ArgumentParser(description="只读核验本次问题台账交付，不自动补写事实")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=Path("docs/problem-improvement-log.md"))
    parser.add_argument("--source-id", action="append", required=True)
    parser.add_argument("--minimum-entries", type=int, default=1)
    args = parser.parse_args()
    try:
        results = check_log(args.database, args.source, args.source_id, args.minimum_entries)
    except (OSError, ValueError, TypeError, sqlite3.Error):
        print(json.dumps({"passed": False, "error": "check_unavailable"}))
        raise SystemExit(1) from None
    passed = all(item["passed"] for item in results)
    print(json.dumps({"passed": passed, "results": results}, ensure_ascii=False))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
