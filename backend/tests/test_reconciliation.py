"""验证对账只报告数据库与工件差异，且诊断包不包含评审正文。"""

from pathlib import Path

from fastapi.testclient import TestClient
from ocr_manager.api import create_app
from ocr_manager.config import Settings
from ocr_manager.reconciliation import reconcile
from ocr_manager.storage import Store


def test_reconcile_detects_orphan_artifact_and_missing_result(tmp_path: Path) -> None:
    """差异清单保留可定位 ID，但不自动删除孤儿目录。"""

    store = Store(tmp_path / "app.db")
    store.migrate()
    repository_id = store.add_repository({
        "name": "合成项目", "gitlab_url": "https://gitlab.example.test",
        "project_id": 51, "remote_url": "https://gitlab.example.test/team/repo.git",
        "target_branch": "main", "auth_kind": "secret", "webhook_secret": "cipher",
        "feishu_webhook": "",
    })
    assert store.add_event(repository_id, 7, None, "a" * 40, None)
    event = store.next_event()
    assert event is not None
    store.finish_event(event["id"], ["a" * 40], {"a" * 40: ("snapshot", "")}, None)
    job = store.list_jobs()[0]
    with store.connection() as db:
        db.execute(
            "UPDATE review_jobs SET status='complete', result_path=? WHERE id=?",
            (str(tmp_path / "runs" / str(job["id"]) / "1" / "result.json"), job["id"]),
        )
    run = tmp_path / "runs" / str(job["id"])
    run.mkdir(parents=True)
    orphan = tmp_path / "runs" / "99999"
    orphan.mkdir()

    result = reconcile(store, tmp_path)
    codes = {issue["code"] for issue in result["issues"]}
    assert "result_artifact_missing" in codes
    assert "artifact_without_job" in codes
    assert orphan.is_dir()


def test_diagnostic_export_is_redacted_and_carries_request_id(settings: Settings) -> None:
    """诊断包只包含安全投影，HTTP 响应给出关联请求 ID。"""

    with TestClient(create_app(settings)) as client:
        response = client.get(
            "/api/diagnostics/export", headers={"X-Admin-Token": settings.admin_token},
        )

    assert response.status_code == 200
    assert response.headers.get("x-request-id")
    text = response.text
    assert "OCR_APP_MASTER_KEY" not in text
    assert "api_key" not in text
    assert '"thinking"' not in text
    assert '"schema_version"' in text


def test_mutation_request_id_is_saved_in_management_audit(settings: Settings) -> None:
    """管理 API 返回的请求 ID 与脱敏审计元数据可相互检索。"""

    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/maintenance/prune?days=90",
            headers={"X-Admin-Token": settings.admin_token},
        )
        bundle = client.get(
            "/api/diagnostics/export", headers={"X-Admin-Token": settings.admin_token},
        ).json()

    assert response.status_code == 200
    request_id = response.headers["x-request-id"]
    assert any(item["correlation_id"] == request_id for item in bundle["management_requests"])


def test_correlation_id_spans_event_job_attempt_and_delivery(tmp_path: Path) -> None:
    """同一事件产生的任务、尝试和通知继承事件关联 ID。"""

    store = Store(tmp_path / "app.db")
    store.migrate()
    repository_id = store.add_repository({
        "name": "合成项目", "gitlab_url": "https://gitlab.example.test",
        "project_id": 52, "remote_url": "https://gitlab.example.test/team/repo.git",
        "target_branch": "main", "auth_kind": "secret", "webhook_secret": "cipher",
        "feishu_webhook": "",
    })
    assert store.add_event(repository_id, 8, None, "b" * 40, None, "request-correlation")
    event = store.next_event()
    assert event is not None
    store.finish_event(event["id"], ["b" * 40], {"b" * 40: ("snapshot", "")}, None)
    job = store.list_jobs()[0]
    store.finish_job(job["id"], "skipped", None, None, None)
    with store.connection() as db:
        correlations = [row[0] for row in db.execute(
            """SELECT correlation_id FROM merge_events WHERE id=?
            UNION ALL SELECT correlation_id FROM review_jobs WHERE id=?
            UNION ALL SELECT correlation_id FROM review_attempts WHERE job_id=?
            UNION ALL SELECT correlation_id FROM notification_deliveries WHERE job_id=?""",
            (event["id"], job["id"], job["id"], job["id"]),
        )]
    assert correlations == ["request-correlation"] * 4
