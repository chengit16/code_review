"""汇总队列、备份与磁盘状态；清理范围只限终态任务的受控运行目录。"""

from __future__ import annotations

import shutil
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from ocr_manager.artifact_lock import artifact_lock
from ocr_manager.storage import Store


def operations_snapshot(store: Store, data_dir: Path, backup_dir: Path) -> dict[str, Any]:
    """由 SQLite 事实计算指标，备份只检查最近副本的完整性。"""

    with store.connection() as db:
        queue = [dict(row) for row in db.execute(
            """SELECT status, COUNT(*) AS count FROM review_jobs GROUP BY status"""
        )]
        oldest = db.execute(
            """SELECT MIN(created_at) FROM review_jobs WHERE status IN ('queued','running')"""
        ).fetchone()[0]
        durations = db.execute(
            """SELECT COUNT(*) AS count, AVG(
              (julianday(finished_at)-julianday(started_at))*86400
            ) AS average_seconds FROM review_jobs
            WHERE started_at IS NOT NULL AND finished_at IS NOT NULL
            AND created_at>=datetime('now','-7 days')"""
        ).fetchone()
        retries = db.execute(
            "SELECT COALESCE(SUM(MAX(attempts-1,0)),0) FROM review_jobs"
        ).fetchone()[0]
        delivery = [dict(row) for row in db.execute(
            "SELECT status, COUNT(*) AS count FROM notification_deliveries GROUP BY status"
        )]
        events = [dict(row) for row in db.execute(
            "SELECT status, COUNT(*) AS count FROM merge_events GROUP BY status"
        )]
    disk = shutil.disk_usage(data_dir)
    snapshots = sorted(backup_dir.glob("app-*.db"), key=lambda path: path.stat().st_mtime,
                       reverse=True) if backup_dir.is_dir() else []
    latest = snapshots[0] if snapshots else None
    backup_ok = False
    if latest:
        try:
            with sqlite3.connect(f"file:{latest}?mode=ro", uri=True) as db:
                backup_ok = db.execute("PRAGMA quick_check").fetchone()[0] == "ok"
            backup_ok = backup_ok and latest.with_suffix(".private.json").is_file()
        except (OSError, sqlite3.Error):
            backup_ok = False
    age = int((datetime.now(UTC) - datetime.fromtimestamp(latest.stat().st_mtime, UTC))
              .total_seconds()) if latest else None
    queue_map = {row["status"]: row["count"] for row in queue}
    delivery_map = {row["status"]: row["count"] for row in delivery}
    alerts = []
    if queue_map.get("failed", 0) or queue_map.get("partial", 0):
        alerts.append("存在失败或部分完成的评审")
    if delivery_map.get("failed", 0):
        alerts.append("存在飞书投递失败")
    if not backup_ok or age is None or age > 48 * 3600:
        alerts.append("最近备份缺失、损坏或超过 48 小时")
    if disk.free < 2 * 1024**3:
        alerts.append("可用磁盘空间少于 2 GB")
    if oldest:
        try:
            queued_at = datetime.strptime(oldest, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
            if datetime.now(UTC) - queued_at > timedelta(minutes=30):
                alerts.append("最早任务已等待超过 30 分钟")
        except ValueError:
            alerts.append("队列时间格式无效")
    return {"jobs": queue_map, "events": {r["status"]: r["count"] for r in events},
            "deliveries": delivery_map, "retry_count": retries,
            "average_review_seconds": round(durations["average_seconds"] or 0),
            "review_count_7d": durations["count"], "oldest_pending_at": oldest,
            "disk_free_bytes": disk.free, "backup": {
                "last_at": datetime.fromtimestamp(latest.stat().st_mtime, UTC).isoformat()
                if latest else None, "healthy": backup_ok, "age_seconds": age,
            }, "alerts": alerts}


def eligible_artifacts(
    store: Store, data_dir: Path, days: int, job_id: int | None = None,
) -> list[tuple[int, Path, int]]:
    """只匹配终态任务 ID 对应的非符号链接目录；保留所有 SQLite 结论。"""

    cutoff = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    with store.connection() as db:
        rows = db.execute(
            """SELECT j.id FROM review_jobs j WHERE j.finished_at<?
            AND j.status IN ('complete','partial','failed','skipped')
            AND (? IS NULL OR j.id=?)
            AND NOT EXISTS (SELECT 1 FROM notification_deliveries d
              WHERE d.job_id=j.id AND d.status IN ('pending','sending'))""",
            (cutoff, job_id, job_id),
        ).fetchall()
    root = data_dir / "runs"
    result = []
    for row in rows:
        path = root / str(row["id"])
        if not path.is_dir() or path.is_symlink():
            continue
        # 工件可能含模型诊断和源代码；目录大小只用于操作预览。
        size = sum(file.stat().st_size for file in path.rglob("*") if file.is_file()
                   and not file.is_symlink())
        result.append((row["id"], path, size))
    return result


def prune_artifacts(store: Store, data_dir: Path, days: int) -> dict[str, int]:
    """删除已确认的旧工件目录，任务与报告安全投影继续保留。"""

    removed = []
    for job_id, _path, _size in eligible_artifacts(store, data_dir, days):
        with artifact_lock(data_dir, job_id) as acquired:
            if not acquired:
                continue
            # 预览与删除间任务可能被重审或通知重发，锁内重新校验当前事实。
            candidates = eligible_artifacts(store, data_dir, days, job_id)
            if not candidates:
                continue
            _candidate_id, path, size = candidates[0]
            shutil.rmtree(path)
            with store.connection() as db:
                db.execute("UPDATE review_jobs SET result_path=NULL WHERE id=?", (job_id,))
            removed.append(size)
    return {"count": len(removed), "bytes": sum(removed)}
