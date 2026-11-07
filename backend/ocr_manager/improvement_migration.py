"""第 39 版仅新增平台改进台账与历史；不导入聊天或改写评审业务数据。"""

IMPROVEMENT_MIGRATION = """
CREATE TABLE project_improvements (
 id INTEGER PRIMARY KEY,
 client_key TEXT NOT NULL UNIQUE,
 title TEXT NOT NULL CHECK(length(trim(title)) BETWEEN 1 AND 160),
 kind TEXT NOT NULL CHECK(kind IN ('problem','improvement')),
 category TEXT NOT NULL CHECK(category IN
   ('stability','performance','integration','deployment','experience','security','other')),
 status TEXT NOT NULL CHECK(status IN
   ('open','investigating','planned','verifying','resolved','deferred')),
 scope TEXT NOT NULL,
 description TEXT NOT NULL,
 analysis TEXT NOT NULL,
 solution TEXT NOT NULL,
 code_state TEXT NOT NULL CHECK(code_state IN ('unchanged','modified','not_applicable')),
 verification_state TEXT NOT NULL CHECK(verification_state IN
   ('not_run','passed','failed','blocked','not_applicable')),
 validation_evidence TEXT NOT NULL,
 deployment_state TEXT NOT NULL CHECK(deployment_state IN
   ('not_deployed','confirmed','unknown','not_applicable')),
 deployment_evidence TEXT NOT NULL,
 next_steps TEXT NOT NULL,
 "references" TEXT NOT NULL,
 version INTEGER NOT NULL DEFAULT 1 CHECK(version >= 1),
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX idx_improvements_filter ON project_improvements(status,kind,id DESC);
CREATE TABLE project_improvement_revisions (
 improvement_id INTEGER NOT NULL REFERENCES project_improvements(id),
 version INTEGER NOT NULL,
 actor TEXT NOT NULL,
 note TEXT NOT NULL,
 snapshot_json TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 PRIMARY KEY(improvement_id,version)
);
"""
