"""保存 Agent 能力、方案、项目授权和按次执行证据。"""

AGENT_CAPABILITY_MIGRATION = """
CREATE TABLE IF NOT EXISTS agent_skills (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  pattern TEXT NOT NULL,
  body TEXT NOT NULL,
  actor TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS agent_mcp_services (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  endpoint TEXT NOT NULL,
  token_ciphertext TEXT,
  timeout_seconds INTEGER NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1,
  actor TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS agent_mcp_grants (
  service_id INTEGER NOT NULL REFERENCES agent_mcp_services(id),
  repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
  tool TEXT NOT NULL,
  PRIMARY KEY(service_id,repository_id,tool)
);
CREATE TABLE IF NOT EXISTS agent_schemes (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  basis_id INTEGER REFERENCES agent_schemes(id),
  document TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('draft','published','disabled')),
  actor TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT OR IGNORE INTO agent_schemes(id,name,document,state,actor)
  VALUES (1,'基础逐页评审','{"steps":[],"skill_ids":[]}', 'published','系统');
CREATE TABLE IF NOT EXISTS agent_scheme_default (
  id INTEGER PRIMARY KEY CHECK(id=1),
  scheme_id INTEGER NOT NULL REFERENCES agent_schemes(id)
);
INSERT OR IGNORE INTO agent_scheme_default VALUES (1,1);
CREATE TABLE IF NOT EXISTS agent_project_settings (
  repository_id INTEGER PRIMARY KEY REFERENCES repositories(id) ON DELETE CASCADE,
  scheme_id INTEGER REFERENCES agent_schemes(id),
  model_profile_id INTEGER REFERENCES model_profiles(id) ON DELETE RESTRICT,
  version INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_capability_audit (
  id INTEGER PRIMARY KEY,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  subject_id INTEGER NOT NULL,
  change_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS agent_capability_checks (
  id INTEGER PRIMARY KEY,
  kind TEXT NOT NULL CHECK(kind IN ('mcp','preview')),
  subject_id INTEGER NOT NULL,
  job_id INTEGER REFERENCES review_jobs(id) ON DELETE CASCADE,
  input_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','running','complete','failed')),
  result_json TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TEXT
);
CREATE INDEX IF NOT EXISTS agent_capability_checks_queue ON agent_capability_checks(status,id);
CREATE TABLE IF NOT EXISTS agent_run_capabilities (
  run_id INTEGER PRIMARY KEY REFERENCES agent_reviews(id) ON DELETE CASCADE,
  snapshot TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS agent_run_capabilities_scheme
  ON agent_run_capabilities(json_extract(snapshot,'$.scheme_id'),run_id);
CREATE TABLE IF NOT EXISTS agent_capability_events (
  id INTEGER PRIMARY KEY,
  run_id INTEGER NOT NULL REFERENCES agent_reviews(id) ON DELETE CASCADE,
  step TEXT NOT NULL,
  path TEXT NOT NULL,
  source TEXT NOT NULL,
  status TEXT NOT NULL,
  evidence TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(run_id,step,path,source)
);
"""
