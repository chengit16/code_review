"""独立监控服务的持久化告警与投递；只在异常状态变化时产生群消息。"""

from __future__ import annotations

import fcntl
import logging
import os
import time
from datetime import UTC, datetime, timedelta

from cryptography.fernet import InvalidToken

from ocr_manager.config import Settings, load_settings
from ocr_manager.feishu import FeishuDeliveryError, post_message
from ocr_manager.monitoring import operations_snapshot
from ocr_manager.secrets import SecretBox
from ocr_manager.storage import Store


def alert_conditions(store: Store, settings: Settings, queue_minutes: int) -> dict[str, bool]:
    """Worker 锁检查独立于评审循环，因此长评审不会阻止检测进程停止。"""

    from ocr_manager.worker import worker_is_running

    metrics = operations_snapshot(store, settings.data_dir, settings.data_dir.parent / "backups")
    oldest = metrics["oldest_pending_at"]
    delayed = bool(oldest and datetime.now(UTC) - datetime.strptime(
        oldest, "%Y-%m-%d %H:%M:%S"
    ).replace(tzinfo=UTC) > timedelta(minutes=queue_minutes))
    return {"Worker 未运行": not worker_is_running(settings.data_dir),
            "队列等待超时": delayed,
            "存在失败或部分完成的评审": bool(metrics["jobs"].get("failed") or
                                          metrics["jobs"].get("partial")),
            "飞书评审通知失败": bool(metrics["deliveries"].get("failed")),
            "备份缺失、损坏或超过 48 小时": not metrics["backup"]["healthy"] or
             (metrics["backup"]["age_seconds"] or 10**9) > 48 * 3600,
            "可用磁盘空间少于 2 GB": metrics["disk_free_bytes"] < 2 * 1024**3}


def reconcile_alerts(store: Store, conditions: dict[str, bool]) -> None:
    """变化和投递同事务写入；重启、重复检查不重复创建同一轮告警。"""

    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        config = db.execute("SELECT * FROM alert_config WHERE id=1").fetchone()
        if not config["enabled"] or config["target_id"] is None:
            return
        for key, active in conditions.items():
            old = db.execute("SELECT * FROM alert_states WHERE key=?", (key,)).fetchone()
            if old is not None and bool(old["active"]) == active:
                continue
            episode = (int(old["episode"]) if old else 0) + int(active)
            db.execute("""INSERT INTO alert_states(key,active,episode) VALUES(?,?,?)
                       ON CONFLICT(key) DO UPDATE SET active=excluded.active,
                       episode=excluded.episode""", (key, int(active), episode))
            if old is None and not active:
                continue
            db.execute("""INSERT OR IGNORE INTO alert_deliveries
                       (key,episode,recovered,message,target_id) VALUES(?,?,?,?,?)""",
                       (key, episode, int(not active),
                        f"Open Code Review {'恢复' if not active else '告警'}：{key}",
                        config["target_id"]))


def deliver_alert(store: Store, settings: Settings) -> bool:
    """有限退避仅改变告警投递，不触发 OCR；目标丢失时等待人工修复。"""

    with store.connection() as db:
        row = db.execute("""SELECT * FROM alert_deliveries WHERE status='pending'
                         AND next_run_at<=CURRENT_TIMESTAMP ORDER BY id LIMIT 1""").fetchone()
        if row is None:
            return False
        delivery = dict(row)
        db.execute("UPDATE alert_deliveries SET status='sending', attempts=attempts+1 WHERE id=?",
                   (delivery["id"],))
    error_text = None
    retryable = False
    try:
        target = store.get_notification_target(delivery["target_id"])
        if target is None:
            raise ValueError("告警通道已删除")
        box = SecretBox(settings.master_key)
        post_message(box.decrypt(target["webhook_ciphertext"]),
                     {"msg_type": "text", "content": {"text": delivery["message"]}},
                     box.decrypt(target["signing_secret_ciphertext"])
                     if target["signing_secret_ciphertext"] else "")
    except FeishuDeliveryError as error:
        error_text, retryable = str(error), error.retryable
    except (ValueError, InvalidToken):
        error_text = "告警通道不可用"
    with store.connection() as db:
        db.execute("""UPDATE alert_deliveries SET status=?, error=?,
                   sent_at=CASE WHEN ? IS NULL THEN CURRENT_TIMESTAMP ELSE NULL END,
                   next_run_at=datetime('now',printf('+%d seconds',min(300,attempts*attempts*10)))
                   WHERE id=?""", ("sent" if error_text is None else "pending"
                                    if retryable and delivery["attempts"] + 1 < 5 else "failed",
                                    error_text, error_text, delivery["id"]))
    return True


def main() -> None:
    """独立监控进程每 30 秒检查异常，投递恢复遵守至少一次发送语义。"""

    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = load_settings()
    store = Store(settings.data_dir / "app.db")
    store.migrate()
    descriptor = os.open(settings.data_dir / "monitor.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with store.connection() as db:
            db.execute("UPDATE alert_deliveries SET status='pending' WHERE status='sending'")
        while True:
            with store.connection() as db:
                config = dict(db.execute("SELECT * FROM alert_config WHERE id=1").fetchone())
            if config["enabled"]:
                reconcile_alerts(store, alert_conditions(store, settings, config["queue_minutes"]))
                # 限制每轮投递数量，避免大量历史消息饿死状态检测。
                for _ in range(20):
                    if not deliver_alert(store, settings):
                        break
            time.sleep(30)
    finally:
        os.close(descriptor)


if __name__ == "__main__":
    main()
