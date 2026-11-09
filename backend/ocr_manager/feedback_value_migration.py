"""第 51 版加入明确忽略反馈；保留旧修复评价和时间，不推断任何问题处置。"""

MIGRATION = """
CREATE TABLE review_feedback_v51 (
 job_id INTEGER NOT NULL REFERENCES review_jobs(id),
 comment_index INTEGER NOT NULL CHECK(comment_index>=0),
 verdict TEXT NOT NULL CHECK(verdict IN ('helpful','false_positive','ignored','fixed')),
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(job_id,comment_index)
);
INSERT INTO review_feedback_v51 SELECT * FROM review_feedback;
DROP TABLE review_feedback;
ALTER TABLE review_feedback_v51 RENAME TO review_feedback;
CREATE TABLE review_finding_feedback_v51 (
 finding_id TEXT PRIMARY KEY REFERENCES review_issue_occurrences(finding_id) ON DELETE CASCADE,
 verdict TEXT NOT NULL CHECK(verdict IN ('helpful','false_positive','ignored','fixed')),
 actor TEXT NOT NULL,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO review_finding_feedback_v51 SELECT * FROM review_finding_feedback;
DROP TABLE review_finding_feedback;
ALTER TABLE review_finding_feedback_v51 RENAME TO review_finding_feedback;
"""
