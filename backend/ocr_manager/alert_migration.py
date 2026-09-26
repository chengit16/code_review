"""告警状态与投递迁移；业务评审通知和运维告警各自重试。"""

ALERT_MIGRATION = """
CREATE TABLE alert_config (
 id INTEGER PRIMARY KEY CHECK(id=1), enabled INTEGER NOT NULL DEFAULT 0,
 target_id INTEGER REFERENCES notification_targets(id) ON DELETE SET NULL,
 queue_minutes INTEGER NOT NULL DEFAULT 30
);
INSERT INTO alert_config(id) VALUES(1);
CREATE TABLE alert_states (
 key TEXT PRIMARY KEY, active INTEGER NOT NULL, episode INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE alert_deliveries (
 id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT NOT NULL, episode INTEGER NOT NULL,
 recovered INTEGER NOT NULL, message TEXT NOT NULL,
 target_id INTEGER REFERENCES notification_targets(id) ON DELETE SET NULL,
 status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
 error TEXT, next_run_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, sent_at TEXT,
 UNIQUE(key,episode,recovered)
);
"""
