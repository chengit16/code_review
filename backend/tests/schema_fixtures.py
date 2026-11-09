"""只为临时测试库退回旧结构；禁止对真实数据库使用这些破坏性辅助函数。"""

import sqlite3


def remove_improvement_schema(db: sqlite3.Connection) -> None:
    """临时库模拟旧版时先移除第 39 版表，避免后续迁移撞上新版残留。"""

    remove_improvement_theme_schema(db)
    db.execute("DROP TABLE project_improvement_revisions")
    db.execute("DROP TABLE project_improvements")


def remove_improvement_theme_schema(db: sqlite3.Connection) -> None:
    """临时库回放第 40 版前移除主题表及其依赖关系。"""

    remove_improvement_archive_schema(db)
    db.execute("DROP TABLE improvement_theme_revisions")
    db.execute("DROP TABLE improvement_theme_links")
    db.execute("DROP TABLE improvement_theme_phases")
    db.execute("DROP TABLE improvement_themes")


def remove_observability_schema(db: sqlite3.Connection) -> None:
    """移除第 36 版新增结构，让旧库迁移用例真实重放新版 DDL。"""

    remove_improvement_schema(db)
    db.execute("DROP TABLE worker_execution_slots")
    db.execute("DROP TRIGGER review_attempt_evidence")
    db.execute("DROP TRIGGER review_stage_finished")
    db.execute("DROP TABLE review_stage_timings")
    db.execute("ALTER TABLE project_review_limits DROP COLUMN newline_filter_enabled")
    for table, columns in (
        ("review_jobs", ("scope_json", "reason_code", "attempt_ready_at")),
        ("premerge_reviews", ("scope_json",)),
        ("review_attempts", ("scope_json", "reason_code", "scheduled_at", "retry_ready_at")),
    ):
        for column in columns:
            db.execute(f"ALTER TABLE {table} DROP COLUMN {column}")


def remove_improvement_archive_schema(db: sqlite3.Connection) -> None:
    """仅对隔离库移除 41 版列和索引，使旧迁移测试完整重放归档结构。"""

    remove_improvement_maintenance_schema(db)
    for table in ("project_improvements", "improvement_themes",
                  "project_improvement_revisions", "improvement_theme_revisions"):
        columns = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
        db.execute(f"DROP INDEX IF EXISTS {table}_archive")
        for column in ("archived_at", "archived_by", "archive_reason", "action"):
            if column in columns:
                db.execute(f"ALTER TABLE {table} DROP COLUMN {column}")


def remove_improvement_maintenance_schema(db: sqlite3.Connection) -> None:
    """临时库回放旧结构前移除 42 版同步游标，避免外键阻止旧表重建。"""

    remove_finding_schema(db)
    db.execute("DROP TABLE IF EXISTS review_recovery_aggregates")
    db.execute("DROP TABLE IF EXISTS review_recoveries")
    db.execute("DROP TABLE IF EXISTS improvement_log_imports")
    db.execute("DROP TABLE IF EXISTS improvement_maintenance")


def remove_finding_schema(db: sqlite3.Connection) -> None:
    """仅测试库恢复 43 版出现表，保留旧记录以验证 44 版重建和反馈回填。"""

    remove_effective_schema(db)
    db.execute("DROP TABLE IF EXISTS review_finding_feedback")
    columns = {row[1] for row in db.execute("PRAGMA table_xinfo(review_issue_occurrences)")}
    if "recovery_id" in columns:
        db.execute("""CREATE TABLE review_issue_occurrences_legacy (
            id INTEGER PRIMARY KEY,issue_id INTEGER NOT NULL REFERENCES review_issues(id)
            ON DELETE CASCADE,job_id INTEGER NOT NULL REFERENCES review_jobs(id) ON DELETE CASCADE,
            attempt_number INTEGER NOT NULL,comment_index INTEGER NOT NULL,
            mr_iid INTEGER NOT NULL,commit_sha TEXT NOT NULL,path TEXT NOT NULL,start_line INTEGER,
            content TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            severity TEXT,category TEXT,UNIQUE(job_id,attempt_number,comment_index))""")
        fields = ("id,issue_id,job_id,attempt_number,comment_index,mr_iid,commit_sha,path,"
                  "start_line,content,created_at,severity,category")
        db.execute(f"INSERT INTO review_issue_occurrences_legacy({fields}) SELECT {fields} "
                   "FROM review_issue_occurrences WHERE recovery_id IS NULL")
        db.execute("DROP TABLE review_issue_occurrences")
        db.execute("ALTER TABLE review_issue_occurrences_legacy RENAME TO review_issue_occurrences")
        db.execute("CREATE INDEX idx_issue_occurrences_issue "
                   "ON review_issue_occurrences(issue_id,id DESC)")
        db.execute("CREATE INDEX idx_issue_occurrences_time "
                   "ON review_issue_occurrences(created_at,issue_id)")
    db.execute("DROP INDEX IF EXISTS review_recoveries_source")


