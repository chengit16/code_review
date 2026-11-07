"""第 40 版新增优化主题、阶段快照和问题关联；现有记录不会自动猜测归属。"""

IMPROVEMENT_THEME_MIGRATION = """
CREATE TABLE improvement_themes (
 id INTEGER PRIMARY KEY,
 client_key TEXT NOT NULL UNIQUE,
 title TEXT NOT NULL CHECK(length(trim(title)) BETWEEN 1 AND 160),
 category TEXT NOT NULL CHECK(category IN
   ('stability','performance','integration','deployment','experience','security','other')),
 status TEXT NOT NULL CHECK(status IN ('planned','active','paused','completed','deferred')),
 scope TEXT NOT NULL,
 objective TEXT NOT NULL,
 rationale TEXT NOT NULL,
 outcome TEXT NOT NULL,
 next_steps TEXT NOT NULL,
 "references" TEXT NOT NULL,
 version INTEGER NOT NULL DEFAULT 1 CHECK(version >= 1),
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX idx_improvement_themes_status ON improvement_themes(status,id DESC);
CREATE TABLE improvement_theme_phases (
 theme_id INTEGER NOT NULL REFERENCES improvement_themes(id),
 ordinal INTEGER NOT NULL CHECK(ordinal >= 0),
 title TEXT NOT NULL,
 goal TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('planned','active','completed','deferred')),
 solution TEXT NOT NULL,
 code_state TEXT NOT NULL CHECK(code_state IN ('unchanged','modified','not_applicable')),
 verification_state TEXT NOT NULL CHECK(verification_state IN
   ('not_run','passed','failed','blocked','not_applicable')),
 validation_evidence TEXT NOT NULL,
 deployment_state TEXT NOT NULL CHECK(deployment_state IN
   ('not_deployed','confirmed','unknown','not_applicable')),
 deployment_evidence TEXT NOT NULL,
 next_steps TEXT NOT NULL,
 PRIMARY KEY(theme_id,ordinal)
);
CREATE TABLE improvement_theme_links (
 theme_id INTEGER NOT NULL REFERENCES improvement_themes(id),
 improvement_id INTEGER NOT NULL REFERENCES project_improvements(id),
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 PRIMARY KEY(theme_id,improvement_id)
);
CREATE INDEX idx_improvement_theme_links_record ON improvement_theme_links(improvement_id,theme_id);
CREATE TABLE improvement_theme_revisions (
 theme_id INTEGER NOT NULL REFERENCES improvement_themes(id),
 version INTEGER NOT NULL,
 actor TEXT NOT NULL,
 note TEXT NOT NULL,
 snapshot_json TEXT NOT NULL,
 improvement_ids_json TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 PRIMARY KEY(theme_id,version)
);
"""
