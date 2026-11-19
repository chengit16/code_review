"""53→54：保留旧分支及历史任务，合并后订阅迁至 Push，不产生模型或通知任务。"""

from ocr_manager.config_history import CONFIG_FIELDS

MIGRATION = """
ALTER TABLE repositories ADD COLUMN target_branches TEXT NOT NULL DEFAULT '[]'
 CHECK(json_valid(target_branches) AND json_type(target_branches)='array');
UPDATE repositories SET target_branches=json_array(target_branch);
UPDATE repositories SET enable_default_branch_pushes=1 WHERE enable_merge_requests=1;
UPDATE repositories SET enable_merge_requests=0 WHERE enable_merge_requests=1;
ALTER TABLE merge_events ADD COLUMN target_branch TEXT NOT NULL DEFAULT '';
UPDATE merge_events SET target_branch=COALESCE(
 (SELECT j.target_branch FROM review_jobs j WHERE j.event_id=merge_events.id LIMIT 1),
 (SELECT r.target_branch FROM repositories r WHERE r.id=merge_events.repository_id),'');
ALTER TABLE premerge_reviews ADD COLUMN target_branch TEXT NOT NULL DEFAULT '';
UPDATE premerge_reviews SET target_branch=COALESCE(
 (SELECT r.target_branch FROM repositories r WHERE r.id=premerge_reviews.repository_id),'');
ALTER TABLE merged_review_ranges RENAME TO merged_review_ranges_v53;
CREATE TABLE merged_review_ranges (
 repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
 mr_iid INTEGER NOT NULL,head_sha TEXT NOT NULL,before_sha TEXT NOT NULL,after_sha TEXT NOT NULL,
 job_id INTEGER REFERENCES review_jobs(id) ON DELETE SET NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,target_branch TEXT NOT NULL,
 PRIMARY KEY(repository_id,mr_iid,head_sha,before_sha,after_sha,target_branch)
);
INSERT INTO merged_review_ranges
 SELECT m.repository_id,m.mr_iid,m.head_sha,m.before_sha,m.after_sha,m.job_id,m.created_at,
 COALESCE((SELECT j.target_branch FROM review_jobs j WHERE j.id=m.job_id),
 (SELECT r.target_branch FROM repositories r WHERE r.id=m.repository_id),'')
 FROM merged_review_ranges_v53 m;
DROP TABLE merged_review_ranges_v53;
CREATE INDEX idx_merged_ranges ON merged_review_ranges(repository_id,before_sha,after_sha);
DROP TRIGGER preserve_deleted_premerge;
ALTER TABLE deleted_premerge_versions RENAME TO deleted_premerge_versions_v53;
CREATE TABLE deleted_premerge_versions (
 repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
 mr_iid INTEGER NOT NULL,head_sha TEXT NOT NULL,context_hint TEXT NOT NULL DEFAULT '',
 target_branch TEXT NOT NULL,deleted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(repository_id,mr_iid,head_sha,context_hint,target_branch)
);
INSERT INTO deleted_premerge_versions
 SELECT d.repository_id,d.mr_iid,d.head_sha,d.context_hint,r.target_branch,d.deleted_at
 FROM deleted_premerge_versions_v53 d JOIN repositories r ON r.id=d.repository_id;
DROP TABLE deleted_premerge_versions_v53;
CREATE TRIGGER preserve_deleted_premerge BEFORE DELETE ON review_jobs
 WHEN OLD.source='premerge' BEGIN
 INSERT OR IGNORE INTO deleted_premerge_versions
 (repository_id,mr_iid,head_sha,context_hint,target_branch)
 VALUES(OLD.repository_id,OLD.mr_iid,OLD.commit_sha,COALESCE(OLD.context_hint,''),OLD.target_branch);
END;
CREATE INDEX idx_events_branch ON merge_events(repository_id,target_branch,id);
CREATE INDEX idx_merged_branch ON merged_review_ranges(repository_id,target_branch);
"""

# 旧配置版本原样保留；新分支数组的增删改也必须进入配置审计与恢复证据。

_fields = (*CONFIG_FIELDS["repository"][1], "target_branches")
_before = "json_object(" + ",".join(f"'{key}',OLD.{key}" for key in _fields) + ")"
_after = "json_object(" + ",".join(f"'{key}',NEW.{key}" for key in _fields) + ")"
MIGRATION += f"""
DROP TRIGGER history_repositories_insert;
DROP TRIGGER history_repositories_update;
DROP TRIGGER history_repositories_delete;
CREATE TRIGGER history_repositories_insert AFTER INSERT ON repositories BEGIN
 INSERT INTO config_revisions(object_type,object_id,action,after_json)
 VALUES('repository',NEW.id,'created',{_after}); END;
CREATE TRIGGER history_repositories_update AFTER UPDATE ON repositories
 WHEN {_before}!={_after} BEGIN
 INSERT INTO config_revisions(object_type,object_id,action,before_json,after_json)
 VALUES('repository',NEW.id,'updated',{_before},{_after}); END;
CREATE TRIGGER history_repositories_delete AFTER DELETE ON repositories BEGIN
 INSERT INTO config_revisions(object_type,object_id,action,before_json)
 VALUES('repository',OLD.id,'deleted',{_before}); END;
"""
