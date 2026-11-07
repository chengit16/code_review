"""统一当前有效发现的反馈统计；兼容旧初审反馈，补审按主身份计数，历史不复活为当前。"""

from ocr_manager.review_effective import EFFECTIVE

CURRENT_FEEDBACK = f"""SELECT j.id AS job_id,j.repository_id,f.verdict,j.finished_at AS generated_at
 FROM review_feedback f JOIN review_jobs j ON j.id=f.job_id
 WHERE j.status IN ('complete','partial','failed','skipped')
 UNION ALL
 SELECT j.id,j.repository_id,f.verdict,o.created_at FROM review_finding_feedback f
 JOIN review_issue_occurrences o ON o.finding_id=f.finding_id
 JOIN review_jobs j ON j.id=o.job_id AND j.attempts=o.attempt_number
 JOIN ({EFFECTIVE}) e ON e.job_id=j.id
 WHERE o.recovery_id IS NOT NULL AND EXISTS (
 SELECT 1 FROM json_each(e.document_json,'$.findings') x
 WHERE json_extract(x.value,'$.finding_id')=o.finding_id)"""
