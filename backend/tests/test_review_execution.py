"""验证评审故障落库、有限重试及版本失效；仅使用临时数据库和合成 Git/OCR。"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import httpx
import pytest
from ocr_manager import storage, worker
from ocr_manager.config import Settings
from ocr_manager.premerge import enqueue_premerge, next_premerge, retry_premerge
from ocr_manager.review_failures import ReviewFailure
from ocr_manager.secrets import SecretBox
from ocr_manager.storage import Store
from schema_fixtures import remove_observability_schema
from test_review_failures import SHA, failed_result


@pytest.fixture
def environment(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> tuple[Store, int]:
    """持久化隔离项目并替换所有 Git/GitLab 调用，不读取真实仓库或网络。"""

    store = Store(settings.data_dir / "app.db")
    store.migrate()
    repository_id = store.add_repository({
        "name": "评审稳定性测试", "gitlab_url": "https://synthetic.invalid", "project_id": 42,
        "remote_url": "https://synthetic.invalid/team/repo.git", "target_branch": "main",
        "auth_kind": "secret", "webhook_secret": "synthetic-ciphertext",
        "feishu_webhook": "synthetic-ciphertext",
        "gitlab_token_ciphertext": SecretBox(settings.master_key).encrypt("synthetic-token")})

    class FakeGit:
        """模拟不可变范围与工作目录，清理时不执行文件删除。"""

        def __init__(self, *_args: Any) -> None:
            pass

        def fetch(self) -> None:
            pass

        def is_on_target(self, _sha: str) -> bool:
            return True

        def is_range_base(self, _base: str, _head: str) -> bool:
            return True

        def fetch_mr_head(self, _iid: int, _head: str) -> None:
            pass

        def checkout(self, _sha: str, target: Path) -> None:
            target.mkdir(parents=True, exist_ok=True)

        def changed_files(self, _sha: str) -> list[dict[str, Any]]:
            return [{"path": "main.py", "added": 1, "deleted": 0}]

        def range_changed_files(self, _base: str, head: str) -> list[dict[str, Any]]:
            return self.changed_files(head)

        def commit_author(self, _sha: str) -> str:
            return "合成提交人"

        def remove_checkout(self, _target: Path) -> None:
            pass

    class FakeGitLab:
        """返回已核对的 MR 头，不接受真实凭据。"""

        def __init__(self, *_args: Any) -> None:
            pass

        def check_access(self, *_args: Any) -> None:
            pass

        def get_merge_request(self, *_args: Any) -> dict[str, Any]:
            return {"state": "opened", "sha": SHA, "target_branch": "main",
                    "target_project_id": 42,
                    "diff_refs": {"base_sha": "b" * 40, "head_sha": SHA}}

    monkeypatch.setattr(worker, "GitRepository", FakeGit)
    monkeypatch.setattr(worker, "GitLabClient", FakeGitLab)
    return store, repository_id


def enqueue_job(store: Store, repository_id: int, settings: Settings) -> int:
    """按真实配置摘要创建一个不可变测试任务，再由公开领取入口执行。"""

    assert store.add_event(repository_id, 7, "synthetic-event", SHA, None)
    event = store.next_event()
    assert event is not None
    store.finish_event(event["id"], [SHA], {SHA: (
        worker.config_hash(store, settings, "", repository_id), "")}, None)
    return store.list_jobs()[0]["id"]


@pytest.mark.parametrize("code", [404, 429, 503])
def test_failed_result_is_saved_with_bounded_retry(
    environment: tuple[Store, int], settings: Settings, monkeypatch: pytest.MonkeyPatch, code: int,
) -> None:
    """404 立即失败；429/5xx 只允许额外一次尝试，每次保留工件、用量和原始错误。"""

    store, repository_id = environment
    job_id = enqueue_job(store, repository_id, settings)

    def fake_review(_settings: Settings, _checkout: Path, run_dir: Path,
                    *_args: Any, **_kwargs: Any) -> tuple[str, dict[str, Any]]:
        raw = failed_result(code)
        (run_dir / "result.json").write_text(json.dumps(raw), encoding="utf-8")
        return "failed", raw

    monkeypatch.setattr(worker, "run_review", fake_review)
    for number in range(1, (1 if code == 404 else 2) + 1):
        job = store.next_job()
        assert job is not None
        worker.review_job(store, settings, job)
        detail = store.get_job(job_id)
        assert detail is not None
        final = code == 404 or number == 2
        assert detail["status"] == ("failed" if final else "queued")
        assert f"HTTP {code}" in detail["error"]
        assert detail["result"]["comments"] == []
        assert detail["result"]["diagnostic"]["retry_scheduled"] is not final
        assert detail["result"]["usage"]["input_tokens"] == 50
        assert len(detail["attempt_history"]) == number
        attempt = detail["attempt_history"][0]
        assert attempt["started_at"] is not None
        assert Path(attempt["result_path"]).is_file()
        assert "synthetic-private" not in attempt["result_json"]
        assert json.loads(attempt["result_json"])["retry_summary"]["total_retries"] == 2
        assert (detail["delivery"] is not None) is final
        if not final:
            with store.connection() as db:
                assert db.execute(
                    "SELECT next_run_at>CURRENT_TIMESTAMP FROM review_jobs WHERE id=?",
                    (job_id,)).fetchone()[0] == 1
                db.execute("UPDATE review_jobs SET next_run_at=CURRENT_TIMESTAMP WHERE id=?",
                           (job_id,))
    assert store.next_job() is None
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM notification_deliveries").fetchone()[0] == 1


@pytest.mark.parametrize("error", [RuntimeError("synthetic-private-token"),
                                   ReviewFailure("timeout", "OCR result 超时"),
                                   httpx.ConnectError("synthetic-private-token")])
def test_exception_retry_is_separate_from_event_policy(
    environment: tuple[Store, int], settings: Settings, monkeypatch: pytest.MonkeyPatch,
    error: Exception, caplog: pytest.LogCaptureFixture,
) -> None:
    """模型整体超时和未知异常不重试，网络瞬断例外；日志不泄漏外部异常正文。"""

    store, repository_id = environment
    job_id = enqueue_job(store, repository_id, settings)

    def fail(*_args: Any, **_kwargs: Any) -> tuple[str, dict[str, Any]]:
        raise error

    monkeypatch.setattr(worker, "run_review", fail)
    job = store.next_job()
    assert job is not None
    worker.review_job(store, settings, job)
    detail = store.get_job(job_id)
    assert detail is not None
    assert detail["status"] == ("queued" if isinstance(error, httpx.ConnectError) else "failed")
    assert "synthetic-private-token" not in str(detail["error"]) + caplog.text
    assert worker.is_temporary(RuntimeError("事件临时错误"))


def test_recovery_and_manual_retry_keep_new_budget(
    environment: tuple[Store, int], settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """重启不重置两次预算，人工确认重跑则开始新周期但保留原尝试历史。"""

    store, repository_id = environment
    job_id = enqueue_job(store, repository_id, settings)

    def fail(*_args: Any, **_kwargs: Any) -> tuple[str, dict[str, Any]]:
        raise httpx.ConnectError("synthetic-private")

    monkeypatch.setattr(worker, "run_review", fail)
    first = store.next_job()
    assert first is not None
    worker.review_job(store, settings, first)
    with store.connection() as db:
        db.execute("UPDATE review_jobs SET next_run_at=CURRENT_TIMESTAMP WHERE id=?", (job_id,))
    assert store.next_job() is not None
    store.recover()
    detail = store.get_job(job_id)
    assert detail is not None and detail["status"] == "failed"
    assert len(detail["attempt_history"]) == 2
    assert all(item["started_at"] for item in detail["attempt_history"])
    assert store.retry_job(job_id) == job_id
    third = store.next_job()
    assert third is not None
    worker.review_job(store, settings, third)
    detail = store.get_job(job_id)
    assert detail is not None and detail["status"] == "queued"
    assert len(detail["attempt_history"]) == 3


@pytest.mark.parametrize("code", [404, 429])
def test_premerge_uses_same_failure_policy(
    environment: tuple[Store, int], settings: Settings, monkeypatch: pytest.MonkeyPatch, code: int,
) -> None:
    """合并前审查共享空评论兼容与两次上限，但不创建合并后通知。"""

    store, repository_id = environment
    with store.connection() as db:
        db.execute("INSERT INTO premerge_settings(repository_id,enabled) VALUES(?,1)",
                   (repository_id,))
    assert enqueue_premerge(store, repository_id, 7, SHA)
    monkeypatch.setattr(worker, "run_review", lambda *_args, **_kw: ("failed", failed_result(code)))
    for attempt in range(1, (1 if code == 404 else 2) + 1):
        review = next_premerge(store)
        assert review is not None
        worker.review_premerge(store, settings, review)
        with store.connection() as db:
            row = db.execute("SELECT * FROM premerge_reviews WHERE id=?",
                             (review["id"],)).fetchone()
            assert row["status"] == ("queued" if code == 429 and attempt == 1 else "failed")
            assert f"HTTP {code}" in row["error"]
            assert json.loads(row["result_json"])["comments"] == []
            assert db.execute("SELECT COUNT(*) FROM notification_deliveries").fetchone()[0] == 0
            db.execute("UPDATE premerge_reviews SET next_run_at=CURRENT_TIMESTAMP WHERE id=?",
                       (review["id"],))
    assert next_premerge(store) is None


def test_old_premerge_failure_cannot_requeue_superseded_version(
    environment: tuple[Store, int], settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """模型失败的同时新版本入队，旧故障不能使过期评审重新成为可运行任务。"""

    store, repository_id = environment
    with store.connection() as db:
        db.execute("INSERT INTO premerge_settings(repository_id,enabled) VALUES(?,1)",
                   (repository_id,))
    assert enqueue_premerge(store, repository_id, 7, SHA)

    def replace_version(*_args: Any, **_kwargs: Any) -> tuple[str, dict[str, Any]]:
        assert enqueue_premerge(store, repository_id, 7, "c" * 40)
        return "failed", failed_result(429)

    monkeypatch.setattr(worker, "run_review", replace_version)
    review = next_premerge(store)
    assert review is not None
    worker.review_premerge(store, settings, review)
    with store.connection() as db:
        rows = db.execute("SELECT status FROM premerge_reviews ORDER BY id").fetchall()
    assert [row["status"] for row in rows] == ["superseded", "queued"]


def test_policy_migration_preserves_legacy_versions_without_guessing_policy(
    environment: tuple[Store, int], settings: Settings,
) -> None:
    """模拟 34 版旧队列升级；不回填新策略，旧任务必须人工重建后才能执行。"""

    store, repository_id = environment
    with store.connection() as db:
        db.execute("INSERT INTO premerge_settings(repository_id,enabled) VALUES(?,1)",
                   (repository_id,))
    assert enqueue_premerge(store, repository_id, 7, SHA)
    with store.connection() as db:
        remove_observability_schema(db)
        db.execute("ALTER TABLE premerge_reviews DROP COLUMN execution_policy")
        db.execute("PRAGMA user_version=34")
    store.migrate()
    with store.connection() as db:
        old = db.execute("SELECT * FROM premerge_reviews").fetchone()
        assert old["execution_policy"] is None and old["head_sha"] == SHA
        assert db.execute("PRAGMA user_version").fetchone()[0] == storage.SCHEMA_VERSION
    claimed = next_premerge(store)
    assert claimed is not None
    worker.review_premerge(store, settings, claimed)
    with store.connection() as db:
        old = db.execute("SELECT * FROM premerge_reviews").fetchone()
        assert old["status"] == "failed" and "执行策略已变化" in old["error"]
    new_id = retry_premerge(store, claimed["id"])
    assert new_id is not None and new_id != claimed["id"]
    with store.connection() as db:
        new = db.execute("SELECT execution_policy FROM premerge_reviews WHERE id=?",
                         (new_id,)).fetchone()
        assert json.loads(new["execution_policy"])["review_policy"]["max_attempts"] == 2


def test_failed_policy_migration_rolls_back_ddl(
    environment: tuple[Store, int], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """新增策略列迁移失败时，DDL 与版本号一起回滚，不留下半升级数据库。"""

    store, _repository_id = environment
    with store.connection() as db:
        remove_observability_schema(db)
        db.execute("ALTER TABLE premerge_reviews DROP COLUMN execution_policy")
        db.execute("PRAGMA user_version=34")
    monkeypatch.setattr(storage, "REVIEW_POLICY_MIGRATION", """
        ALTER TABLE premerge_reviews ADD COLUMN execution_policy TEXT;
        CREATE TABLE invalid_test (id INTEGER);
        CREATE TABLE invalid_test (id INTEGER);
    """)
    with pytest.raises(sqlite3.OperationalError):
        store.migrate()
    with store.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 34
        columns = {row["name"] for row in db.execute("PRAGMA table_info(premerge_reviews)")}
        assert "execution_policy" not in columns
        assert db.execute("SELECT name FROM sqlite_master WHERE name='invalid_test'").fetchone(
        ) is None
