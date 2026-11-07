"""第 43 版建立独立补审批次与候选聚合；不修改初审事实、不启用入口或回填旧任务。"""

RECOVERY_MIGRATION = """
CREATE TABLE review_recoveries (
 id INTEGER PRIMARY KEY,
 job_id INTEGER NOT NULL REFERENCES review_jobs(id) ON DELETE CASCADE,
 source_attempt INTEGER NOT NULL CHECK(source_attempt>0),
 source_revision INTEGER NOT NULL CHECK(source_revision>=0),
 client_key TEXT NOT NULL UNIQUE,
 source_digest TEXT NOT NULL,
 source_result_json TEXT NOT NULL,
 config_snapshot TEXT NOT NULL,
 approved_json TEXT NOT NULL,
 token_budget INTEGER NOT NULL CHECK(token_budget>0),
 timeout_seconds INTEGER NOT NULL CHECK(timeout_seconds BETWEEN 1 AND 3600),
 status TEXT NOT NULL DEFAULT 'queued'
   CHECK(status IN ('queued','running','complete','partial','failed','cancelled','stale')),
 execution_token TEXT,
 cancel_requested INTEGER NOT NULL DEFAULT 0 CHECK(cancel_requested IN (0,1)),
 result_json TEXT,
 result_path TEXT,
 error_code TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 started_at TEXT,
 finished_at TEXT
);
CREATE UNIQUE INDEX review_recoveries_active ON review_recoveries(job_id)
 WHERE status IN ('queued','running');
CREATE INDEX review_recoveries_history ON review_recoveries(job_id,id DESC);
CREATE TABLE review_recovery_aggregates (
 job_id INTEGER NOT NULL REFERENCES review_jobs(id) ON DELETE CASCADE,
 source_attempt INTEGER NOT NULL,
 revision INTEGER NOT NULL CHECK(revision>0),
 recovery_id INTEGER NOT NULL UNIQUE REFERENCES review_recoveries(id) ON DELETE CASCADE,
 result_json TEXT NOT NULL,
 origins_json TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(job_id,source_attempt,revision)
);
"""
