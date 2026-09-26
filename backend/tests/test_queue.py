"""保护 SQLite 队列事务、顺序、重复事件及重跑通知状态。"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from ocr_manager import storage
from ocr_manager.storage import SCHEMA, SCHEMA_VERSION, Store
from ocr_manager.worker import worker_lock


def make_store(tmp_path: Path) -> tuple[Store, int]:
    """建立最小仓库记录，测试数据库唯一约束和事务顺序。"""

    store = Store(tmp_path / "app.db")
    store.migrate()
    repository_id = store.add_repository(
        {
            "name": "示例",
            "gitlab_url": "https://gitlab.example.test",
            "project_id": 42,
            "remote_url": "git@gitlab.example.test:team/repo.git",
            "target_branch": "main",
            "auth_kind": "secret",
            "webhook_secret": "ciphertext",
            "feishu_webhook": "ciphertext",
        }
    )
    return store, repository_id


def snapshots(commits: list[str], config_hash: str = "cfg") -> dict[str, tuple[str, str]]:
    """为队列测试提供每个提交对应的不可变配置与规则摘要。"""

    return {sha: (config_hash, "rule-blob") for sha in commits}


def test_event_and_job_queue_are_idempotent_and_ordered(tmp_path: Path) -> None:
    """同一 MR 的提交按序领取，重复投递不会生成第二批任务。"""

    store, repository_id = make_store(tmp_path)
    assert store.add_event(repository_id, 7, "delivery-1", "a" * 40, None)
    assert not store.add_event(repository_id, 7, "delivery-2", "a" * 40, None)
    event = store.next_event()
    assert event is not None
    commits = ["a" * 40, "b" * 40]
    store.finish_event(
        event["id"],
        commits,
        {commits[0]: ("cfg-a", "rule-a"), commits[1]: ("cfg-b", "rule-b")},
        None,
    )
    first = store.next_job()
    assert first is not None and first["commit_sha"] == "a" * 40
    assert (first["config_hash"], first["rule_digest"]) == ("cfg-a", "rule-a")
    assert store.next_job() is None
    store.finish_job(first["id"], "complete", "result.json", {"comments": []}, None)
    second = store.next_job()
    assert second is not None and second["commit_sha"] == "b" * 40
    assert (second["config_hash"], second["rule_digest"]) == ("cfg-b", "rule-b")


def test_retry_does_not_send_stale_result(tmp_path: Path) -> None:
    """重审后先移除旧投递，再按新结果建立待发通知。"""

    store, repository_id = make_store(tmp_path)
    store.add_event(repository_id, 7, "delivery-1", "a" * 40, None)
    event = store.next_event()
    assert event is not None
    store.finish_event(event["id"], ["a" * 40], snapshots(["a" * 40]), None)
    job = store.next_job()
    assert job is not None
    store.finish_job(job["id"], "failed", None, None, "模型失败")
    assert store.retry_job(job["id"])
    assert store.next_delivery() is None
    retried = store.next_job()
    assert retried is not None
    store.finish_job(job["id"], "complete", "result.json", {"comments": []}, None)
    assert store.next_delivery() is not None


def test_recovery_requeues_claimed_work(tmp_path: Path) -> None:
    """单 Worker 意外退出后，被领取但未确认的工作可重新处理。"""

    store, repository_id = make_store(tmp_path)
    store.add_event(repository_id, 7, "delivery-1", None, None)
    assert store.next_event() is not None
    store.recover()
    assert store.next_event() is not None


def test_worker_lock_rejects_a_second_instance(tmp_path: Path) -> None:
    """第二个 Worker 无法在首个实例运行时重置队列或重复领取任务。"""

    with worker_lock(tmp_path):
        with pytest.raises(RuntimeError, match="已有 Worker"):
            with worker_lock(tmp_path):
                pass
    with worker_lock(tmp_path):
        pass


def test_recovery_records_interrupted_job_and_retry_limit(tmp_path: Path) -> None:
    """每次崩溃计入尝试历史，第三次中断后失败并进入通知队列。"""

    store, repository_id = make_store(tmp_path)
    store.add_event(repository_id, 7, None, None, None)
    event = store.next_event()
    assert event is not None
    store.finish_event(event["id"], ["a" * 40], snapshots(["a" * 40]), None)
    for attempt in range(1, 4):
        job = store.next_job()
        assert job is not None
        store.recover()
        detail = store.get_job(job["id"])
        assert detail is not None
        assert detail["status"] == ("failed" if attempt == 3 else "queued")
        assert len(detail["attempt_history"]) == attempt
    assert detail["delivery"]["status"] == "pending"
    assert store.next_job() is None


def test_permanent_feishu_failure_stops_automatic_retry(tmp_path: Path) -> None:
    """无效机器人配置不重复投递，管理员修正后仍可手动重发。"""

    store, repository_id = make_store(tmp_path)
    store.add_event(repository_id, 7, None, None, None)
    event = store.next_event()
    assert event is not None
    store.finish_event(event["id"], ["a" * 40], snapshots(["a" * 40]), None)
    job = store.next_job()
    assert job is not None
    store.finish_job(job["id"], "complete", None, {"comments": []}, None)
    delivery = store.next_delivery()
    assert delivery is not None
    store.finish_delivery(delivery["id"], "飞书返回 HTTP 401", retryable=False)
    detail = store.get_job(job["id"])
    assert detail is not None
    assert detail["delivery"]["status"] == "failed"
    assert store.next_delivery() is None
    assert store.retry_delivery(job["id"])
    assert store.next_delivery() is not None


def test_recovery_honors_event_and_delivery_limits(tmp_path: Path) -> None:
    """中断中的事件及通知达到上限后进入可见终态。"""

    store, repository_id = make_store(tmp_path)
    store.add_event(repository_id, 7, None, None, None)
    event = store.next_event()
    assert event is not None
    with store.connection() as db:
        db.execute("UPDATE merge_events SET attempts=3 WHERE id=?", (event["id"],))
    store.recover()
    assert store.list_events()[0]["status"] == "needs_attention"
    store.retry_event(event["id"])
    claimed = store.next_event()
    assert claimed is not None
    store.finish_event(event["id"], ["a" * 40], snapshots(["a" * 40]), None)
    job = store.next_job()
    assert job is not None
    store.finish_job(job["id"], "complete", None, {}, None)
    delivery = store.next_delivery()
    assert delivery is not None
    with store.connection() as db:
        db.execute("UPDATE notification_deliveries SET attempts=5 WHERE id=?", (delivery["id"],))
    store.recover()
    detail = store.get_job(job["id"])
    assert detail is not None
    assert detail["delivery"]["status"] == "failed"


def test_temporary_failure_is_bounded_and_records_attempts(tmp_path: Path) -> None:
    """临时故障不会立即丢任务，第三次失败后保留历史并生成通知。"""

    store, repository_id = make_store(tmp_path)
    store.add_event(repository_id, 7, "delivery-1", "a" * 40, None)
    event = store.next_event()
    assert event is not None
    store.finish_event(event["id"], ["a" * 40], snapshots(["a" * 40]), None)
    for attempt in range(1, 4):
        job = store.next_job()
        assert job is not None
        store.defer_job(job["id"], "模型暂时不可用")
        detail = store.get_job(job["id"])
        assert detail is not None
        assert detail["status"] == ("failed" if attempt == 3 else "queued")
        if attempt < 3:
            with store.connection() as db:
                db.execute(
                    "UPDATE review_jobs SET next_run_at=CURRENT_TIMESTAMP WHERE id=?", (job["id"],)
                )
    assert len(detail["attempt_history"]) == 3
    assert detail["delivery"]["status"] == "pending"


def test_repository_rotation_preserves_mr_order(tmp_path: Path) -> None:
    """一个仓库的后续提交等待前序结果，其他仓库可先获得评审机会。"""

    store, first_repo = make_store(tmp_path)
    second_repo = store.add_repository(
        {
            "name": "其他项目",
            "gitlab_url": "https://gitlab.example.test",
            "project_id": 43,
            "remote_url": "git@gitlab.example.test:team/other.git",
            "target_branch": "main",
            "auth_kind": "secret",
            "webhook_secret": "ciphertext",
            "feishu_webhook": "ciphertext",
        }
    )
    for repository_id, commits in ((first_repo, ["a" * 40, "b" * 40]), (second_repo, ["c" * 40])):
        store.add_event(repository_id, 7, f"delivery-{repository_id}", None, None)
        event = store.next_event()
        assert event is not None
        store.finish_event(event["id"], commits, snapshots(commits), None)
    first = store.next_job()
    assert first is not None and first["repository_id"] == first_repo
    other = store.next_job(first_repo)
    assert other is not None and other["repository_id"] == second_repo
    store.finish_job(first["id"], "complete", "result.json", {}, None)
    third = store.next_job(second_repo)
    assert third is not None and third["commit_sha"] == "b" * 40


def test_manual_retry_starts_new_retry_budget(tmp_path: Path) -> None:
    """历史尝试次数保留，但人工重跑应获得完整的新一轮退避次数。"""

    store, repository_id = make_store(tmp_path)
    store.add_event(repository_id, 7, None, None, None)
    event = store.next_event()
    assert event is not None
    store.finish_event(event["id"], ["a" * 40], snapshots(["a" * 40]), None)
    first = store.next_job()
    assert first is not None
    store.finish_job(first["id"], "failed", None, None, "初次失败")
    assert store.retry_job(first["id"]) == first["id"]
    retried = store.next_job()
    assert retried is not None
    store.defer_job(retried["id"], "暂时失败")
    detail = store.get_job(retried["id"])
    assert detail is not None
    assert detail["status"] == "queued"
    assert detail["attempts"] == 2


def test_schema_migrates_existing_v1_database(tmp_path: Path) -> None:
    """已部署的旧数据库升级后保留事件并加入新的重试字段。"""

    store = Store(tmp_path / "app.db")
    with store.connection() as db:
        db.executescript(SCHEMA)
        db.execute("PRAGMA user_version=1")
    store.migrate()
    with store.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        columns = {row["name"] for row in db.execute("PRAGMA table_info(review_jobs)")}
        assert "retry_start_attempts" in columns


def test_failed_migration_rolls_back_ddl_and_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """迁移中途失败时不能留下新表或提前提升 user_version。"""

    store = Store(tmp_path / "app.db")
    store.migrate()
    with store.connection() as db:
        db.execute("PRAGMA user_version=6")
        db.execute("DROP TABLE connection_checks")
        db.execute("ALTER TABLE review_jobs DROP COLUMN rule_digest")
    monkeypatch.setattr(
        storage,
        "SCHEMA_V7",
        "CREATE TABLE migration_probe (id INTEGER);\nCREATE TABLE migration_probe (id INTEGER);",
    )
    with pytest.raises(sqlite3.OperationalError):
        store.migrate()
    with store.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 6
        assert (
            db.execute("SELECT name FROM sqlite_master WHERE name='migration_probe'").fetchone()
            is None
        )


def test_changed_model_creates_new_job_snapshot(tmp_path: Path) -> None:
    """旧结论可追溯，模型版本变化后的重评审使用新任务 ID。"""

    store, repository_id = make_store(tmp_path)
    store.add_event(repository_id, 7, None, None, None)
    event = store.next_event()
    assert event is not None
    store.finish_event(event["id"], ["a" * 40], snapshots(["a" * 40], "old"), None)
    first = store.next_job()
    assert first is not None
    store.finish_job(first["id"], "complete", None, {}, None)
    new_id = store.retry_job(first["id"], "new")
    assert new_id is not None and new_id != first["id"]
    assert store.get_job(first["id"])["status"] == "complete"
    assert store.get_job(new_id)["status"] == "queued"
    assert store.get_job(new_id)["rule_digest"] == "rule-blob"


def test_job_detail_does_not_expose_raw_model_thinking(tmp_path: Path) -> None:
    """原始 OCR 工件保留，浏览器详情只接收发现和覆盖投影。"""

    store, repository_id = make_store(tmp_path)
    store.add_event(repository_id, 7, None, None, None)
    event = store.next_event()
    assert event is not None
    store.finish_event(event["id"], ["a" * 40], snapshots(["a" * 40]), None)
    job = store.next_job()
    assert job is not None
    store.finish_job(
        job["id"],
        "complete",
        "result.json",
        {
            "thinking": "private-reasoning",
            "comments": [
                {"path": "main.py", "content": "修复边界", "thinking": "private-reasoning"}
            ],
            "manifest": {
                "terminal_state": "complete",
                "coverage": {"selected": []},
                "execution": {"thinking": "private-reasoning"},
            },
        },
        None,
    )
    detail = store.get_job(job["id"])
    assert detail is not None
    assert "private-reasoning" not in json.dumps(detail)
    assert detail["result"]["comments"] == [{"path": "main.py", "content": "修复边界"}]
    with store.connection() as db:
        row = db.execute("SELECT result_json FROM review_jobs WHERE id=?", (job["id"],))
        assert "private-reasoning" not in row.fetchone()[0]


def test_paused_repository_holds_jobs_and_notifications(tmp_path: Path) -> None:
    """暂停仓库时保留已入库工作，恢复后从同一状态继续处理。"""

    store, repository_id = make_store(tmp_path)
    store.add_event(repository_id, 7, None, None, None)
    event = store.next_event()
    assert event is not None
    store.finish_event(event["id"], ["a" * 40], snapshots(["a" * 40]), None)
    assert store.update_repository(repository_id, {"enabled": False})
    assert store.next_job() is None
    assert store.update_repository(repository_id, {"enabled": True})
    job = store.next_job()
    assert job is not None
    store.finish_job(job["id"], "complete", "result.json", {}, None)
    assert store.update_repository(repository_id, {"enabled": False})
    assert store.next_delivery() is None
    assert store.update_repository(repository_id, {"enabled": True})
    assert store.next_delivery() is not None
