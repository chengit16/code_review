"""新增独立影子任务与调用台账；旧 OCR 尝试无需回填或改写。"""

AGENT_REVIEW_MIGRATION = """
CREATE TABLE IF NOT EXISTS agent_reviews (
  id INTEGER PRIMARY KEY,
  job_id INTEGER NOT NULL REFERENCES review_jobs(id) ON DELETE CASCADE,
  source_attempt_id INTEGER NOT NULL REFERENCES review_attempts(id) ON DELETE CASCADE,
  previous_id INTEGER REFERENCES agent_reviews(id) ON DELETE CASCADE,
  request_key TEXT NOT NULL,
  base_sha TEXT NOT NULL,
  head_sha TEXT NOT NULL,
  ocr_config_hash TEXT NOT NULL,
  context_digest TEXT NOT NULL,
  model_snapshot TEXT NOT NULL,
  input_key TEXT,
  input_manifest_json TEXT,
  status TEXT NOT NULL DEFAULT 'queued'
    CHECK(status IN ('queued','running','complete','partial','failed','skipped','cancelled')),
  cancel_requested INTEGER NOT NULL DEFAULT 0 CHECK(cancel_requested IN (0,1)),
  reason TEXT,
  result_json TEXT,
  completed_pages INTEGER NOT NULL DEFAULT 0 CHECK(completed_pages>=0),
  progress_json TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  started_at TEXT,
  finished_at TEXT,
  UNIQUE(job_id, request_key)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_review_active ON agent_reviews(job_id)
  WHERE status IN ('queued','running');
CREATE INDEX IF NOT EXISTS idx_agent_review_queue ON agent_reviews(status,id);
CREATE INDEX IF NOT EXISTS idx_agent_review_source ON agent_reviews(source_attempt_id,id);
CREATE TABLE IF NOT EXISTS agent_review_calls (
  id TEXT PRIMARY KEY,
  agent_review_id INTEGER NOT NULL REFERENCES agent_reviews(id) ON DELETE CASCADE,
  hunk_id INTEGER NOT NULL,
  page_offset INTEGER NOT NULL,
  reserved_tokens INTEGER NOT NULL CHECK(reserved_tokens>0),
  prompt_tokens INTEGER,
  completion_tokens INTEGER,
  provider_model TEXT,
  status TEXT NOT NULL DEFAULT 'unknown' CHECK(status IN ('unknown','recorded')),
  started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TEXT,
  UNIQUE(agent_review_id,hunk_id,page_offset)
);
"""
