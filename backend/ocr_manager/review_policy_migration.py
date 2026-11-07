"""为合并前队列冻结执行策略；旧记录保留空值，不能反推为新策略任务。"""

REVIEW_POLICY_MIGRATION = """
ALTER TABLE premerge_reviews ADD COLUMN execution_policy TEXT;
"""
