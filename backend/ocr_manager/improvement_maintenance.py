"""独立 monitor 的台账维护用例及运维入口；本地文件同步失败时整轮停止自动归档。"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from ocr_manager.config import Settings, load_settings
from ocr_manager.improvement_auto_archive import archive_candidates, candidate_counts
from ocr_manager.improvement_log_sync import sync_project_log
from ocr_manager.improvement_maintenance_contracts import (
    MaintenancePolicy,
    MaintenanceResult,
    MaintenanceStatus,
)
from ocr_manager.storage import Store


def maintenance_status(store: Store, settings: Settings) -> MaintenanceStatus:
    """只读策略、最近执行事实和候选数；来源仅投影是否配置，不返回私有路径。"""

    with store.connection() as db:
        db.execute("BEGIN")
        row = dict(db.execute("SELECT * FROM improvement_maintenance WHERE id=1").fetchone())
        records, themes = candidate_counts(
            db, row["archive_after_days"], datetime.now(UTC).isoformat())
    result = MaintenanceResult.model_validate_json(row.pop("last_result_json"))
    row.pop("id")
    return MaintenanceStatus(**row, last_result=result, source_configured=bool(
        settings.improvement_log_path), candidate_records=records, candidate_themes=themes)


def set_maintenance_policy(store: Store, payload: MaintenancePolicy) -> None:
    """管理员入口仅保存版本化策略；不在 HTTP 内执行文件扫描或归档。"""

    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        changed = db.execute("""UPDATE improvement_maintenance SET enabled=?,archive_after_days=?,
            version=version+1 WHERE id=1 AND version=?""",
            (payload.enabled, payload.archive_after_days, payload.expected_version)).rowcount
        if changed != 1:
            raise ValueError("策略版本已更新，请刷新核对；未覆盖其他管理员的设置")


def run_maintenance(store: Store, settings: Settings) -> MaintenanceResult:
    """每轮幂等同步和归档；失败留稳定错误码，下一轮可重试，不输出异常正文。"""

    result = MaintenanceResult()
    error_code = ""
    try:
        # 1. 本地来源在写事务外读取；冲突虽不阻止其他来源导入，但阻止整轮归档。
        if settings.improvement_log_path:
            result.sync = sync_project_log(store, Path(settings.improvement_log_path))
            if result.sync.conflicts:
                error_code = "source_conflict"
    except (OSError, ValueError, sqlite3.Error):
        error_code = "source_unavailable"
    if not error_code:
        try:
            # 2. 获取短写锁后重新读策略，筛选和历史同事务；失败不留下半次归档。
            with store.connection() as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute("SELECT * FROM improvement_maintenance WHERE id=1").fetchone()
                if row["enabled"]:
                    archived = archive_candidates(db, row["archive_after_days"],
                                                  datetime.now(UTC).isoformat())
                    result.archived_records = archived.archived_records
                    result.archived_themes = archived.archived_themes
        except (ValueError, LookupError, sqlite3.Error):
            error_code = "archive_failed"
            result.archived_records = result.archived_themes = 0
    # 3. 记录真正提交的数量；失败不能刷新成功时间，日志不带来源或私有错误正文。
    with store.connection() as db:
        db.execute("""UPDATE improvement_maintenance SET
            last_checked_at=strftime('%Y-%m-%dT%H:%M:%fZ','now'),
            last_success_at=CASE WHEN ?='' THEN strftime('%Y-%m-%dT%H:%M:%fZ','now')
                ELSE last_success_at END,last_error_code=?,last_result_json=? WHERE id=1""",
            (error_code, error_code, result.model_dump_json()))
    if error_code:
        logging.getLogger(__name__).warning("台账维护未完成：%s", error_code)
    return result


def monitor_maintenance(store: Store, settings: Settings) -> None:
    """隔离维护的未预期失败，不终止监控或阻止既有告警；后续周期继续重试。"""

    try:
        run_maintenance(store, settings)
    except Exception:
        logging.getLogger(__name__).error("台账维护未完成：maintenance_failed")


def main() -> None:
    """运维命令不隐式迁移；预览只读，启用后可显式立即执行一轮并检查运行错误码。"""

    parser = argparse.ArgumentParser(description="台账同步与自动归档维护")
    parser.add_argument("--enable", action="store_true")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()
    if args.preview and (args.enable or args.once):
        parser.error("预览不能同时修改或执行")
    settings = load_settings()
    if not (settings.data_dir / "app.db").is_file():
        raise SystemExit("数据库不存在；请先执行独立的备份与迁移流程")
    store = Store(settings.data_dir / "app.db")
    if args.enable:
        current = maintenance_status(store, settings)
        set_maintenance_policy(store, MaintenancePolicy(enabled=True,
            archive_after_days=args.days, expected_version=current.version))
    if args.once:
        run_maintenance(store, settings)
    status = maintenance_status(store, settings)
    print(json.dumps(status.model_dump(), ensure_ascii=False))
    if args.once and status.last_error_code:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
