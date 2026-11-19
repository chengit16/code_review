"""通过管理 API 验证留档、并发冲突、权限、入队幂等与历史清理。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from agent_comparison_fixture import finish_comparison, seed_task
from fastapi.testclient import TestClient
from ocr_manager.agent_review_config import AgentReviewConfig
from ocr_manager.api import create_app
from ocr_manager.config import Settings
from ocr_manager.review_history_cleanup import apply_cleanup, plan_cleanup
from ocr_manager.storage import SCHEMA_VERSION, Store
from test_auth import ADMIN, create_user, enable_users, login

PATH = "/api/jobs/1/agent-comparisons"
DRAFT = {"evaluations": [{"finding_id": "agent:1", "verdict": "valid", "worth_fixing": True,
                          "note": "核对了固定版本证据"}]}


def comparison_app(settings: Settings) -> tuple[TestClient, Store]:
    """独立试点、固定试点仓库和不可用于外部系统的凭据。"""

    config = AgentReviewConfig("http://127.0.0.1:1/v1/chat/completions", "fixture-agent",
                               frozenset({1}), "fixture-key")
    app = create_app(replace(settings, agent_review=config))
    store = Store(settings.data_dir / "app.db")
    assert seed_task(store, settings.data_dir) == 1
    return TestClient(app), store


def submit(client: TestClient, key: str, previous: int | None = None, attempt: int = 1) -> int:
    """经实际管理路由登记提交，不执行模型调用。"""

    response = client.post(PATH, headers=ADMIN, json={"request_key": key,
        "previous_id": previous, "source_attempt": attempt})
    assert response.status_code == 202, response.text
    return int(response.json()["id"])


def test_agent_history_is_frozen_and_rerun_has_no_ocr_side_effect(settings: Settings) -> None:
    """保护旧 OCR 尝试、固定范围、前驱约束，并确保不创建通知或评审副本。"""

    client, store = comparison_app(settings)
    with client:
        assert client.get(PATH).status_code == 401
        old_job = client.get("/api/jobs/2/agent-comparisons", headers=ADMIN).json()
        assert old_job["items"] == [] and "固定提交范围" in old_job["unavailable_reason"]
        initial = client.get(PATH, headers=ADMIN).json()
        assert initial["items"] == [] and initial["unavailable_reason"] is None
        assert client.post(PATH, headers=ADMIN, json={"request_key": "stale", "previous_id": None,
            "source_attempt": 2}).status_code == 409
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(submit, client, "same") for _ in range(2)]
        assert {future.result() for future in futures} == {1}
        path = f"{PATH}/1"
        assert client.get("/api/jobs/2/agent-comparisons/1", headers=ADMIN).status_code == 404
        queued = client.get(PATH, headers=ADMIN).json()
        assert queued["active_id"] == 1
        assert client.put(f"{path}/curation", headers=ADMIN, json={"expected_version": 0,
            "document": DRAFT}).json()["detail"]["code"] == "comparison_running"
        finish_comparison(store, settings.data_dir, 1)
        detail = client.get(path, headers=ADMIN)
        assert detail.status_code == 200, detail.text
        assert detail.headers["cache-control"] == "no-store"
        first = detail.json()
        assert first["ocr"]["coverage"]["completed"] == 1
        assert first["agent"]["files"][0]["reviewed"] == 25
        assert first["agent"]["usage"]["input_tokens"] == 40
        assert first["suggestions"][0]["agent_ids"] == ["agent:0"]
        hidden = ("fixture-key", "chat/completions", "model_snapshot", "progress_json")
        assert all(value not in detail.text for value in hidden)
        changed = client.post(PATH, headers=ADMIN, json={"request_key": "same", "previous_id": None,
            "source_attempt": 2})
        assert changed.status_code == 409
        assert changed.json()["detail"]["code"] == "request_key_mismatch"
        stale_predecessor = {"request_key": "stale-id", "previous_id": None, "source_attempt": 1}
        assert client.post(PATH, headers=ADMIN, json=stale_predecessor).status_code == 409
        new_id = submit(client, "rerun", previous=1)
        assert new_id == 2
        assert client.get(f"{PATH}/2", headers=ADMIN).json()["ocr"] == first["ocr"]
        page = client.get(PATH, headers=ADMIN, params={"limit": 1}).json()
        assert page["next_before_id"] == 2 and page["items"][0]["id"] == 2
        older = client.get(PATH, headers=ADMIN, params={"before_id": 2}).json()
        assert older["items"][0]["id"] == 1 and older["next_before_id"] is None
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM agent_reviews").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM review_attempts").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM notification_deliveries").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM gitlab_publications").fetchone()[0] == 0


def test_readers_and_conflicting_curation_are_isolated_from_history(settings: Settings) -> None:
    """读者不得修改；并发写入只接受一个起始版本，旧裁定和版本仍可读。"""

    client, store = comparison_app(settings)
    with client:
        assert submit(client, "view") == 1
        finish_comparison(store, settings.data_dir, 1)
        create_user(client, "alice", "admin")
        create_user(client, "reader", "reader")
        enable_users(client)
        editor = {"Authorization": f"Bearer {login(client, 'alice')['token']}"}
        reader = {"Authorization": f"Bearer {login(client, 'reader')['token']}"}
        path = f"{PATH}/1"
        update = f"{path}/curation"
        assert client.get(path, headers=reader).status_code == 200
        assert client.put(update, headers=reader, json={"expected_version": 0,
            "document": DRAFT}).status_code == 403
        assert client.post(PATH, headers=reader, json={}).status_code == 403
        invalid = client.put(update, headers=editor, json={"expected_version": 0, "document": {
            "evaluations": [{"finding_id": "agent:404", "verdict": "valid"}],
        }})
        assert invalid.status_code == 409
        assert invalid.json()["detail"]["code"] == "invalid_evaluation"
        draft = DRAFT | {
            "matches": [{"id": "match:review", "label": "重复订单",
                         "ocr_ids": ["ocr:0"], "agent_ids": ["agent:0"]}],
            "missed": [{"id": "missed:test", "path": "orders.py", "line": 9, "title": "共同漏报"}],
        }
        with ThreadPoolExecutor(max_workers=2) as pool:
            writes = [pool.submit(client.put, update, headers=editor, json={"expected_version": 0,
                "document": draft}) for _ in range(2)]
        assert sorted(write.result().status_code for write in writes) == [200, 409]
        v1 = client.get(path, headers=reader).json()["curation"]
        assert v1["version"] == 1 and v1["actor"] == "alice"
        assert v1["document"]["missed"][0]["title"] == "共同漏报"
        assert client.put(update, headers=editor, json={"expected_version": 1,
            "document": DRAFT}).json()["version"] == 2
        old = client.get(path, headers=reader, params={"curation_version": 1}).json()
        assert old["curation"] == v1
        assert client.get(path, headers=reader, params={"curation_version": 3}).status_code == 404
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM review_finding_feedback").fetchone()[0] == 0


def test_migration_keeps_v55_comparisons_and_cleanup_cascades_curation(settings: Settings) -> None:
    """在有 Agent 历史的 v55 副本上迁移，裁定只随对应任务清理。"""

    client, store = comparison_app(settings)
    with client:
        assert submit(client, "migration") == 1
        finish_comparison(store, settings.data_dir, 1)
        with store.connection() as db:
            db.execute("DROP TABLE agent_comparison_curations")
            db.execute("DROP INDEX idx_agent_reviews_job_history")
            db.execute("PRAGMA user_version=55")
        store.migrate()
        assert client.get(f"{PATH}/1", headers=ADMIN).status_code == 200
        assert client.put(f"{PATH}/1/curation", headers=ADMIN, json={"expected_version": 0,
            "document": DRAFT}).status_code == 200
    with store.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        db.execute("UPDATE review_jobs SET created_at='2024-01-01 00:00:00' WHERE id=1")
        db.execute("UPDATE review_issue_backfill SET completed=1")
    with store.connection() as db:
        plan = plan_cleanup(db, "2025-01-01 00:00:00")
        assert plan.job_ids == (1,)
        apply_cleanup(db, plan)
        assert db.execute("SELECT COUNT(*) FROM agent_comparison_curations").fetchone()[0] == 0
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
