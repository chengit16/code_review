"""为每次双评审追加独立裁定历史，随比较来源级联清理。"""

AGENT_COMPARISON_MIGRATION = """
CREATE TABLE IF NOT EXISTS agent_comparison_curations (
  agent_review_id INTEGER NOT NULL REFERENCES agent_reviews(id) ON DELETE CASCADE,
  version INTEGER NOT NULL CHECK(version>0),
  document TEXT NOT NULL CHECK(json_valid(document)),
  actor TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(agent_review_id,version)
);
CREATE INDEX IF NOT EXISTS idx_agent_reviews_job_history ON agent_reviews(job_id,id DESC);
"""
