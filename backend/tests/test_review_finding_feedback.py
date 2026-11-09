"""用隔离 SQLite 验证稳定反馈、出现记录、版本竞争和迁移回滚；不调用真实模型或业务库。"""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from fastapi.testclient import TestClient
from ocr_manager.api import create_app
from ocr_manager.config import Settings
from ocr_manager.review_finding_feedback import FindingFeedbackVersion, write_feedback
from ocr_manager.review_recovery_domain import RecoveryConflict
from ocr_manager.review_recovery_store import cancel, claim, enqueue, finish
from ocr_manager.storage import Store
from schema_fixtures import remove_finding_schema
from test_auth import create_user, enable_users, login
from test_review_conclusions import recovered as recovered
from test_review_recovery import ADMIN, child_result, command, make_source

BASE = "/api/jobs/1/finding-feedback"
CHILD = "j1:a1:r1:c0"
VERSION = {"source_attempt": 1, "revision": 2}


def insert_legacy_fixed_feedback(store: Store, job_id: int, index: int, actor: str) -> None:
    """仅为兼容测试注入旧修复值，不通过新反馈接口生成历史数据。"""

    with store.connection() as db:
        attempt = db.execute("SELECT attempts FROM review_jobs WHERE id=?", (job_id,)).fetchone()[0]
        db.execute("INSERT INTO review_feedback(job_id,comment_index,verdict) VALUES(?,?,'fixed')",
                   (job_id, index))
        db.execute("INSERT INTO review_finding_feedback(finding_id,verdict,actor) "
                   "VALUES(?,'fixed',?)", (f"j{job_id}:a{attempt}:c{index}", actor))


def test_stable_feedback_isolated_from_initial_indices_and_publications(
    recovered: tuple[Store, Settings, dict[str, Any]],
) -> None:
    """同下标来自不同批次不互相覆盖；初审发现数量、映射与发布统计不误认补审。"""

    store, settings, _ = recovered
    with store.connection() as db:
        db.execute("""INSERT INTO gitlab_publications(job_id,attempt_number,comment_index,status)
            VALUES(1,1,0,'sent')""")
    with TestClient(create_app(settings)) as api:
        assert api.put(f"{BASE}/{CHILD}", headers=ADMIN,
                       json=VERSION | {"verdict": "false_positive"}).status_code == 200
        detail = api.get("/api/jobs/1", headers=ADMIN).json()
        assert detail["feedback"] == {} and detail["issue_ids"] == {"0": 1}
        listing = api.get("/api/task-search", headers=ADMIN).json()["items"][0]
        assert listing["finding_count"] == 3
        assert listing["issue_summary"]["open_count"] == 3
        assert listing["issue_summary"]["ignored_count"] == 0
        assert listing["issue_summary"]["open_count"] == 3
        assert listing["issue_summary"]["fixed_count"] == 0
        assert api.get("/api/task-search?issue_state=open", headers=ADMIN).json()["total"] == 1
        assert api.get("/api/task-search?issue_state=resolved", headers=ADMIN).json()["total"] == 0
        assert api.get("/api/task-search", headers=ADMIN).json()["status_counts"]["complete"] == 1
        issues = api.get("/api/review-issues/2", headers=ADMIN).json()
        assert issues["status"] == "open"
        assert issues["occurrences"][0]["finding_id"] == CHILD
        assert issues["occurrences"][0]["recovery_id"] == 1
        effect = api.get("/api/review-effectiveness?days=7", headers=ADMIN).json()
        assert effect["summary"]["generated"] == 3
        assert effect["summary"]["published"] == 1
        assert sum(p["published"] for p in effect["projects"]) == 1
        history = api.get(BASE, headers=ADMIN, params=VERSION)
        assert history.headers["cache-control"] == "no-store"
        assert [(item["finding_id"], item["verdict"]) for item in history.json()] == [
            (CHILD, "false_positive")]
        assert api.put(f"{BASE}/j1:a1:r2:c0", headers=ADMIN,
                       json=VERSION | {"verdict": "ignored"}).status_code == 200
        # 价值反馈不得替代跟进问题的独立处置状态。
        assert api.get("/api/review-issues/3", headers=ADMIN).json()["status"] == "open"
        assert api.get("/api/review-issues/1", headers=ADMIN).json()["status"] == "open"
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM notification_deliveries").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM gitlab_publications").fetchone()[0] == 1


