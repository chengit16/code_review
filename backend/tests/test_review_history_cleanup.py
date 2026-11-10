"""隔离验证一次性历史清理的北京时间边界、保留事实、拒绝条件与事务回滚。"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from ocr_manager.review_history_cleanup import apply_cleanup, plan_cleanup
from ocr_manager.storage import Store

CUTOFF = "2026-11-08 16:00:00"


@pytest.fixture
def database(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """仅建临时 schema 52 库；一条旧任务、一条恰好零点的任务及各自反馈。"""

    path = tmp_path / "app.db"
    Store(path).migrate()
    db = sqlite3.connect(path)
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("""INSERT INTO repositories(id,name,gitlab_url,project_id,remote_url,
        target_branch,auth_kind,webhook_secret,feishu_webhook)
        VALUES(1,'隔离项目','https://example.invalid',1,'https://example.invalid/r.git',
        'main','secret','合成','合成')""")
    for identifier, created in ((1, "2026-11-08 15:59:59"), (2, CUTOFF)):
        db.execute("""INSERT INTO merge_events(id,repository_id,mr_iid,status,created_at)
            VALUES(?,1,?,'done',?)""", (identifier, identifier, created))
        db.execute("INSERT INTO job_identity(id) VALUES(?)", (identifier,))
        db.execute("""INSERT INTO review_jobs(id,repository_id,event_id,mr_iid,commit_sha,
            ordinal,config_hash,status,created_at,finished_at,attempts)
            VALUES(?,1,?,?,?,0,'合成','complete',?,?,1)""",
                   (identifier, identifier, identifier, str(identifier), created, created))
        db.execute("""INSERT INTO review_attempts(job_id,attempt_number,status,finished_at)
            VALUES(?,1,'complete',?)""", (identifier, created))
        db.execute("INSERT INTO notification_deliveries(job_id,status) VALUES(?,'sent')",
                   (identifier,))
        db.execute("""INSERT INTO review_issues(id,repository_id,fingerprint,path,content,
            first_seen_at,last_seen_at) VALUES(?,1,?,'src/x.py','合成问题',?,?)""",
                   (identifier, str(identifier), created, created))
        db.execute("""INSERT INTO review_issue_occurrences(issue_id,job_id,attempt_number,
            comment_index,mr_iid,commit_sha,path,content,created_at)
            VALUES(?,?,1,0,?,?,'src/x.py','合成问题',?)""",
                   (identifier, identifier, identifier, str(identifier), created))
        db.execute("""INSERT INTO review_feedback(job_id,comment_index,verdict)
            VALUES(?,0,'helpful')""", (identifier,))
        db.execute("""INSERT INTO review_finding_feedback(finding_id,verdict,actor)
            VALUES(?,'helpful','隔离测试')""", (f"j{identifier}:a1:c0",))
        db.execute("""INSERT INTO review_issue_events(issue_id,new_status,actor,created_at)
            VALUES(?,'open','隔离测试',?)""", (identifier, created))
    db.commit()
    yield db
    db.close()


def test_cleanup_preserves_midnight_jobs_and_all_other_tables(database: sqlite3.Connection) -> None:
    """UTC 16 点即北京时间零点；任务身份、事件及配置不可回退或删除。"""

    plan = plan_cleanup(database, CUTOFF)
    assert plan.job_ids == (1,) and plan.issue_ids == (1,)
    result = apply_cleanup(database, plan)
    assert result["deleted_jobs"] == result["deleted_issues"] == 1
    for table in ("review_jobs", "review_issues"):
        assert database.execute(f"SELECT id FROM {table}").fetchall() == [(2,)]
    assert database.execute("SELECT job_id FROM review_attempts").fetchall() == [(2,)]
    assert database.execute("SELECT job_id FROM review_feedback").fetchall() == [(2,)]
    assert database.execute("SELECT finding_id FROM review_finding_feedback").fetchall() == [
        ("j2:a1:c0",)]
    assert database.execute("SELECT count(*) FROM merge_events").fetchone()[0] == 2
    assert database.execute("SELECT count(*) FROM job_identity").fetchone()[0] == 2
    assert database.execute("PRAGMA foreign_key_check").fetchall() == []
    assert database.execute("PRAGMA user_version").fetchone()[0] == 52
    assert apply_cleanup(database, plan_cleanup(database, CUTOFF))["deleted_jobs"] == 0


def test_preview_change_rejected(database: sqlite3.Connection) -> None:
    """不只校验数量；预览后的配置变化也要求重新备份和演练。"""

    plan = plan_cleanup(database, CUTOFF)
    database.execute("UPDATE repositories SET name='已变化' WHERE id=1")
    database.commit()
    with pytest.raises(ValueError, match="预览后数据库发生变化"):
        apply_cleanup(database, plan)
    assert database.execute("SELECT count(*) FROM review_jobs").fetchone()[0] == 2


def test_cross_day_issue_rejected(database: sqlite3.Connection) -> None:
    """保留任务复用旧问题时不擅自改写首次发现或人工处置。"""

    database.execute("UPDATE review_issue_occurrences SET issue_id=1 WHERE job_id=2")
    database.commit()
    with pytest.raises(ValueError, match="跨日问题"):
        plan_cleanup(database, CUTOFF)


def test_retained_merge_dependency_rejected(database: sqlite3.Connection) -> None:
    """旧合并目标被今天问题引用时，拒绝外键自动置空破坏今天的结论。"""

    database.execute("UPDATE review_issues SET status='merged',merged_into_id=1 WHERE id=2")
    database.commit()
    with pytest.raises(ValueError, match="保留问题依赖旧合并目标"):
        plan_cleanup(database, CUTOFF)


@pytest.mark.parametrize("table,predicate", [
    ("review_jobs", "status='running'"),
    ("merge_events", "status='queued'"),
    ("notification_deliveries", "status='pending'"),
])
def test_inflight_work_rejected(database: sqlite3.Connection, table: str, predicate: str) -> None:
    """排队、执行和投递都不能在清理时继续推进。"""

    database.execute(f"UPDATE {table} SET {predicate}")
    database.commit()
    with pytest.raises(ValueError, match="在途或待处理"):
        plan_cleanup(database, CUTOFF)


def test_unexpected_trigger_rolls_back(database: sqlite3.Connection) -> None:
    """未知级联或触发器若修改保留事实，删除整体回滚。"""

    database.execute("""CREATE TRIGGER unexpected_cleanup AFTER DELETE ON review_jobs BEGIN
        UPDATE repositories SET name='不可接受的副作用' WHERE id=1; END""")
    database.commit()
    plan = plan_cleanup(database, CUTOFF)
    with pytest.raises(ValueError, match="保留数据发生非预期变化"):
        apply_cleanup(database, plan)
    assert database.execute("SELECT name FROM repositories").fetchone()[0] == "隔离项目"
    assert database.execute("SELECT count(*) FROM review_jobs").fetchone()[0] == 2
    assert database.execute("SELECT count(*) FROM review_feedback").fetchone()[0] == 2


def test_wrong_schema_rejected_without_migration(database: sqlite3.Connection) -> None:
    """维护不顺带升级或降级业务库。"""

    database.execute("PRAGMA user_version=49")
    with pytest.raises(ValueError, match="schema 52"):
        plan_cleanup(database, CUTOFF)
    assert database.execute("PRAGMA user_version").fetchone()[0] == 49
