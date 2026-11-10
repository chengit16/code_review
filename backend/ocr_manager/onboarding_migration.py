"""扩展目标测试与异步仓库资料获取；旧测试保留历史，不补造当前版本证明。"""

MIGRATION = """
ALTER TABLE connection_checks RENAME TO legacy_connection_checks;
DROP INDEX idx_connection_checks_active;
DROP INDEX idx_connection_checks_queue;
CREATE TABLE connection_checks (
 id INTEGER PRIMARY KEY,
 kind TEXT NOT NULL CHECK(kind IN ('git','gitlab','model','feishu')),
 repository_id INTEGER REFERENCES repositories(id),
 model_profile_id INTEGER,
 notification_target_id INTEGER,
 config_revision_id INTEGER,
 config_fingerprint TEXT,
 status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','running','passed','failed')),
 error TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, finished_at TEXT,
 CHECK((kind='model' AND repository_id IS NULL AND notification_target_id IS NULL)
 OR (kind IN ('git','gitlab') AND repository_id IS NOT NULL
     AND model_profile_id IS NULL AND notification_target_id IS NULL)
 OR (kind='feishu' AND model_profile_id IS NULL
     AND ((repository_id IS NOT NULL AND notification_target_id IS NULL)
       OR (repository_id IS NULL AND notification_target_id IS NOT NULL))))
);
INSERT INTO connection_checks
 (id,kind,repository_id,config_revision_id,status,error,created_at,finished_at)
 SELECT id,kind,repository_id,config_revision_id,status,error,created_at,finished_at
 FROM legacy_connection_checks;
DROP TABLE legacy_connection_checks;
CREATE UNIQUE INDEX idx_connection_checks_active ON connection_checks
 (kind,COALESCE(repository_id,0),COALESCE(model_profile_id,0),COALESCE(notification_target_id,0))
 WHERE status IN ('queued','running');
CREATE INDEX idx_connection_checks_queue ON connection_checks(status,id);
CREATE TABLE repository_discoveries (
 id INTEGER PRIMARY KEY,
 remote_url TEXT NOT NULL,
 token_ciphertext TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','running','passed','failed')),
 result_json TEXT, error TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, finished_at TEXT
);
CREATE INDEX idx_repository_discoveries_queue ON repository_discoveries(status,id);
"""
