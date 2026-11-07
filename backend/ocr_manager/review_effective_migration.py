"""第 45 版保存已校验的有效结论与独立补充通知；不回填历史候选或开启业务入口。"""

EFFECTIVE_MIGRATION = """
ALTER TABLE review_recoveries ADD COLUMN requested_by TEXT;
CREATE TABLE review_recovery_fairness (
 id INTEGER PRIMARY KEY CHECK(id=1),
 next_kind TEXT NOT NULL CHECK(next_kind IN ('initial','recovery'))
);
INSERT INTO review_recovery_fairness VALUES(1,'recovery');
CREATE TABLE review_effective_conclusions (
 job_id INTEGER PRIMARY KEY REFERENCES review_jobs(id) ON DELETE CASCADE,
 source_attempt INTEGER NOT NULL,
 revision INTEGER NOT NULL,
 recovery_id INTEGER NOT NULL UNIQUE REFERENCES review_recoveries(id) ON DELETE CASCADE,
 document_json TEXT NOT NULL CHECK(json_valid(document_json)),
 highest_severity TEXT,
 FOREIGN KEY(job_id,source_attempt,revision)
  REFERENCES review_recovery_aggregates(job_id,source_attempt,revision) ON DELETE CASCADE
);
CREATE TABLE review_recovery_deliveries (
 id INTEGER PRIMARY KEY,
 job_id INTEGER NOT NULL REFERENCES review_jobs(id) ON DELETE CASCADE,
 source_attempt INTEGER NOT NULL,
 revision INTEGER NOT NULL,
 recovery_id INTEGER NOT NULL UNIQUE REFERENCES review_recoveries(id) ON DELETE CASCADE,
 document_json TEXT NOT NULL CHECK(json_valid(document_json)),
 status TEXT NOT NULL DEFAULT 'pending'
  CHECK(status IN ('pending','sending','sent','failed','superseded')),
 execution_token TEXT,
 attempts INTEGER NOT NULL DEFAULT 0,
 error TEXT,
 next_run_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 sent_at TEXT,
 UNIQUE(job_id,source_attempt,revision)
);
CREATE INDEX review_recovery_delivery_queue ON review_recovery_deliveries(status,next_run_at,id);
CREATE TRIGGER review_effective_job_changed AFTER UPDATE OF
 result_json,config_snapshot,config_hash,commit_sha,base_sha,rule_digest
 ON review_jobs BEGIN
 DELETE FROM review_effective_conclusions WHERE job_id=NEW.id;
END;
CREATE TRIGGER review_effective_attempt_removed AFTER DELETE ON review_attempts BEGIN
 DELETE FROM review_effective_conclusions
 WHERE job_id=OLD.job_id AND source_attempt=OLD.attempt_number;
END;
CREATE TRIGGER review_effective_aggregate_removed AFTER DELETE ON review_recovery_aggregates BEGIN
 DELETE FROM review_effective_conclusions
 WHERE job_id=OLD.job_id AND source_attempt=OLD.source_attempt;
END;
CREATE TRIGGER review_effective_attempt_changed AFTER UPDATE OF
 result_json,status,config_snapshot,attempt_number,job_id
 ON review_attempts BEGIN
 DELETE FROM review_effective_conclusions
 WHERE (job_id=OLD.job_id AND source_attempt=OLD.attempt_number)
 OR (job_id=NEW.job_id AND source_attempt=NEW.attempt_number);
END;
CREATE TRIGGER review_effective_batch_changed AFTER UPDATE OF
 result_json,status,source_attempt,job_id,
 source_result_json,source_digest,approved_json,config_snapshot
 ON review_recoveries BEGIN
 DELETE FROM review_effective_conclusions
 WHERE job_id=OLD.job_id AND source_attempt=OLD.source_attempt AND recovery_id>=OLD.id;
END;
CREATE TRIGGER review_effective_batch_removed AFTER DELETE ON review_recoveries BEGIN
 DELETE FROM review_effective_conclusions
 WHERE job_id=OLD.job_id AND source_attempt=OLD.source_attempt AND recovery_id>=OLD.id;
END;
CREATE TRIGGER review_effective_aggregate_changed AFTER UPDATE ON review_recovery_aggregates BEGIN
 DELETE FROM review_effective_conclusions
 WHERE job_id=OLD.job_id AND source_attempt=OLD.source_attempt;
END;
"""
