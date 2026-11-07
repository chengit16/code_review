"""新增范围与逐次调度事实；旧值保持未知，不反推历史退避或阶段耗时。"""

OBSERVABILITY_MIGRATION = """
ALTER TABLE review_jobs ADD COLUMN scope_json TEXT;
ALTER TABLE review_jobs ADD COLUMN reason_code TEXT;
ALTER TABLE review_jobs ADD COLUMN attempt_ready_at TEXT;
ALTER TABLE premerge_reviews ADD COLUMN scope_json TEXT;
ALTER TABLE review_attempts ADD COLUMN scope_json TEXT;
ALTER TABLE review_attempts ADD COLUMN reason_code TEXT;
ALTER TABLE review_attempts ADD COLUMN scheduled_at TEXT;
ALTER TABLE review_attempts ADD COLUMN retry_ready_at TEXT;
CREATE TABLE review_stage_timings (
 id INTEGER PRIMARY KEY,
 job_id INTEGER NOT NULL REFERENCES review_jobs(id) ON DELETE CASCADE,
 attempt_number INTEGER NOT NULL,
 stage TEXT NOT NULL,
 started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 finished_at TEXT
);
CREATE INDEX idx_review_stage_attempt ON review_stage_timings(job_id,attempt_number);
CREATE TRIGGER review_attempt_evidence AFTER INSERT ON review_attempts BEGIN
 UPDATE review_attempts SET
 scope_json=(SELECT scope_json FROM review_jobs WHERE id=NEW.job_id),
 reason_code=(SELECT reason_code FROM review_jobs WHERE id=NEW.job_id),
 scheduled_at=(SELECT attempt_ready_at FROM review_jobs WHERE id=NEW.job_id),
 retry_ready_at=(SELECT CASE WHEN status='queued' THEN next_run_at ELSE NULL END
   FROM review_jobs WHERE id=NEW.job_id)
 WHERE id=NEW.id;
END;
CREATE TRIGGER review_stage_finished AFTER UPDATE OF status ON review_jobs
WHEN NEW.status!='running' BEGIN
 UPDATE review_stage_timings SET finished_at=CURRENT_TIMESTAMP
 WHERE job_id=NEW.id AND finished_at IS NULL;
END;
"""
