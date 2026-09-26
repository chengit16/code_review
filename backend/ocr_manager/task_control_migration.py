"""独立任务停止迁移，避免 Store 与管理路由互相依赖。"""

CONTROL_MIGRATION = """
ALTER TABLE review_jobs ADD COLUMN cancel_requested INTEGER NOT NULL DEFAULT 0;
"""
