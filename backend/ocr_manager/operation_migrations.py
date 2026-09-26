"""保存运维能力的增量迁移；已有业务迁移保持不变。"""

TASK_MIGRATION = """
ALTER TABLE review_jobs ADD COLUMN target_branch TEXT NOT NULL DEFAULT '';
UPDATE review_jobs SET target_branch=COALESCE(
  (SELECT target_branch FROM repositories WHERE id=repository_id), '');
ALTER TABLE review_jobs ADD COLUMN failure_stage TEXT;
ALTER TABLE review_jobs ADD COLUMN started_at TEXT;
ALTER TABLE review_jobs ADD COLUMN changed_files TEXT;
ALTER TABLE review_attempts ADD COLUMN failure_stage TEXT;
CREATE INDEX idx_jobs_search ON review_jobs(repository_id, status, id DESC);
CREATE INDEX idx_jobs_time ON review_jobs(created_at, id DESC);
"""

READINESS_MIGRATION = """
ALTER TABLE connection_checks ADD COLUMN config_revision_id INTEGER;
"""
