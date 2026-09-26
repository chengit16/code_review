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

FEEDBACK_MIGRATION = """
CREATE TABLE review_feedback (
  job_id INTEGER NOT NULL REFERENCES review_jobs(id),
  comment_index INTEGER NOT NULL CHECK(comment_index>=0),
  verdict TEXT NOT NULL CHECK(verdict IN ('helpful','false_positive','fixed')),
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(job_id,comment_index)
);
CREATE TABLE project_policies (
  repository_id INTEGER PRIMARY KEY REFERENCES repositories(id),
  minimum_severity TEXT NOT NULL DEFAULT 'medium'
    CHECK(minimum_severity IN ('critical','high','medium','low')),
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE review_jobs ADD COLUMN notification_min_severity TEXT NOT NULL DEFAULT 'medium';
"""
