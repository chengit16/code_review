"""验证任务处置摘要、状态分面及详情直达事实一致性；仅使用临时 SQLite 和合成发现。"""

from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient
from ocr_manager.api import create_app
from ocr_manager.config import Settings
from ocr_manager.review_issues import capture_findings
from ocr_manager.review_recovery_store import claim, enqueue
from ocr_manager.storage import Store
from test_review_conclusions import recovered as recovered
from test_review_recovery import ADMIN, command
from test_task_operations import populate


def _result(comments: list[dict[str, Any]], *, partial: bool = False,
            waived: bool = False, excluded: bool = False) -> dict[str, Any]:
    return {"comments": comments, "preview": {"excluded_count": int(excluded), "files": []},
            "manifest": {"terminal_state": "partial" if partial else "complete", "coverage": {
                "selected": ["a.py"], "completed": [] if partial or waived else ["a.py"],
                "reused": [], "failed": ["a.py"] if partial else [],
                "waived": ["a.py"] if waived else []}}}


def _seed(store: Store, job_id: int, comments: list[dict[str, Any]], **options: bool) -> None:
    result = _result(comments, **options)
    with store.connection() as db:
        db.execute("UPDATE review_jobs SET attempts=1,status=?,result_json=? WHERE id=?",
                   (result["manifest"]["terminal_state"], json.dumps(result), job_id))
        job = dict(db.execute("SELECT * FROM review_jobs WHERE id=?", (job_id,)).fetchone())
        capture_findings(db, job, comments)


def test_zero_findings_requires_verified_complete_coverage(
    client: TestClient, settings: Settings,
) -> None:
    """部分覆盖、范围排除、豁免、空历史及排队均不混入未发现问题筛选。"""

    store, _ = populate(client, settings, 7)
    _seed(store, 1, [])
    _seed(store, 2, [], partial=True)
    _seed(store, 3, [], waived=True)
    _seed(store, 4, [], excluded=True)
    with store.connection() as db:
        db.execute("UPDATE review_jobs SET status='complete',result_json=NULL WHERE id=5")
        db.execute("UPDATE review_jobs SET status='failed' WHERE id=6")
    headers = {"X-Admin-Token": settings.admin_token}
    rows = client.get("/api/task-search", headers=headers).json()["items"]
    by_id = {row["id"]: row["issue_summary"] for row in rows}
    assert by_id[1]["no_findings"] is True
    assert all(not by_id[index]["no_findings"] for index in range(2, 8))
    assert not by_id[7]["available"] and not by_id[7]["complete"]
    assert [row["id"] for row in client.get(
        "/api/task-search?issue_state=none", headers=headers).json()["items"]] == [1]
    assert [row["id"] for row in client.get(
        "/api/task-search?issue_state=unknown", headers=headers).json()["items"]] == [5]
    assert client.get("/api/task-search?issue_state=resolved", headers=headers).json()["total"] == 0


def test_counts_deduplicate_problems_and_match_filters_neighbors_and_reopening(
    client: TestClient, settings: Settings,
) -> None:
    """多条发现关联同问题只计一次；全量分面不受分页和当前评审状态影响。"""

    store, repository_id = populate(client, settings, 4)
    comments = [{"path": "a.py", "content": "合成同一问题", "severity": "high"}] * 2
    _seed(store, 1, comments)
    _seed(store, 2, comments)
    _seed(store, 3, [{"path": "b.py", "content": "合成待忽略"}])
    headers = {"X-Admin-Token": settings.admin_token}
    result = client.get("/api/task-search?issue_state=open&status=complete&page_size=1",
                        headers=headers).json()
    assert result["total"] == 3 and len(result["items"]) == 1
    assert result["status_counts"]["total"] == 3
    one = client.get("/api/task-search?mr_iid=1", headers=headers).json()["items"][0]
    assert one["issue_summary"]["finding_count"] == 2
    assert one["issue_summary"]["open_count"] == 1
    detail = client.get("/api/jobs/1", headers=headers).json()
    assert detail["issue_summary"] == one["issue_summary"]
    assert detail["issue_summary"]["highest_severity"] == "high"
    with store.connection() as db:
        db.execute("UPDATE review_issues SET status='fixed' WHERE path='a.py'")
        db.execute("UPDATE review_issues SET status='ignored' WHERE path='b.py'")
    result = client.get("/api/task-search?issue_state=resolved&page_size=1", headers=headers).json()
    assert result["total"] == 3
    assert result["status_counts"]["complete"] == 3
    assert client.get("/api/jobs/2/neighbors?issue_state=resolved", headers=headers).json() == {
        "previous_id": 3, "next_id": 1}
    with store.connection() as db:
        db.execute("UPDATE review_issues SET status='open' WHERE path='a.py'")
    result = client.get("/api/task-search", headers=headers, params={
        "repository_id": repository_id, "issue_state": "open", "status": "failed"}).json()
    assert result["total"] == 0 and result["status_counts"]["total"] == 2
    assert result["status_counts"]["complete"] == 2


