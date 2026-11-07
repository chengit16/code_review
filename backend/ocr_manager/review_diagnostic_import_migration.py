"""第 46 版独立保存历史诊断及导入来源；不修改初审结果、补审摘要或投递事实。"""

DIAGNOSTIC_IMPORT_MIGRATION = """
CREATE TABLE review_historical_diagnostics (
 job_id INTEGER NOT NULL REFERENCES review_jobs(id) ON DELETE CASCADE,
 attempt_number INTEGER NOT NULL CHECK(attempt_number>0),
 source_kind TEXT NOT NULL CHECK(source_kind IN ('attempt','job')),
 source_status TEXT NOT NULL CHECK(source_status IN ('partial','failed')),
 head_sha TEXT NOT NULL,
 base_sha TEXT,
 source_result_json TEXT NOT NULL CHECK(json_valid(source_result_json)),
 artifact_digest TEXT NOT NULL,
 analysis_json TEXT NOT NULL CHECK(json_valid(analysis_json)),
 imported_by TEXT NOT NULL,
 imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(job_id,attempt_number)
);
"""
