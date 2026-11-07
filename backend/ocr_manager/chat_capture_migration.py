"""第 47 版保存显式会话授权、脱敏摄取与可逆关联；不自动绑定或读取任何会话。"""

CHAT_CAPTURE_MIGRATION = """
CREATE TABLE chat_source_bindings (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 thread_id TEXT NOT NULL UNIQUE,
 project_root TEXT NOT NULL,
 since_ms INTEGER NOT NULL CHECK(since_ms>=0),
 enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)),
 version INTEGER NOT NULL DEFAULT 1,
 last_checked_at TEXT,
 last_success_at TEXT,
 last_error_code TEXT NOT NULL DEFAULT '',
 last_message_ms INTEGER,
 last_scan_count INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE chat_capture_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 binding_id INTEGER NOT NULL REFERENCES chat_source_bindings(id),
 turn_id TEXT NOT NULL,
 message_id TEXT NOT NULL,
 fingerprint TEXT NOT NULL,
 role TEXT NOT NULL CHECK(role IN ('user','assistant')),
 classification TEXT NOT NULL CHECK(classification IN ('issue','pending','progress')),
 excerpt TEXT NOT NULL,
 source_ms INTEGER NOT NULL,
 improvement_id INTEGER REFERENCES project_improvements(id),
 version INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 UNIQUE(binding_id,message_id,fingerprint)
);
CREATE INDEX idx_chat_capture_binding ON chat_capture_events(binding_id,id);
CREATE TABLE chat_capture_links (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 event_id INTEGER NOT NULL REFERENCES chat_capture_events(id),
 improvement_id INTEGER REFERENCES project_improvements(id),
 actor TEXT NOT NULL,
 reason TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
"""
