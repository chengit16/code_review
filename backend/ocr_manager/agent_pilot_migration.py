"""第 57 版持久化管理台的单仓试点授权，现有仓库初始无页面授权。"""

AGENT_PILOT_MIGRATION = """
CREATE TABLE IF NOT EXISTS agent_review_pilots (
    repository_id INTEGER PRIMARY KEY REFERENCES repositories(id) ON DELETE CASCADE,
    enabled_by TEXT NOT NULL,
    enabled_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""
