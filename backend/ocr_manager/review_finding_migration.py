"""第 44 版保存稳定来源的出现与反馈；保留旧索引接口，迁移不启动补审或历史模型调用。"""

FINDING_MIGRATION = """
CREATE UNIQUE INDEX review_recoveries_source
 ON review_recoveries(id,job_id,source_attempt);
CREATE TABLE review_issue_occurrences_v44 (
 id INTEGER PRIMARY KEY,
 issue_id INTEGER NOT NULL REFERENCES review_issues(id) ON DELETE CASCADE,
 job_id INTEGER NOT NULL REFERENCES review_jobs(id) ON DELETE CASCADE,
 attempt_number INTEGER NOT NULL,
 comment_index INTEGER NOT NULL CHECK(comment_index>=0),
 recovery_id INTEGER REFERENCES review_recoveries(id) ON DELETE CASCADE,
 finding_id TEXT GENERATED ALWAYS AS (
  'j'||job_id||':a'||attempt_number||
  CASE WHEN recovery_id IS NULL THEN '' ELSE ':r'||recovery_id END||':c'||comment_index
 ) STORED NOT NULL UNIQUE,
 mr_iid INTEGER NOT NULL,
 commit_sha TEXT NOT NULL,
 path TEXT NOT NULL,
 start_line INTEGER,
 content TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 severity TEXT,
 category TEXT,
 FOREIGN KEY(recovery_id,job_id,attempt_number)
  REFERENCES review_recoveries(id,job_id,source_attempt) ON DELETE CASCADE
);
INSERT INTO review_issue_occurrences_v44
 (id,issue_id,job_id,attempt_number,comment_index,mr_iid,commit_sha,path,start_line,
  content,created_at,severity,category)
 SELECT id,issue_id,job_id,attempt_number,comment_index,mr_iid,commit_sha,path,start_line,
  content,created_at,severity,category FROM review_issue_occurrences;
DROP TABLE review_issue_occurrences;
ALTER TABLE review_issue_occurrences_v44 RENAME TO review_issue_occurrences;
CREATE UNIQUE INDEX review_occurrences_initial
 ON review_issue_occurrences(job_id,attempt_number,comment_index) WHERE recovery_id IS NULL;
CREATE UNIQUE INDEX review_occurrences_recovery
 ON review_issue_occurrences(recovery_id,comment_index) WHERE recovery_id IS NOT NULL;
CREATE INDEX review_occurrences_source
 ON review_issue_occurrences(job_id,attempt_number,comment_index);
CREATE INDEX idx_issue_occurrences_issue ON review_issue_occurrences(issue_id,id DESC);
CREATE INDEX idx_issue_occurrences_time ON review_issue_occurrences(created_at,issue_id);
CREATE TABLE review_finding_feedback (
 finding_id TEXT PRIMARY KEY REFERENCES review_issue_occurrences(finding_id) ON DELETE CASCADE,
 verdict TEXT NOT NULL CHECK(verdict IN ('helpful','false_positive','fixed')),
 actor TEXT NOT NULL,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO review_finding_feedback(finding_id,verdict,actor,updated_at)
 SELECT o.finding_id,f.verdict,'历史反馈迁移',f.updated_at
 FROM review_feedback f JOIN review_jobs j ON j.id=f.job_id
 JOIN review_issue_occurrences o ON o.job_id=j.id AND o.attempt_number=j.attempts
  AND o.comment_index=f.comment_index AND o.recovery_id IS NULL;
"""