def test_authenticated_reader_cannot_change_finding_feedback(
    recovered: tuple[Store, Settings, dict[str, Any]],
) -> None:
    """真实会话的只读角色可以查历史，但不能借新反馈路由修改或撤销问题决策。"""

    _, settings, _ = recovered
    with TestClient(create_app(settings)) as api:
        create_user(api, "administrator", "admin")
        create_user(api, "reader", "reader")
        enable_users(api)
        reader = login(api, "reader")
        headers = {"Authorization": f"Bearer {reader['token']}"}
        assert api.get(BASE, headers=headers, params=VERSION).status_code == 200
        assert api.put(f"{BASE}/{CHILD}", headers=headers,
                       json=VERSION | {"verdict": "fixed"}).status_code == 403
        assert api.delete(f"{BASE}/{CHILD}", headers=headers, params=VERSION).status_code == 403


def test_old_and_stable_root_feedback_share_one_decision(
    recovered: tuple[Store, Settings, dict[str, Any]],
) -> None:
    """根发现双向兼容旧反馈接口，不生成第二份计数；重审只清旧投影，保留历史审计。"""

    store, settings, raw = recovered
    with TestClient(create_app(settings)) as api:
        assert api.put("/api/jobs/1/feedback/0", headers=ADMIN,
                       json={"verdict": "helpful"}).status_code == 200
        assert api.get(BASE, headers=ADMIN, params=VERSION).json()[0]["verdict"] == "helpful"
        assert api.put(f"{BASE}/j1:a1:c0", headers=ADMIN,
                       json=VERSION | {"verdict": "ignored"}).status_code == 200
        assert api.get("/api/jobs/1", headers=ADMIN).json()["feedback"] == {"0": "ignored"}
        assert api.get("/api/review-feedback/summary", headers=ADMIN).json()[0]["total"] == 1
        assert api.delete("/api/jobs/1/feedback/0", headers=ADMIN).status_code == 200
        assert api.get(BASE, headers=ADMIN, params=VERSION).json() == []
        assert api.put(f"{BASE}/j1:a1:c0", headers=ADMIN,
                       json=VERSION | {"verdict": "helpful"}).status_code == 200
        assert store.retry_job(1) == 1
        assert api.put(f"{BASE}/j1:a1:c0", headers=ADMIN,
                       json=VERSION | {"verdict": "ignored"}).status_code == 409
        assert api.get(BASE, headers=ADMIN, params=VERSION).json()[0]["verdict"] == "helpful"
        assert store.next_job()
        store.finish_job(1, "partial", None, raw, None)
        assert api.get(BASE, headers=ADMIN,
                       params={"source_attempt": 2, "revision": 0}).json() == []
        assert api.get("/api/jobs/1", headers=ADMIN).json()["feedback"] == {}


