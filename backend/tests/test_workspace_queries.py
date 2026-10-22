"""验证工作台的全量统计、最新版本、问题搜索及当前尝试摘要，不访问外部服务。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from ocr_manager.config import Settings
from ocr_manager.premerge import enqueue_premerge
from ocr_manager.storage import Store
from test_auth import create_user, enable_users, login
from test_review_issues import create_repository, finish_with_finding
from test_task_operations import populate

ADMIN = {"X-Admin-Token": "test-admin-token"}


def test_overview_counts_entire_history_and_matches_views(
    client: TestClient, settings: Settings,
) -> None:
    """二百条之外仍计入总量，历史失败与同输入已恢复异常分开统计。"""

    store, _ = populate(client, settings, 251)
    with store.connection() as db:
        db.execute("UPDATE review_jobs SET status='failed' WHERE id IN (1,2,3)")
        db.execute("UPDATE review_jobs SET status='partial' WHERE id=4")
        db.execute("""UPDATE review_jobs SET status='complete',mr_iid=1,config_hash='new-config',
                   commit_sha=(SELECT commit_sha FROM review_jobs WHERE id=1) WHERE id=251""")
        db.execute("UPDATE review_jobs SET status='running' WHERE id=250")
        db.execute("INSERT INTO notification_deliveries(job_id,status) VALUES(251,'failed')")
    result = client.get("/api/overview", headers=ADMIN).json()
    assert result["summary"] == {"repositories": 1, "total": 251, "queued": 245,
                                 "running": 1, "complete": 1, "historical_failed": 3,
                                 "attention": 3, "notification_failed": 1}
    assert len(result["recent"]) == 8
    for view, count in (("attention", 3), ("active", 246), ("notification_failed", 1)):
        listing = client.get("/api/task-search", headers=ADMIN, params={"view": view}).json()
        assert listing["total"] == count
    assert client.get("/api/jobs/3/neighbors?view=attention", headers=ADMIN).json() == {
        "previous_id": 4, "next_id": 2}
    # 相同 SHA 但基线不同不是恢复，也不能把其他 MR 的完整结果作为恢复依据。
    with store.connection() as db:
        db.execute("UPDATE review_jobs SET base_sha=? WHERE id=251", ("b" * 40,))
    assert client.get("/api/overview", headers=ADMIN).json()["summary"]["attention"] == 4


def test_task_summary_uses_current_attempt_and_independent_delivery(
    client: TestClient, settings: Settings,
) -> None:
    """重审未完成时不会沿用旧发现数量，通知失败也不改写评审状态。"""

    repository_id = create_repository(client)
    store = Store(settings.data_dir / "app.db")
    job_id = finish_with_finding(store, repository_id, 1, "a" * 40)
    first = client.get("/api/task-search", headers=ADMIN).json()["items"][0]
    assert (first["finding_count"], first["highest_severity"]) == (1, "high")
    with store.connection() as db:
        db.execute("UPDATE review_jobs SET attempts=2 WHERE id=?", (job_id,))
        db.execute("UPDATE notification_deliveries SET status='failed' WHERE job_id=?", (job_id,))
    second = client.get("/api/task-search", headers=ADMIN).json()["items"][0]
    assert (second["finding_count"], second["highest_severity"]) == (0, None)
    assert second["status"] == "complete" and second["delivery_status"] == "failed"


def test_issue_search_is_literal_and_combines_filters(
    client: TestClient, settings: Settings,
) -> None:
    """描述、路径和编号可搜索；SQL 通配符与引号不获得特殊含义。"""

    repository_id = create_repository(client)
    store = Store(settings.data_dir / "app.db")
    finish_with_finding(store, repository_id, 1, "a" * 40, content="输入包含 20%_ ' 仍需校验")
    finish_with_finding(store, repository_id, 2, "b" * 40, content="另一条发现")
    for q, count in (("20%_ '", 1), ("SRC/APP", 2), ("1", 1), ("   ", 2), ("' OR 1=1", 0)):
        result = client.get("/api/review-issues", headers=ADMIN,
                            params={"q": q, "repository_id": repository_id}).json()
        assert result["total"] == count
    assert client.get("/api/review-issues", headers=ADMIN, params={
        "q": "输入", "severity": "low"}).json()["total"] == 0
    assert client.get("/api/review-issues?q=" + "x" * 201, headers=ADMIN).status_code == 422


def test_premerge_latest_is_chosen_before_status_filter_and_paginated(
    client: TestClient, settings: Settings,
) -> None:
    """默认只展示每个 MR 最新接收版本，旧成功不会冒充当前成功，历史可单独翻页。"""

    repository_id = create_repository(client)
    store = Store(settings.data_dir / "app.db")
    assert client.put(f"/api/repositories/{repository_id}/premerge", headers=ADMIN,
                      json={"enabled": True}).status_code == 200
    for index in range(102):
        enqueue_premerge(store, repository_id, 7, f"{index:040x}", None)
    with store.connection() as db:
        db.execute("UPDATE premerge_reviews SET status='complete' WHERE id=1")
    latest = client.get("/api/premerge-search", headers=ADMIN).json()
    assert latest["total"] == 1 and latest["items"][0]["id"] == 102
    assert client.get("/api/premerge-search?status=complete", headers=ADMIN).json()["total"] == 0
    older = client.get("/api/premerge-search", headers=ADMIN, params={
        "latest_only": False, "page": 5, "page_size": 25}).json()
    assert older["total"] == 102 and [item["id"] for item in older["items"]] == [2, 1]
    assert client.get("/api/premerge-search?latest_only=false&status=complete",
                      headers=ADMIN).json()["total"] == 1
    assert client.get("/api/premerge-search?mr_iid=8", headers=ADMIN).json()["total"] == 0


@pytest.mark.parametrize("path", ["/api/overview", "/api/premerge-search"])
def test_workspace_queries_require_auth(client: TestClient, path: str) -> None:
    """聚合和版本检索与原管理接口使用同样的认证边界。"""

    assert client.get(path).status_code == 401


def test_reader_can_read_new_views_but_cannot_retry(client: TestClient) -> None:
    """新只读视图不缩减原只读权限，新增界面也不能绕过写操作授权。"""

    create_user(client, "workspace-admin", "admin")
    create_user(client, "workspace-reader", "reader")
    enable_users(client)
    session = login(client, "workspace-reader")
    headers = {"Authorization": f"Bearer {session['token']}"}
    for path in ("/api/overview", "/api/premerge-search", "/api/task-search?view=attention",
                 "/api/review-issues?q=权限"):
        assert client.get(path, headers=headers).status_code == 200
    assert client.post("/api/jobs/batch-retry", headers=headers,
                       json={"ids": [1]}).status_code == 403


@pytest.mark.parametrize("query", ["page=0", "page_size=101", "status=unknown",
                                   "repository_id=0", "mr_iid=0"])
def test_premerge_search_rejects_invalid_filters(client: TestClient, query: str) -> None:
    """非法页码或筛选不得回退到无条件查询。"""

    assert client.get(f"/api/premerge-search?{query}", headers=ADMIN).status_code == 422
