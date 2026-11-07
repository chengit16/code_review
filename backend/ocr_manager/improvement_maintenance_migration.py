"""第 42 版保存归档策略、后台运行事实和台账来源游标，不自动启用或导入。"""

IMPROVEMENT_MAINTENANCE_MIGRATION = """
CREATE TABLE improvement_maintenance (
 id INTEGER PRIMARY KEY CHECK(id=1),
 enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0,1)),
 archive_after_days INTEGER NOT NULL DEFAULT 30 CHECK(archive_after_days BETWEEN 1 AND 3650),
 version INTEGER NOT NULL DEFAULT 1,
 last_checked_at TEXT,
 last_success_at TEXT,
 last_error_code TEXT NOT NULL DEFAULT '',
 last_result_json TEXT NOT NULL DEFAULT '{}'
);
INSERT INTO improvement_maintenance(id) VALUES(1);
CREATE TABLE improvement_log_imports (
 source_id TEXT PRIMARY KEY,
 improvement_id INTEGER NOT NULL UNIQUE REFERENCES project_improvements(id),
 applied_version INTEGER NOT NULL,
 entry_digests_json TEXT NOT NULL,
 imported_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
"""