@pytest.mark.parametrize("fault,expected", [
    ("unauthorized", 401), ("stale_revision", 409),
    ("stale_attempt", 409), ("missing_version", 422), ("bool_version", 422),
    ("unknown_field", 422), ("invalid_verdict", 422), ("legacy_fixed_write", 422),
    ("foreign_id", 404),
    ("unknown_id", 404), ("cancelled_source", 409), ("corrupt_origin", 409),
])
def test_feedback_fail_closed(
    recovered: tuple[Store, Settings, dict[str, Any]], fault: str, expected: int,
) -> None:
    """写入必须有管理员身份、显式最新版本和可信主来源；失败不留下反馈或问题决策。"""

    store, settings, _ = recovered
    payload: dict[str, Any] = VERSION | {"verdict": "ignored"}
    identifier = CHILD
    if fault == "stale_revision":
        payload["revision"] = 1
    elif fault == "stale_attempt":
        payload["source_attempt"] = 2
    elif fault == "missing_version":
        del payload["revision"]
    elif fault == "bool_version":
        payload["source_attempt"] = True
    elif fault == "unknown_field":
        payload["actor"] = "伪造作者"
    elif fault == "invalid_verdict":
        payload["verdict"] = "not_valid"
    elif fault == "legacy_fixed_write":
        payload["verdict"] = "fixed"
    elif fault == "foreign_id":
        identifier = "j2:a1:r1:c0"
    elif fault == "unknown_id":
        identifier = "j1:a1:r999:c0"
    elif fault == "cancelled_source":
        with store.connection() as db:
            db.execute("UPDATE review_jobs SET cancel_requested=1 WHERE id=1")
    elif fault == "corrupt_origin":
        with store.connection() as db:
            db.execute("UPDATE review_recovery_aggregates SET origins_json='[]' WHERE revision=2")
    with TestClient(create_app(settings)) as api:
        response = api.put(f"{BASE}/{identifier}", json=payload,
                           headers={} if fault == "unauthorized" else ADMIN)
        assert response.status_code == expected, response.text
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM review_finding_feedback").fetchone()[0] == 0
        assert db.execute(
            "SELECT COUNT(*) FROM review_issues WHERE status!='open'").fetchone()[0] == 0


def test_feedback_retraction_respects_later_manual_decisions(
    recovered: tuple[Store, Settings, dict[str, Any]],
) -> None:
    """撤销只清除价值反馈，不改变跟进问题人工处理；重复删除返回缺失。"""

    store, settings, _ = recovered
    with TestClient(create_app(settings)) as api:
        assert api.put(f"{BASE}/{CHILD}", headers=ADMIN,
                       json=VERSION | {"verdict": "ignored"}).status_code == 200
        assert api.delete(f"{BASE}/{CHILD}", headers=ADMIN, params=VERSION).status_code == 200
        assert api.delete(f"{BASE}/{CHILD}", headers=ADMIN, params=VERSION).status_code == 404
        assert api.put(f"{BASE}/{CHILD}", headers=ADMIN,
                       json=VERSION | {"verdict": "ignored"}).status_code == 200
        assert api.patch("/api/review-issues/2", headers=ADMIN,
                         json={"status": "ignored", "note": "独立人工判断"}).status_code == 200
        assert api.delete(f"{BASE}/{CHILD}", headers=ADMIN, params=VERSION).status_code == 200
        assert api.get("/api/review-issues/2", headers=ADMIN).json()["status"] == "ignored"


def test_concurrent_feedback_does_not_duplicate_occurrences_or_events(
    recovered: tuple[Store, Settings, dict[str, Any]],
) -> None:
    """多次同 verdict 写入由 SQLite 唯一键与事务串行化；不生成问题处理审计。"""

    store, _, _ = recovered
    def apply(_: int) -> None:
        write_feedback(store, 1, CHILD, FindingFeedbackVersion(**VERSION), "ignored", "合成管理员")

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(apply, range(8)))
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM review_finding_feedback").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM review_issue_occurrences").fetchone()[0] == 3
        assert db.execute(
            "SELECT COUNT(*) FROM review_issue_events WHERE issue_id=2").fetchone()[0] == 1


