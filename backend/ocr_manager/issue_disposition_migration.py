"""第 50 版区分人工忽略与误报；保留旧状态约束和历史评价，不执行外部调用。"""

MIGRATION = """
ALTER TABLE review_issues ADD COLUMN dismissal_reason TEXT
 CHECK(dismissal_reason IS NULL OR dismissal_reason='false_positive');
UPDATE review_issues SET dismissal_reason='false_positive'
 WHERE status='ignored' AND EXISTS (
 SELECT 1 FROM review_issue_events e WHERE e.issue_id=review_issues.id
 AND e.id=(SELECT MAX(n.id) FROM review_issue_events n WHERE n.issue_id=e.issue_id)
 AND e.new_status='ignored' AND EXISTS (
 SELECT 1 FROM review_issue_occurrences o WHERE o.issue_id=e.issue_id
 AND e.note='任务 #'||o.job_id||' 第 '||o.attempt_number||' 次'||
 CASE WHEN o.recovery_id IS NULL THEN '' ELSE '补审 #'||o.recovery_id||' ' END||
 '发现 '||(o.comment_index+1)||'：标记为误报，同步忽略'));
CREATE VIEW review_issue_states AS SELECT id,repository_id,fingerprint,
 CASE WHEN status='ignored' AND dismissal_reason='false_positive'
 THEN 'false_positive' ELSE status END AS status,
 path,content,severity,category,first_seen_at,last_seen_at,closed_at,merged_into_id,
 dismissal_reason FROM review_issues;
"""
