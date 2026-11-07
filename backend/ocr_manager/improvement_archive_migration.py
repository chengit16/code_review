"""第 41 版补充归档元数据和历史动作；旧记录保持未归档，不改写业务结论。"""

IMPROVEMENT_ARCHIVE_MIGRATION = ""
for _table in ("project_improvements", "improvement_themes",
               "project_improvement_revisions", "improvement_theme_revisions"):
    IMPROVEMENT_ARCHIVE_MIGRATION += f"""
        ALTER TABLE {_table} ADD COLUMN archived_at TEXT;
        ALTER TABLE {_table} ADD COLUMN archived_by TEXT NOT NULL DEFAULT '';
        ALTER TABLE {_table} ADD COLUMN archive_reason TEXT NOT NULL DEFAULT '';
    """
for _table in ("project_improvement_revisions", "improvement_theme_revisions"):
    IMPROVEMENT_ARCHIVE_MIGRATION += f"""
        ALTER TABLE {_table} ADD COLUMN action TEXT NOT NULL DEFAULT 'update'
            CHECK(action IN ('create','update','archive','restore'));
        UPDATE {_table} SET action='create' WHERE version=1;
    """
for _table in ("project_improvements", "improvement_themes"):
    IMPROVEMENT_ARCHIVE_MIGRATION += f"""
        CREATE INDEX {_table}_archive ON {_table}(archived_at,id DESC);
    """