def test_feedback_write_does_not_write_issue_audit(
    recovered: tuple[Store, Settings, dict[str, Any]],
) -> None:
    """价值反馈不写问题审计；审计表不可写不影响独立反馈事务。"""

    store, _, _ = recovered
    with store.connection() as db:
        db.execute("""CREATE TRIGGER reject_feedback_audit BEFORE INSERT ON review_issue_events
            BEGIN SELECT RAISE(ABORT,'synthetic failure'); END""")
    write_feedback(store, 1, CHILD, FindingFeedbackVersion(**VERSION), "ignored", "合成管理员")
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM review_finding_feedback").fetchone()[0] == 1
        assert db.execute("SELECT status FROM review_issues WHERE id=2").fetchone()[0] == "open"


def test_capture_deduplicates_primary_origin_and_is_atomic(
    client: TestClient, settings: Settings,
) -> None:
    """新发现与聚合同事务，重复附加来源不新建出现记录；落库失败可安全重新终结。"""

    store, enabled, raw = make_source(client, settings)
    enqueue(store, enabled, 1, command())
    task = claim(store)
    assert task
    child = child_result(raw)
    child["comments"] *= 2
    with store.connection() as db:
        db.execute("""CREATE TRIGGER reject_capture BEFORE INSERT ON review_issue_occurrences
            BEGIN SELECT RAISE(ABORT,'synthetic failure'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        finish(store, task, child)
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM review_recovery_aggregates").fetchone()[0] == 0
        assert db.execute("SELECT status FROM review_recoveries").fetchone()[0] == "running"
        db.execute("DROP TRIGGER reject_capture")
    assert finish(store, task, child)
    assert not finish(store, task, child)
    with store.connection() as db:
        rows = db.execute("SELECT finding_id FROM review_issue_occurrences ORDER BY id").fetchall()
        assert [row[0] for row in rows] == ["j1:a1:c0", CHILD]
    with TestClient(create_app(enabled)) as api:
        duplicate = api.put(f"{BASE}/j1:a1:r1:c1", headers=ADMIN,
                            json={"source_attempt": 1, "revision": 1, "verdict": "ignored"})
        assert duplicate.status_code == 404


@pytest.mark.parametrize("state", ["cancelled", "failed", "stale"])
def test_unaccepted_batch_does_not_capture_candidate_findings(
    client: TestClient, settings: Settings, state: str,
) -> None:
    """取消、失败或失效批次保留用量，但不把未采纳的新发现录成平台问题。"""

    store, enabled, raw = make_source(client, settings)
    batch = enqueue(store, enabled, 1, command())
    task = claim(store)
    assert task
    if state == "cancelled":
        assert cancel(store, batch)
    elif state == "stale":
        # 活动补审会阻止全量重审入队；直接模拟执行期间父来源被取消的失效事实。
        assert store.retry_job(1) is None
        with store.connection() as db:
            db.execute("UPDATE review_jobs SET cancel_requested=1 WHERE id=1")
    assert finish(store, task, child_result(raw),
                  error_code="synthetic_failure" if state == "failed" else None)
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM review_issue_occurrences").fetchone()[0] == 1
        assert db.execute("SELECT status FROM review_recoveries").fetchone()[0] == state


def test_legacy_candidate_without_occurrence_is_not_silently_backfilled(
    recovered: tuple[Store, Settings, dict[str, Any]],
) -> None:
    """旧候选缺少出现记录时反馈显式冲突，不靠评论下标猜测问题或后台历史回填。"""

    store, _, _ = recovered
    with store.connection() as db:
        db.execute("DELETE FROM review_issue_occurrences WHERE finding_id=?", (CHILD,))
    with pytest.raises(RecoveryConflict, match="finding_occurrence_missing"):
        write_feedback(store, 1, CHILD, FindingFeedbackVersion(**VERSION), "ignored", "合成管理员")


@pytest.mark.parametrize("broken", [False, True])
def test_migration_preserves_legacy_feedback_and_rolls_back_failed_rebuild(
    client: TestClient, settings: Settings, broken: bool,
) -> None:
    """只在临时库回放 43→44；出现 ID、时间、问题关系和反馈保留，失败不留下半张表。"""

    store, _, _ = make_source(client, settings)
    insert_legacy_fixed_feedback(store, 1, 0, "合成旧作者")
    with store.connection() as db:
        remove_finding_schema(db)
        before = [tuple(row) for row in db.execute("SELECT * FROM review_issue_occurrences")]
        db.execute("PRAGMA user_version=43")
        if broken:
            db.execute("CREATE TABLE review_finding_feedback(blocker TEXT)")
    if broken:
        with pytest.raises(sqlite3.OperationalError):
            store.migrate()
        with store.connection() as db:
            assert db.execute("PRAGMA user_version").fetchone()[0] == 43
            assert [tuple(row) for row in db.execute(
                "SELECT * FROM review_issue_occurrences")] == before
            db.execute("DROP TABLE review_finding_feedback")
    store.migrate()
    store.migrate()
    with store.connection() as db:
        row = dict(db.execute("SELECT * FROM review_issue_occurrences").fetchone())
        assert row.pop("finding_id") == "j1:a1:c0" and row.pop("recovery_id") is None
        assert tuple(row.values()) == before[0]
        feedback = db.execute("SELECT * FROM review_finding_feedback").fetchone()
        assert feedback["verdict"] == "fixed" and feedback["actor"] == "历史反馈迁移"
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_occurrence_foreign_key_binds_recovery_to_original_attempt(
    recovered: tuple[Store, Settings, dict[str, Any]],
) -> None:
    """数据库约束拒绝把补审来源挂到其他根尝试；不能只靠接口校验防错。"""

    store, _, _ = recovered
    with pytest.raises(sqlite3.IntegrityError), store.connection() as db:
        db.execute("UPDATE review_issue_occurrences SET attempt_number=2 WHERE recovery_id=1")
    with pytest.raises(RecoveryConflict, match="feedback_version_changed"):
        write_feedback(store, 1, CHILD, FindingFeedbackVersion(source_attempt=1, revision=1),
                       "ignored", "合成管理员")


def test_schema51_adds_ignore_feedback_and_preserves_legacy_repair(
    recovered: tuple[Store, Settings, dict[str, Any]],
) -> None:
    """第 51 版保留旧修复评价与原时间，新增忽略可写且不改问题状态。"""

    store, _, _ = recovered
    insert_legacy_fixed_feedback(store, 1, 0, "合成旧作者")
    with store.connection() as db:
        for table, definition in (
            ("review_feedback", "job_id INTEGER NOT NULL, comment_index INTEGER NOT NULL, "
             "verdict TEXT NOT NULL CHECK(verdict IN ('helpful','false_positive','fixed')), "
             "updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, "
             "PRIMARY KEY(job_id,comment_index)"),
            ("review_finding_feedback", "finding_id TEXT PRIMARY KEY "
             "REFERENCES review_issue_occurrences(finding_id) ON DELETE CASCADE, "
             "verdict TEXT NOT NULL CHECK(verdict IN ('helpful','false_positive','fixed')), "
             "actor TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"),
        ):
            backup = f"{table}_51test"
            db.execute(f"CREATE TABLE {backup} ({definition})")
            db.execute(f"INSERT INTO {backup} SELECT * FROM {table}")
            db.execute(f"DROP TABLE {table}")
            db.execute(f"ALTER TABLE {backup} RENAME TO {table}")
        db.execute("PRAGMA user_version=50")
    store.migrate()
    with store.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 51
        verdict = db.execute(
            "SELECT verdict FROM review_finding_feedback WHERE finding_id='j1:a1:c0'").fetchone()[0]
        assert verdict == "fixed"
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    before = store.get_job(1)["issue_statuses"]
    assert store.set_review_feedback(1, 0, "ignored", "合成管理员") is None
    assert store.get_job(1)["issue_statuses"] == before
    assert store.get_job(1)["feedback"][0] == "ignored"
