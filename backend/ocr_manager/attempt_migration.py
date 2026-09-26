"""扩展不可变尝试快照；旧库只能回填最后一次仍可确认的安全结果。"""

ATTEMPT_MIGRATION = """
ALTER TABLE review_jobs ADD COLUMN config_snapshot TEXT;
ALTER TABLE review_attempts ADD COLUMN config_snapshot TEXT;
ALTER TABLE review_attempts ADD COLUMN result_json TEXT;
ALTER TABLE review_attempts ADD COLUMN changed_files TEXT;
ALTER TABLE review_attempts ADD COLUMN started_at TEXT;
UPDATE review_attempts SET result_json=(SELECT result_json FROM review_jobs j
  WHERE j.id=job_id AND j.attempts=attempt_number AND j.status=review_attempts.status);
"""
