"""保留全局任务 ID 与待清理目录，防止删除项目后路径被新任务复用。"""

MAINTENANCE_MIGRATION = """
CREATE TABLE job_identity (id INTEGER PRIMARY KEY AUTOINCREMENT);
INSERT INTO job_identity(id) SELECT MAX(id) FROM review_jobs HAVING COUNT(*) > 0;
CREATE TABLE orphan_artifacts (
 job_id INTEGER PRIMARY KEY, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""
