"""统一评审主体并保留旧预审身份；迁移只复制历史事实，不执行模型或通知。"""

MIGRATION = """
ALTER TABLE review_jobs ADD COLUMN source TEXT NOT NULL DEFAULT 'mr';
UPDATE review_jobs SET source='push' WHERE mr_iid<0;
ALTER TABLE review_jobs ADD COLUMN legacy_premerge_id INTEGER;
CREATE UNIQUE INDEX idx_jobs_legacy_premerge ON review_jobs(legacy_premerge_id);
ALTER TABLE review_jobs ADD COLUMN context_hint TEXT;
ALTER TABLE review_jobs ADD COLUMN context_json TEXT;
ALTER TABLE review_jobs ADD COLUMN mr_state TEXT;
ALTER TABLE review_jobs ADD COLUMN superseded INTEGER NOT NULL DEFAULT 0;
ALTER TABLE review_jobs ADD COLUMN execution_policy TEXT;
ALTER TABLE review_jobs ADD COLUMN historical_import INTEGER NOT NULL DEFAULT 0;
ALTER TABLE merge_events ADD COLUMN source TEXT NOT NULL DEFAULT 'mr';
ALTER TABLE merge_events ADD COLUMN force_full_review INTEGER NOT NULL DEFAULT 0;
UPDATE merge_events SET source='push' WHERE mr_iid<0;
CREATE TABLE review_event_links (
 event_id INTEGER NOT NULL REFERENCES merge_events(id) ON DELETE CASCADE,
 job_id INTEGER NOT NULL REFERENCES review_jobs(id) ON DELETE CASCADE,
 relation TEXT NOT NULL,
 evidence_json TEXT NOT NULL DEFAULT '{}',
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(event_id,job_id)
);
INSERT INTO review_event_links(event_id,job_id,relation)
 SELECT event_id,id,'created' FROM review_jobs;
CREATE TABLE merged_review_ranges (
 repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
 mr_iid INTEGER NOT NULL,
 head_sha TEXT NOT NULL,
 before_sha TEXT NOT NULL,
 after_sha TEXT NOT NULL,
 job_id INTEGER REFERENCES review_jobs(id) ON DELETE SET NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(repository_id,mr_iid,head_sha,before_sha,after_sha)
);
CREATE INDEX idx_merged_ranges ON merged_review_ranges(repository_id,before_sha,after_sha);
INSERT INTO merge_events(repository_id,mr_iid,delivery_id,status,source,correlation_id,created_at)
 SELECT repository_id,-3000000000000000000-id,'legacy-premerge-'||id,'done','premerge',
 'legacy-premerge-'||id,created_at FROM premerge_reviews;
INSERT INTO job_identity(id)
 SELECT (SELECT COALESCE(MAX(id),0) FROM job_identity)+ROW_NUMBER() OVER(ORDER BY id)
 FROM premerge_reviews;
INSERT INTO review_jobs(id,repository_id,event_id,mr_iid,commit_sha,base_sha,ordinal,
 config_hash,status,result_path,result_json,error,attempts,next_run_at,created_at,finished_at,
 target_branch,changed_files,scope_json,legacy_premerge_id,source,context_hint,context_json,
 execution_policy,correlation_id,mr_state,superseded)
 SELECT (SELECT MAX(id) FROM job_identity)-(SELECT COUNT(*) FROM premerge_reviews)
 +ROW_NUMBER() OVER(ORDER BY p.id),p.repository_id,e.id,p.mr_iid,p.head_sha,p.base_sha,0,
 'legacy-premerge-'||p.id,CASE WHEN p.status='superseded' THEN 'cancelled'
 WHEN p.status='running' THEN 'queued' ELSE p.status END,p.result_path,p.result_json,p.error,
 p.attempts,p.next_run_at,p.created_at,p.finished_at,r.target_branch,p.changed_files,
 p.scope_json,p.id,'premerge',p.context_hint,p.context_json,p.execution_policy,
 'legacy-premerge-'||p.id,'unknown',p.status='superseded'
 FROM premerge_reviews p JOIN repositories r ON r.id=p.repository_id
 JOIN merge_events e ON e.delivery_id='legacy-premerge-'||p.id AND e.repository_id=p.repository_id;
UPDATE review_jobs SET historical_import=1,
 usage_json=CASE WHEN json_valid(result_json) THEN json_extract(result_json,'$.usage') END
 WHERE legacy_premerge_id IS NOT NULL;
UPDATE review_issue_backfill SET completed=0 WHERE id=1;
INSERT INTO review_event_links(event_id,job_id,relation)
 SELECT event_id,id,'created' FROM review_jobs WHERE source='premerge';
INSERT INTO review_attempts(job_id,attempt_number,status,result_path,error,result_json,
 changed_files,correlation_id)
 SELECT id,attempts,status,result_path,error,result_json,changed_files,correlation_id
 FROM review_jobs WHERE source='premerge' AND attempts>0
 AND status IN ('complete','partial','failed','skipped','cancelled');
CREATE TRIGGER unified_premerge_projection AFTER UPDATE ON review_jobs
 WHEN NEW.legacy_premerge_id IS NOT NULL BEGIN
 UPDATE premerge_reviews SET status=CASE WHEN NEW.superseded=1 THEN 'superseded'
 ELSE NEW.status END,attempts=NEW.attempts,base_sha=NEW.base_sha,result_path=NEW.result_path,
 result_json=NEW.result_json,error=NEW.error,changed_files=NEW.changed_files,
 scope_json=NEW.scope_json,context_json=NEW.context_json,finished_at=NEW.finished_at,
 next_run_at=NEW.next_run_at WHERE id=NEW.legacy_premerge_id;
END;
CREATE INDEX idx_jobs_source ON review_jobs(source,id DESC);
CREATE TABLE deleted_premerge_versions (
 repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
 mr_iid INTEGER NOT NULL,head_sha TEXT NOT NULL,context_hint TEXT NOT NULL DEFAULT '',
 deleted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(repository_id,mr_iid,head_sha,context_hint)
);
CREATE TRIGGER preserve_deleted_premerge BEFORE DELETE ON review_jobs
 WHEN OLD.source='premerge' BEGIN
 INSERT OR IGNORE INTO deleted_premerge_versions(repository_id,mr_iid,head_sha,context_hint)
 VALUES(OLD.repository_id,OLD.mr_iid,OLD.commit_sha,COALESCE(OLD.context_hint,''));
END;
CREATE TABLE repository_query_sessions (
 id TEXT PRIMARY KEY,owner TEXT NOT NULL,remote_url TEXT NOT NULL,token_ciphertext TEXT NOT NULL,
 repository_id INTEGER REFERENCES repositories(id) ON DELETE CASCADE,
 credential_digest TEXT NOT NULL,credential_version TEXT NOT NULL,
 input_token_required INTEGER NOT NULL DEFAULT 0,
 result_json TEXT,expires_at TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE repository_discoveries ADD COLUMN query_session_id TEXT;
ALTER TABLE repository_discoveries ADD COLUMN operation TEXT NOT NULL DEFAULT 'metadata';
ALTER TABLE repository_discoveries ADD COLUMN search TEXT NOT NULL DEFAULT '';
ALTER TABLE repository_discoveries ADD COLUMN page INTEGER NOT NULL DEFAULT 1;
"""
