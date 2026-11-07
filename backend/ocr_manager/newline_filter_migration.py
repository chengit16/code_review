"""新增默认关闭的项目换行过滤开关；不改变旧任务和第 36 版迁移。"""

NEWLINE_FILTER_MIGRATION = """
ALTER TABLE project_review_limits ADD COLUMN newline_filter_enabled INTEGER NOT NULL DEFAULT 0
 CHECK(newline_filter_enabled IN (0,1));
"""