def remove_effective_schema(db: sqlite3.Connection) -> None:
    """临时库回放旧迁移前移除有效结论投影和独立通知，禁止用于业务库。"""

    remove_issue_disposition_schema(db)
    remove_chat_capture_schema(db)
    db.execute("DROP TABLE IF EXISTS review_historical_diagnostics")
    for trigger in ("review_effective_attempt_changed", "review_effective_batch_changed",
                    "review_effective_batch_removed", "review_effective_aggregate_changed",
                    "review_effective_job_changed", "review_effective_attempt_removed",
                    "review_effective_aggregate_removed"):
        db.execute(f"DROP TRIGGER IF EXISTS {trigger}")
    db.execute("DROP TABLE IF EXISTS review_recovery_deliveries")
    db.execute("DROP TABLE IF EXISTS review_effective_conclusions")
    db.execute("DROP TABLE IF EXISTS review_recovery_fairness")
    columns = {row[1] for row in db.execute("PRAGMA table_info(review_recoveries)")}
    if "requested_by" in columns:
        db.execute("ALTER TABLE review_recoveries DROP COLUMN requested_by")


def remove_chat_capture_schema(db: sqlite3.Connection) -> None:
    """仅隔离测试库退回 46 版；按依赖顺序清理聊天表，不用于真实业务库。"""

    remove_recovery_budget_schema(db)
    db.execute("DROP TABLE IF EXISTS chat_capture_links")
    db.execute("DROP TABLE IF EXISTS chat_capture_events")
    db.execute("DROP TABLE IF EXISTS chat_source_bindings")


def remove_recovery_budget_schema(db: sqlite3.Connection) -> None:
    """仅隔离测试库退回 47 版，不修改真实业务库或导入历史。"""

    remove_scheduler_capacity_schema(db)
    db.execute("DROP TABLE IF EXISTS review_recovery_authorizations")
    db.execute("DROP TABLE IF EXISTS review_recovery_budget_evidence")


def remove_scheduler_capacity_schema(db: sqlite3.Connection) -> None:
    """仅合成库还原 48 版单槽及移除容量配置，确保旧迁移测试完整回放。"""

    from ocr_manager.scheduler_state import SCHEDULER_MIGRATION

    remove_issue_disposition_schema(db)
    db.execute("DROP TABLE IF EXISTS worker_scheduler_changes")
    db.execute("DROP TABLE IF EXISTS worker_scheduler_settings")
    columns = {row[1] for row in db.execute("PRAGMA table_info(worker_execution_slots)")}
    if "slot_id" in columns:
        db.execute("ALTER TABLE worker_execution_slots RENAME TO worker_slots_test49")
        db.execute(SCHEDULER_MIGRATION)
        db.execute("""INSERT INTO worker_execution_slots SELECT
            lane,owner,generation,task_kind,task_id,repository_id,pid,state,
            started_at,heartbeat_at,finished_at FROM worker_slots_test49 WHERE slot_index=1""")
        db.execute("DROP TABLE worker_slots_test49")


def remove_issue_disposition_schema(db: sqlite3.Connection) -> None:
    """仅测试库回放第 50 版前移除状态视图与原因列；反馈表按旧版约束重建。"""

    db.execute("DROP VIEW IF EXISTS review_issue_states")
    columns = {row[1] for row in db.execute("PRAGMA table_info(review_issues)")}
    if "dismissal_reason" in columns:
        db.execute("ALTER TABLE review_issues DROP COLUMN dismissal_reason")
