"""用合成 SQLite/工件验证补审资格、幂等、版本聚合和互斥；不访问真实 Git 或模型。"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from ocr_manager.api import create_app
from ocr_manager.attempt_history import save_snapshot
from ocr_manager.config import Settings
from ocr_manager.monitoring import eligible_artifacts, prune_artifacts
from ocr_manager.review_recovery_contracts import RecoveryCreate
from ocr_manager.review_recovery_domain import RecoveryConflict
from ocr_manager.review_recovery_store import (
    cancel,
    claim,
    eligibility,
    enqueue,
    finish,
    public_record,
)
from ocr_manager.storage import Store
from ocr_manager.worker import configuration_snapshot, snapshot_hash
from test_task_operations import populate

PATHS = ("alpha/done.py", "beta/comma,name[1].ts", "gamma/space name.py")
ADMIN = {"X-Admin-Token": "test-admin-token"}


def make_source(client: TestClient, settings: Settings) -> tuple[Store, Settings, dict[str, Any]]:
    """生成有可信快照和原始工件的部分初审；只在本次测试目录中构造业务事实。"""

    store, repository_id = populate(client, settings, 1)
    job = store.next_job()
    assert job
    snapshot = configuration_snapshot(store, settings, repository_id=repository_id)
    with store.connection() as db:
        db.execute("UPDATE review_jobs SET config_hash=? WHERE id=1", (snapshot_hash(snapshot),))
    save_snapshot(store, 1, snapshot)
    items = [{"path": path, "item_id": f"root-{index}"} for index, path in enumerate(PATHS)]
    raw: dict[str, Any] = {
        "comments": [{"path": PATHS[0], "content": "合成初审发现"}],
        "summary": {"input_tokens": 4, "output_tokens": 2, "total_tokens": 6},
        "manifest": {
            "schema_version": "ocr.run-manifest/v1",
            "terminal_state": "partial",
            "input": {"mode": "commit", "resolved_head": job["commit_sha"]},
            "coverage": {
                "selected": items,
                "completed": items[:1],
                "reused": [],
                "waived": [],
                "failed": [item | {"classification": "timeout"} for item in items[1:]],
            },
        },
    }
    path = settings.data_dir / "runs" / "1" / "2" / "result.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(raw))
    store.finish_job(1, "partial", str(path), raw, None)
    return store, settings, raw


def command(revision: int = 0, **changes: Any) -> RecoveryCreate:
    """显式批准固定源版本与有限预算，不允许通过请求指定路径。"""

    return RecoveryCreate.model_validate(
        {
            "client_key": str(uuid4()),
            "source_attempt": 1,
            "source_revision": revision,
            "token_budget": 1000,
            "timeout_seconds": 20,
            **changes,
        }
    )


def child_result(
    raw: dict[str, Any], *, partial: bool = False, paths: tuple[str, ...] = PATHS[1:]
) -> dict[str, Any]:
    """独立批次使用新的局部 item ID，平台聚合只能按已批准路径映射回根身份。"""

    items = [{"path": path, "item_id": f"child-{index}"} for index, path in enumerate(paths)]
    return {
        "comments": [{"path": paths[0], "content": "合成补审发现"}],
        "summary": {"input_tokens": 2, "output_tokens": 1, "total_tokens": 3},
        "manifest": {
            "schema_version": "ocr.run-manifest/v1",
            "terminal_state": "partial" if partial else "complete",
            "input": raw["manifest"]["input"],
            "coverage": {
                "selected": items,
                "completed": items[:1] if partial else items,
                "failed": items[1:] if partial else [],
                "reused": [],
                "waived": [],
            },
        },
    }


@pytest.fixture
def recovery(client: TestClient, settings: Settings) -> tuple[Store, Settings, dict[str, Any]]:
    """每个补审场景使用独立初审，不复用真实任务或 session。"""

    return make_source(client, settings)


def test_default_available_and_strict_admin_api(
    client: TestClient,
    settings: Settings,
    recovery: tuple[Store, Settings, dict[str, Any]],
) -> None:
    """无需开关即可查询资格；JSON 字符串 UUID 可重放，路径/布尔整数注入和匿名写入拒绝。"""

    store, enabled, _ = recovery
    url = "/api/jobs/1/recoveries"
    body = command().model_dump(mode="json")
    assert client.get("/api/jobs/1/recovery-eligibility").status_code == 401
    assert client.post(url, json=body).status_code == 401
    assert client.get("/api/jobs/1/recovery-eligibility", headers=ADMIN).json()["eligible"]
    assert claim(store) is None
    with TestClient(create_app(enabled)) as api:
        for changes in (
            {"paths": ["outside.py"]},
            {"token_budget": True},
            {"source_revision": -1},
            {"client_key": "invalid"},
        ):
            assert api.post(url, headers=ADMIN, json=body | changes).status_code == 422
        qualification = api.get("/api/jobs/1/recovery-eligibility", headers=ADMIN).json()
        assert qualification.pop("snapshot")["head_sha"] == "0" * 39 + "1"
        assert qualification == {
            "eligible": True,
            "reason_code": None,
            "source_attempt": 1,
            "source_revision": 0,
            "remaining_count": 2,
            "remaining_paths": list(PATHS[1:]),
            "max_token_budget": 100000,
            "max_timeout_seconds": 30,
            "remaining_batches": 3,
            "active_recovery_id": None,
            "route": "independent_subset",
            "budget": {"authorization_version": 0, "max_batches": 3, "used_batches": 0,
                       "max_total_tokens": 100000, "committed_tokens": 0,
                       "minimum_start_tokens": 0, "previous_gate": None},
        }
        first = api.post(url, headers=ADMIN, json=body)
        assert first.status_code == 202
        assert api.post(url, headers=ADMIN, json=body).json()["id"] == first.json()["id"]
        assert first.json()["status"] == "queued"
        assert api.post(url, headers=ADMIN, json=body | {"token_budget": 999}).status_code == 409
        assert api.get(url, headers=ADMIN).json()[0]["usage"] is None
        assert api.get("/api/jobs/1/recovery-candidate", headers=ADMIN).json() == {
            "consumer_integration_ready": False,
            "candidate": None,
        }
        for key in ("execution_token", "result_path", "config_snapshot", "source_result_json"):
            assert key not in first.json()


def test_concurrent_different_keys_create_one_active_batch(
    recovery: tuple[Store, Settings, dict[str, Any]],
) -> None:
    """工件锁与数据库唯一约束共同裁决重复点击，不依赖进程内内存状态。"""

    store, settings, _ = recovery

    def submit(_: int) -> str:
        try:
            enqueue(store, settings, 1, command())
            return "created"
        except RecoveryConflict as error:
            return str(error)

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(submit, range(6)))
    assert results.count("created") == 1
    assert set(results) <= {"created", "active_recovery", "artifacts_busy"}
    assert eligibility(store, settings, 1).reason_code == "active_recovery"
    assert store.retry_job(1) is None


def test_candidate_api_only_returns_summary(
    recovery: tuple[Store, Settings, dict[str, Any]],
) -> None:
    """候选明确不是有效结论，管理员接口也不提前透出完整发现和来源映射。"""

    store, settings, raw = recovery
    enqueue(store, settings, 1, command())
    task = claim(store)
    assert task and finish(store, task, child_result(raw))
    with TestClient(create_app(settings)) as api:
        url = "/api/jobs/1/recovery-candidate"
        assert api.get(url).status_code == 401
        response = api.get(url, headers=ADMIN)
        assert response.status_code == 200
        assert response.json() == {"consumer_integration_ready": True, "candidate": {
            "source_attempt": 1, "revision": 1, "recovery_id": task["id"],
            "terminal_state": "complete", "finding_count": 2,
            "coverage": {"selected": 3, "completed": 3, "reused": 0, "failed": 0,
                         "waived": 0}}}
        assert store.retry_job(1) == 1
        # 全量重审刚排队、attempts 尚未递增时，旧候选也不能冒充当前结论。
        assert api.get(url, headers=ADMIN).json()["candidate"] is None


def test_chain_partial_then_complete_preserves_initial_and_per_batch_usage(
    recovery: tuple[Store, Settings, dict[str, Any]],
) -> None:
    """候选逐版本前进，初审 JSON/发现/通知身份不变，用量不冒充聚合累计。"""

    store, settings, raw = recovery
    with store.connection() as db:
        before = dict(db.execute("SELECT * FROM review_jobs WHERE id=1").fetchone())
        initial_attempt = dict(
            db.execute("SELECT * FROM review_attempts WHERE job_id=1").fetchone()
        )
        delivery = dict(
            db.execute("SELECT * FROM notification_deliveries WHERE job_id=1").fetchone()
        )
    path = Path(before["result_path"])
    original_bytes = path.read_bytes()
    first = enqueue(store, settings, 1, command())
    task = claim(store)
    assert task and task["id"] == first
    assert finish(store, task, child_result(raw, partial=True))
    assert not finish(store, task, child_result(raw))
    candidate = eligibility(store, settings, 1)
    assert candidate.eligible and candidate.source_revision == 1 and candidate.remaining_count == 1
    with pytest.raises(RecoveryConflict, match="source_changed"):
        enqueue(store, settings, 1, command())
    enqueue(store, settings, 1, command(1))
    second = claim(store)
    assert second
    result = child_result(raw, paths=PATHS[2:])
    assert finish(store, second, result)
    assert eligibility(store, settings, 1).reason_code == "nothing_remaining"
    with store.connection() as db:
        rows = db.execute("SELECT * FROM review_recovery_aggregates ORDER BY revision").fetchall()
        assert len(rows) == 2
        merged = json.loads(rows[-1]["result_json"])
        assert merged["schema_version"] == "platform.recovery-candidate/v1"
        assert merged["manifest"]["terminal_state"] == "complete" and merged["usage"] is None
        assert [item["item_id"] for item in merged["manifest"]["coverage"]["completed"]] == [
            "root-0",
            "root-1",
            "root-2",
        ]
        assert [item["content"] for item in merged["comments"]] == [
            "合成初审发现",
            "合成补审发现",
            "合成补审发现",
        ]
        assert len(json.loads(rows[-1]["origins_json"])) == 3
        assert dict(db.execute("SELECT * FROM review_jobs WHERE id=1").fetchone()) == before
        assert (
            dict(db.execute("SELECT * FROM review_attempts WHERE job_id=1").fetchone())
            == initial_attempt
        )
        assert (
            dict(db.execute("SELECT * FROM notification_deliveries WHERE job_id=1").fetchone())
            == delivery
        )
        batches = [
            public_record(dict(row)) for row in db.execute("SELECT * FROM review_recoveries")
        ]
        assert [batch["usage"]["total_tokens"] for batch in batches] == [3, 3]
    assert path.read_bytes() == original_bytes
    assert store.retry_job(1) == 1


@pytest.mark.parametrize("fault", [
    "extra", "missing", "waived", "reused", "finding", "budget", "terminal",
])
def test_child_scope_faults_never_publish_candidate(
    recovery: tuple[Store, Settings, dict[str, Any]],
    fault: str,
) -> None:
    """子集漂移、失败终态、越界发现及预算不确定都不能伪造完整结论。"""

    store, settings, raw = recovery
    enqueue(store, settings, 1, command())
    task = claim(store)
    assert task
    child = child_result(raw)
    coverage = child["manifest"]["coverage"]
    if fault == "extra":
        child = child_result(raw, paths=PATHS)
    elif fault == "missing":
        child = child_result(raw, paths=PATHS[1:2])
    elif fault in {"waived", "reused"}:
        coverage[fault] = [coverage["completed"].pop()]
    elif fault == "finding":
        child["comments"][0]["path"] = "unapproved.py"
    elif fault == "terminal":
        child["manifest"]["terminal_state"] = "failed"
    else:
        child["summary"]["budget_exceeded"] = True
    assert finish(store, task, child)
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM review_recovery_aggregates").fetchone()[0] == 0
        row = dict(db.execute("SELECT * FROM review_recoveries").fetchone())
        assert row["status"] == ("failed" if fault in {"budget", "terminal"} else "stale")
        assert public_record(row)["usage"]["total_tokens"] == 3


def test_budget_failure_and_legacy_stale_explain_coverage_without_rewriting_history(
    recovery: tuple[Store, Settings, dict[str, Any]], client: TestClient,
) -> None:
    """有效预算失败不冒充来源失效；旧状态只读兼容，绝不合并、重试或改变原结论。"""

    store, settings, raw = recovery
    enqueue(store, settings, 1, command())
    task = claim(store)
    assert task
    child = child_result(raw)
    child["comments"] = []
    child["summary"]["budget_exceeded"] = True
    child["manifest"]["terminal_state"] = "failed"
    coverage = child["manifest"]["coverage"]
    coverage["failed"] = [
        item | {"classification": "budget", "reason": "synthetic-private-response"}
        for item in coverage["completed"]]
    coverage["completed"] = []
    before = store.get_job(1)
    assert finish(store, task, child)
    for state in ("failed", "stale"):
        with store.connection() as db:
            if state == "stale":
                db.execute("UPDATE review_recoveries SET status='stale',"
                           "error_code='child_not_usable'")
            persisted = dict(db.execute("SELECT * FROM review_recoveries").fetchone())
            assert persisted["status"] == state
            assert persisted["error_code"] == (
                "child_not_usable" if state == "stale" else "budget_unconfirmed")
            assert db.execute("SELECT COUNT(*) FROM review_recovery_aggregates").fetchone()[0] == 0
        response = client.get("/api/jobs/1/recoveries", headers=ADMIN)
        assert response.status_code == 200
        batch = response.json()[0]
        assert "本批完成 0/2 个文件；触发 Token 预算限制" in batch["failure_summary"]
        assert batch["usage"]["total_tokens"] == 3
        assert "synthetic-private-response" not in response.text
        with store.connection() as db:
            assert dict(db.execute("SELECT * FROM review_recoveries").fetchone()) == persisted
        assert store.get_job(1)["result"] == before["result"]


@pytest.mark.parametrize("snapshot", ["null", "[]", "{}", "invalid", '{"timeout_seconds":true}'])
def test_invalid_source_snapshot_is_explicitly_ineligible(
    recovery: tuple[Store, Settings, dict[str, Any]], snapshot: str,
) -> None:
    """历史快照损坏不抛出协议层 500，不猜测原始预算，也不允许排队。"""

    store, settings, _ = recovery
    with store.connection() as db:
        db.execute("UPDATE review_jobs SET config_snapshot=? WHERE id=1", (snapshot,))
    assert eligibility(store, settings, 1).reason_code == "source_evidence_invalid"
    with pytest.raises(RecoveryConflict, match="source_evidence_invalid"):
        enqueue(store, settings, 1, command())


def test_cancel_and_worker_restart_do_not_automatically_repeat_calls(
    recovery: tuple[Store, Settings, dict[str, Any]],
) -> None:
    """迟到结果与旧执行令牌不复活已取消/中断批次；未知用量保留空值。"""

    store, settings, raw = recovery
    first = enqueue(store, settings, 1, command())
    assert cancel(store, first)
    assert claim(store) is None
    second = enqueue(store, settings, 1, command())
    task = claim(store)
    assert task and task["id"] == second
    assert cancel(store, second)
    assert finish(store, task, child_result(raw))
    third = enqueue(store, settings, 1, command())
    interrupted = claim(store)
    assert interrupted and interrupted["id"] == third
    store.recover()
    assert claim(store) is None
    assert not finish(store, interrupted, child_result(raw))
    with store.connection() as db:
        rows = [public_record(dict(row)) for row in db.execute("SELECT * FROM review_recoveries")]
        assert [row["status"] for row in rows] == ["cancelled", "cancelled", "failed"]
        assert rows[-1]["usage"] is None
        assert db.execute("SELECT COUNT(*) FROM review_recovery_aggregates").fetchone()[0] == 0


def test_active_reference_blocks_prune_but_expired_queue_releases_it(
    recovery: tuple[Store, Settings, dict[str, Any]],
) -> None:
    """有界引用七天后释放；清理不修改 SQLite 结论，过期批次不能回退全量执行。"""

    store, settings, _ = recovery
    with store.connection() as db:
        db.execute("UPDATE review_jobs SET finished_at='2020-01-01 00:00:00'")
        db.execute("UPDATE notification_deliveries SET status='sent'")
    assert eligible_artifacts(store, settings.data_dir, 7)
    enqueue(store, settings, 1, command())
    assert not eligible_artifacts(store, settings.data_dir, 7)
    assert prune_artifacts(store, settings.data_dir, 7)["count"] == 0
    with store.connection() as db:
        db.execute("UPDATE review_recoveries SET created_at='2020-01-01 00:00:00'")
    assert prune_artifacts(store, settings.data_dir, 7)["count"] == 1
    assert claim(store) is None
    assert eligibility(store, settings, 1).reason_code == "source_evidence_missing"


def test_delete_parent_cascades_candidates_and_batches(
    recovery: tuple[Store, Settings, dict[str, Any]],
) -> None:
    """删除项目后迟到 Worker 不恢复孤立任务或结果，原有孤儿工件维护继续负责清理。"""

    store, settings, raw = recovery
    enqueue(store, settings, 1, command())
    task = claim(store)
    assert task
    assert store.delete_repository(1)
    assert not finish(store, task, child_result(raw))
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM review_recoveries").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM orphan_artifacts").fetchone()[0] == 1
