"""GitLab 行内发布与飞书投递独立建模，默认关闭外部写回。"""

PUBLICATION_MIGRATION = """
CREATE TABLE gitlab_publication_settings (
 repository_id INTEGER PRIMARY KEY REFERENCES repositories(id) ON DELETE CASCADE,
 enabled INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE gitlab_publications (
 id INTEGER PRIMARY KEY, job_id INTEGER NOT NULL REFERENCES review_jobs(id) ON DELETE CASCADE,
 attempt_number INTEGER NOT NULL, comment_index INTEGER NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending',
 attempts INTEGER NOT NULL DEFAULT 0, next_run_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 error TEXT, discussion_id TEXT, sent_at TEXT,
 UNIQUE(job_id,attempt_number,comment_index)
);
CREATE INDEX idx_publications_ready ON gitlab_publications(status,next_run_at,id);
"""