def test_missing_occurrence_and_broken_merge_never_count_as_resolved(
    client: TestClient, settings: Settings,
) -> None:
    """原始结果仍有发现而关联缺失时保守显示未知，合并循环有界且不误报修复。"""

    store, _ = populate(client, settings, 3)
    for index in range(1, 4):
        _seed(store, index, [{"path": f"{index}.py", "content": "合成问题"}])
    with store.connection() as db:
        db.execute("DELETE FROM review_issue_occurrences WHERE job_id=1")
        db.execute("UPDATE review_issues SET status='merged',merged_into_id=3 WHERE id=2")
        db.execute("UPDATE review_issues SET status='merged',merged_into_id=2 WHERE id=3")
    headers = {"X-Admin-Token": settings.admin_token}
    result = client.get("/api/task-search?issue_state=unknown", headers=headers).json()
    assert result["total"] == 3
    assert all(row["issue_summary"]["unknown_count"] == 1 for row in result["items"])
    assert client.get("/api/task-search?issue_state=resolved", headers=headers).json()["total"] == 0
    with store.connection() as db:
        db.execute("UPDATE review_issues SET status='open',merged_into_id=NULL WHERE id=3")
    result = client.get("/api/task-search?issue_state=open", headers=headers).json()
    assert result["total"] == 2
    detail = client.get("/api/jobs/2", headers=headers).json()
    assert detail["resolved_finding_issues"]["j2:a1:c0"] == {"id": 3, "status": "open"}


def test_effective_recovery_and_rerun_share_one_current_identity_set(
    recovered: tuple[Store, Settings, dict[str, Any]],
) -> None:
    """有效补审三条发现进入摘要；全量重审刚排队即隐藏旧问题，不能统计为全部已处置。"""

    store, settings, _ = recovered
    with TestClient(create_app(settings)) as api:
        row = api.get("/api/task-search", headers=ADMIN).json()["items"][0]
        assert row["issue_summary"]["finding_count"] == 3
        assert row["issue_summary"]["open_count"] == 3
        assert row["list_status"] == "complete"
        assert store.retry_job(1) == 1
        row = api.get("/api/task-search", headers=ADMIN).json()["items"][0]
        assert row["list_status"] == "queued"
        assert not row["issue_summary"]["available"]
        assert row["issue_summary"]["open_count"] == 0
        assert api.get("/api/task-search?issue_state=resolved", headers=ADMIN).json()["total"] == 0


def test_active_recovery_status_matches_navigation_and_facet_counts(
    client: TestClient, settings: Settings,
) -> None:
    """排队补审仍是排队，真正领取才进入运行；有效结论另保留而不覆盖初审。"""

    from test_review_recovery import make_source

    store, settings, _ = make_source(client, settings)
    enqueue(store, settings, 1, command())
    with TestClient(create_app(settings)) as api:
        page = api.get("/api/task-search?status=queued", headers=ADMIN).json()
        assert page["total"] == 1 and page["status_counts"]["queued"] == 1
        assert page["items"][0]["active_recovery_status"] == "queued"
        assert claim(store)
        page = api.get("/api/task-search?status=running", headers=ADMIN).json()
        assert page["total"] == 1 and page["status_counts"]["running"] == 1
        assert page["items"][0]["list_status"] == "running"


def test_notification_filter_combines_with_issue_state_and_preserves_facets(
    client: TestClient, settings: Settings,
) -> None:
    """飞书失败作为独立条件，可组合已完成与待处理；分面不能丢失通知条件。"""

    store, _ = populate(client, settings, 3)
    for index in range(1, 4):
        _seed(store, index, [{"path": f"{index}.py", "content": "合成通知问题"}])
    with store.connection() as db:
        db.execute("INSERT INTO notification_deliveries(job_id,status) VALUES(1,'failed')")
        db.execute("INSERT INTO notification_deliveries(job_id,status) VALUES(2,'sent')")
        db.execute("UPDATE review_jobs SET status='partial' WHERE id=3")
        db.execute("INSERT INTO notification_deliveries(job_id,status) VALUES(3,'failed')")
    headers = {"X-Admin-Token": settings.admin_token}
    query = "notification_failed=true&issue_state=open&status=complete&page_size=1"
    result = client.get(f"/api/task-search?{query}", headers=headers).json()
    assert result["total"] == 1 and result["items"][0]["id"] == 1
    assert result["status_counts"]["total"] == 2
    assert result["status_counts"]["complete"] == result["status_counts"]["partial"] == 1
    assert client.get(f"/api/jobs/2/neighbors?{query}", headers=headers).json() == {
        "previous_id": None, "next_id": 1}
    legacy = client.get("/api/task-search?view=notification_failed&issue_state=open",
                        headers=headers).json()
    assert [row["id"] for row in legacy["items"]] == [3, 1]


def test_supplement_notification_failure_is_filterable_after_effective_completion(
    recovered: tuple[Store, Settings, dict[str, Any]],
) -> None:
    """补审结论已完成但补充投递失败时，不把评审误归失败，也不丢失通知告警。"""

    store, settings, _ = recovered
    with store.connection() as db:
        db.execute("UPDATE review_recovery_deliveries SET status='failed' WHERE revision=2")
    with TestClient(create_app(settings)) as api:
        page = api.get("/api/task-search?notification_failed=true&status=complete&issue_state=open",
                       headers=ADMIN).json()
        assert page["total"] == page["status_counts"]["complete"] == 1
        assert page["items"][0]["recovery_delivery_failed_count"] == 1
        assert page["items"][0]["list_status"] == "complete"
