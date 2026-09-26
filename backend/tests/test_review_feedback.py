"""验证人工反馈、通知阈值与任务快照的边界，不访问外部服务。"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from ocr_manager.config import Settings
from ocr_manager.feishu import build_review_card
from ocr_manager.storage import SCHEMA_VERSION, Store
from ocr_manager.worker import config_hash

ADMIN = {"X-Admin-Token": "test-admin-token"}
SHA = "a" * 40


def add_repository(store: Store) -> int:
    """建立纯本地项目记录，反馈测试只依赖持久化业务事实。"""

    return store.add_repository(
        {
            "name": "示例项目",
            "gitlab_url": "https://gitlab.example.test",
            "project_id": 42,
            "remote_url": "git@gitlab.example.test:team/app.git",
            "target_branch": "main",
            "auth_kind": "secret",
            "webhook_secret": "ciphertext",
            "feishu_webhook": "",
        }
    )


def finished_job(store: Store, repository_id: int) -> int:
    """建立一条含两条发现的终态任务，供反馈和重审验证。"""

    assert store.add_event(repository_id, 7, "delivery-1", SHA, None)
    event = store.next_event()
    assert event is not None
    store.finish_event(event["id"], [SHA], {SHA: ("old-snapshot", "")}, None)
    job = store.next_job()
    assert job is not None
    store.finish_job(
        job["id"],
        "complete",
        None,
        {
            "comments": [
                {"path": "app.py", "severity": "high", "content": "输入错误"},
                {"path": "app.py", "severity": "low", "content": "命名问题"},
            ],
            "manifest": {
                "coverage": {
                    "selected": [1],
                    "completed": [1],
                    "reused": [],
                    "failed": [],
                    "waived": [],
                }
            },
        },
        None,
    )
    return int(job["id"])


def test_feedback_api_validates_index_and_aggregates(
    client: TestClient,
    settings: Settings,
) -> None:
    """管理鉴权与真实评论索引约束防止伪造反馈统计。"""

    store = Store(settings.data_dir / "app.db")
    repository_id = add_repository(store)
    job_id = finished_job(store, repository_id)
    url = f"/api/jobs/{job_id}/feedback/1"
    assert client.put(url, json={"verdict": "false_positive"}).status_code == 401
    assert client.put(url, headers=ADMIN, json={"verdict": "false_positive"}).status_code == 200
    assert client.put(url, headers=ADMIN, json={"verdict": "fixed"}).status_code == 200
    assert (
        client.put(
            f"/api/jobs/{job_id}/feedback/2", headers=ADMIN, json={"verdict": "helpful"}
        ).status_code
        == 409
    )
    assert (
        client.put(
            f"/api/jobs/{job_id}/feedback/-1", headers=ADMIN, json={"verdict": "helpful"}
        ).status_code
        == 409
    )
    assert client.put(url, headers=ADMIN, json={"verdict": "invalid"}).status_code == 422
    detail = client.get(f"/api/jobs/{job_id}", headers=ADMIN).json()
    assert detail["feedback"] == {"1": "fixed"}
    summary = client.get("/api/review-feedback/summary", headers=ADMIN).json()
    assert summary[0]["repository_id"] == repository_id
    assert (summary[0]["total"], summary[0]["fixed"], summary[0]["false_positive"]) == (1, 1, 0)
    assert client.delete(url, headers=ADMIN).status_code == 200
    assert client.delete(url, headers=ADMIN).status_code == 404
    assert client.get("/api/review-feedback/summary", headers=ADMIN).json()[0]["total"] == 0


def test_policy_protects_pending_work_and_retries_clear_feedback(
    client: TestClient,
    settings: Settings,
) -> None:
    """阈值变更进入新快照；旧任务重审不沿用已失效的人工反馈。"""

    store = Store(settings.data_dir / "app.db")
    repository_id = add_repository(store)
    endpoint = f"/api/repositories/{repository_id}/notification-policy"
    original = config_hash(store, settings, repository_id=repository_id)
    assert client.put(endpoint, headers=ADMIN, json={"minimum_severity": "high"}).status_code == 200
    assert config_hash(store, settings, repository_id=repository_id) != original
    assert store.get_project_policy(repository_id) == "high"
    assert store.add_event(repository_id, 7, "delivery-1", SHA, None)
    assert client.put(endpoint, headers=ADMIN, json={"minimum_severity": "low"}).status_code == 409
    event = store.next_event()
    assert event is not None
    store.finish_event(event["id"], [SHA], {SHA: ("old-snapshot", "")}, None)
    assert client.put(endpoint, headers=ADMIN, json={"minimum_severity": "low"}).status_code == 409
    job = store.next_job()
    assert job is not None and job["notification_min_severity"] == "high"
    store.finish_job(
        job["id"],
        "complete",
        None,
        {
            "comments": [
                {"path": "app.py", "content": "问题", "severity": "high"},
            ]
        },
        None,
    )
    store.set_review_feedback(job["id"], 0, "helpful")
    assert store.retry_job(job["id"]) == job["id"]
    retried_detail = store.get_job(job["id"])
    assert retried_detail is not None and retried_detail["feedback"] == {}
    assert client.put(endpoint, headers=ADMIN, json={"minimum_severity": "low"}).status_code == 409
    retried = store.next_job()
    assert retried is not None
    store.finish_job(job["id"], "complete", None, {"comments": []}, None)
    assert client.put(endpoint, headers=ADMIN, json={"minimum_severity": "low"}).status_code == 200
    new_id = store.retry_job(job["id"], "new-snapshot")
    assert new_id is not None and new_id != job["id"]
    new_detail = store.get_job(new_id)
    assert new_detail is not None and new_detail["notification_min_severity"] == "low"
    assert store.delete_repository(repository_id)
    assert store.feedback_summary() == []


def test_card_threshold_preserves_full_review_conclusion() -> None:
    """提高群消息重点阈值时仍展示低危发现数量与需处理结论。"""

    card = build_review_card(
        {
            "repository_name": "示例项目",
            "target_branch": "main",
            "mr_iid": 7,
            "commit_sha": SHA,
            "job_id": 1,
            "review_status": "complete",
            "notification_min_severity": "critical",
            "result_json": {
                "comments": [
                    {"path": "low.py", "content": "低危细节", "severity": "low"},
                ],
                "manifest": {
                    "coverage": {
                        "selected": [1],
                        "completed": [1],
                        "reused": [],
                        "failed": [],
                        "waived": [],
                    }
                },
            },
        }
    )
    elements = str(card["card"]["elements"])
    assert card["card"]["header"]["template"] == "orange"
    assert "低危 1" in card["card"]["header"]["title"]["content"]
    assert "发现 1 条问题" in elements
    assert "低危细节" not in elements


def test_feedback_migration_from_existing_database(tmp_path: Path) -> None:
    """已有 17 版数据库升级后保留项目与任务，并补齐新表和默认阈值。"""

    store = Store(tmp_path / "app.db")
    store.migrate()
    repository_id = add_repository(store)
    with store.connection() as db:
        db.execute("DROP TABLE review_feedback")
        db.execute("DROP TABLE project_policies")
        db.execute("ALTER TABLE review_jobs DROP COLUMN notification_min_severity")
        db.execute("PRAGMA user_version=17")
    store.migrate()
    assert store.get_repository(repository_id) is not None
    assert store.get_project_policy(repository_id) == "medium"
    with store.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
