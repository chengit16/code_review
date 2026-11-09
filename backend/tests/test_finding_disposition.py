"""验证跟进问题独立处置不改价值反馈或覆盖并发决定；仅使用临时 SQLite。"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from ocr_manager.api import create_app
from ocr_manager.config import Settings
from ocr_manager.storage import Store
from test_review_conclusions import recovered as recovered
from test_review_issues import ADMIN, create_repository, finish_with_finding


@pytest.mark.parametrize("verdict", [None, "helpful", "false_positive", "ignored", "fixed"])
def test_independent_ignore_and_restore_preserve_feedback(
    client: TestClient, settings: Settings, verdict: str | None,
) -> None:
    """单项显式处置前后，旧反馈与稳定身份镜像保持一致，忽略绝不计为新误报。"""

    repository_id = create_repository(client)
    store = Store(settings.data_dir / "app.db")
    first = finish_with_finding(store, repository_id, 7, "a" * 40)
    second = finish_with_finding(store, repository_id, 8, "b" * 40)
    job_url = f"/api/jobs/{first}"
    initial = client.get(job_url, headers=ADMIN).json()
    issue_id = initial["issue_ids"]["0"]
    if verdict == "fixed":
        with store.connection() as db:
            db.execute("INSERT INTO review_feedback(job_id,comment_index,verdict) "
                       "VALUES(?,0,'fixed')", (first,))
    elif verdict:
        assert client.put(f"{job_url}/feedback/0", headers=ADMIN,
                          json={"verdict": verdict}).status_code == 200
    before = client.get(job_url, headers=ADMIN).json()
    with store.connection() as db:
        stable_feedback = [tuple(row) for row in db.execute(
            "SELECT * FROM review_finding_feedback ORDER BY finding_id")]
    summary = client.get("/api/review-feedback/summary", headers=ADMIN).json()
    expected = before["issue_statuses"]["0"]
    for status in ("false_positive", "ignored", "fixed", "open"):
        payload = {"targets": [{"id": issue_id, "expected_status": expected}],
                   "status": status, "note": "独立处置合成说明，不修改反馈"}
        result = client.post("/api/review-issues/batch-update", headers=ADMIN, json=payload)
        assert result.status_code == 200
        after = client.get(job_url, headers=ADMIN).json()
        assert after["feedback"] == before["feedback"]
        with store.connection() as db:
            assert [tuple(row) for row in db.execute(
                "SELECT * FROM review_finding_feedback ORDER BY finding_id")] == stable_feedback
        assert after["issue_statuses"]["0"] == status
        assert client.get(f"/api/jobs/{second}", headers=ADMIN).json()[
            "issue_statuses"]["0"] == status
        assert client.get("/api/review-feedback/summary", headers=ADMIN).json() == summary
        events = client.get(f"/api/review-issues/{issue_id}", headers=ADMIN).json()["events"]
        repeated = client.post("/api/review-issues/batch-update", headers=ADMIN, json=payload)
        assert repeated.json()["updated"] == 0
        assert client.get(f"/api/review-issues/{issue_id}", headers=ADMIN).json()[
            "events"] == events
        expected = status


def test_independent_ignore_rejects_stale_state_without_changing_feedback(
    client: TestClient, settings: Settings,
) -> None:
    """确认期间他人标记已修复时，旧 open 快照不能静默覆盖为 ignored。"""

    repository_id = create_repository(client)
    store = Store(settings.data_dir / "app.db")
    job_id = finish_with_finding(store, repository_id, 7, "a" * 40)
    url = f"/api/jobs/{job_id}"
    issue_id = client.get(url, headers=ADMIN).json()["issue_ids"]["0"]
    assert client.post(f"/api/review-issues/{issue_id}", headers=ADMIN,
                       json={"status": "fixed"}).status_code == 200
    result = client.post("/api/review-issues/batch-update", headers=ADMIN, json={
        "targets": [{"id": issue_id, "expected_status": "open"}], "status": "ignored"})
    assert result.status_code == 409
    after = client.get(url, headers=ADMIN).json()
    assert after["issue_statuses"] == {"0": "fixed"}
    assert after["feedback"] == {}
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM review_finding_feedback").fetchone()[0] == 0


@pytest.mark.parametrize("verdict", [None, "helpful", "false_positive"])
def test_recovery_disposition_preserves_stable_feedback_and_quality(
    recovered: tuple[Store, Settings, dict[str, Any]], verdict: str | None,
) -> None:
    """有效结论的补审身份不落入初审索引，独立处置也不影响同集合质量计数。"""

    _, settings, _ = recovered
    identifier = "j1:a1:r1:c0"
    with TestClient(create_app(settings)) as api:
        if verdict:
            response = api.put(f"/api/jobs/1/finding-feedback/{identifier}", headers=ADMIN,
                               json={"source_attempt": 1, "revision": 2, "verdict": verdict})
            assert response.status_code == 200
        before = api.get("/api/jobs/1", headers=ADMIN).json()
        target = before["resolved_finding_issues"][identifier]
        quality = api.get("/api/review-effectiveness?days=7", headers=ADMIN).json()["quality"]
        for status in ("false_positive", "ignored", "fixed", "open"):
            response = api.post("/api/review-issues/batch-update", headers=ADMIN, json={
                "targets": [{"id": target["id"], "expected_status": target["status"]}],
                "status": status, "note": "补审发现独立处置合成验收"})
            assert response.status_code == 200
            after = api.get("/api/jobs/1", headers=ADMIN).json()
            assert after["feedback"] == before["feedback"] == {}
            assert after["finding_feedback"] == before["finding_feedback"]
            assert after["resolved_finding_issues"][identifier]["status"] == status
            after_quality = api.get(
                "/api/review-effectiveness?days=7", headers=ADMIN).json()["quality"]
            actual = {key: value for key, value in after_quality.items()
                      if key != "dispositions"}
            expected = {
                key: value for key, value in quality.items()
                if key != "dispositions"}
            assert actual == expected
            target = after["resolved_finding_issues"][identifier]
