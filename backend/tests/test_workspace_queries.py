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
    assert result["todo"] == {"events_attention": 0, "premerge_failed": 0,
                              "premerge_partial": 0}
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


def test_overview_todo_only_counts_latest_premerge_versions(
    client: TestClient, settings: Settings,
) -> None:
    """首页待办显示异常事件与每个 MR 的最新失败或部分完成版本。"""

    store, repository_id = populate(client, settings, 1)
    with store.connection() as db:
        db.execute("UPDATE merge_events SET status='needs_attention' WHERE id=1")
    assert client.put(f"/api/repositories/{repository_id}/premerge", headers=ADMIN,
                      json={"enabled": True}).status_code == 200
    enqueue_premerge(store, repository_id, 7, "a" * 40)
    with store.connection() as db:
        db.execute("UPDATE premerge_reviews SET status='failed' WHERE id=1")
    enqueue_premerge(store, repository_id, 7, "b" * 40)
    with store.connection() as db:
        db.execute("UPDATE premerge_reviews SET status='partial' WHERE id=2")
    result = client.get("/api/overview", headers=ADMIN).json()
    assert result["todo"] == {"events_attention": 1, "premerge_failed": 0,
                              "premerge_partial": 1}


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


def test_overview_issue_scope_lifecycle_and_unclassified(
    client: TestClient, settings: Settings,
) -> None:
    """全局问题去重、不受项目暂停影响，合并和重开立即改变汇总。"""

    repository_id = create_repository(client)
    store = Store(settings.data_dir / "app.db")
    finish_with_finding(store, repository_id, 1, "a" * 40)
    finish_with_finding(store, repository_id, 2, "b" * 40)
    with store.connection() as db:
        for index, severity in enumerate(("critical", "medium", "low", None, "future")):
            db.execute("""INSERT INTO review_issues
                (repository_id,fingerprint,path,content,severity,status)
                VALUES(?,?,?,?,?,'open')""",
                (repository_id, str(index), "scope.py", "合成问题", severity))
        db.execute("UPDATE repositories SET enabled=0 WHERE id=?", (repository_id,))
    data = client.get("/api/overview?days=7&repository_id=999", headers=ADMIN).json()
    assert data["issue_todo"] == {"open_count": 6, "severity_counts": {
        "critical": 1, "high": 1, "medium": 1, "low": 1, "unclassified": 2}}
    assert client.get("/api/review-issues?status=open", headers=ADMIN).json()["total"] == 6
    for status, count in (("fixed", 5), ("ignored", 5), ("open", 6)):
        assert client.patch("/api/review-issues/1", headers=ADMIN,
                            json={"status": status}).status_code == 200
        assert client.get("/api/overview", headers=ADMIN).json()[
            "issue_todo"]["open_count"] == count
    assert client.post("/api/review-issues/2/merge", headers=ADMIN,
                       json={"target_id": 1}).status_code == 200
    assert client.get("/api/overview", headers=ADMIN).json()["issue_todo"]["open_count"] == 5
    assert client.get("/api/review-issues?status=open", headers=ADMIN).json()["total"] == 5


def test_overview_activity_includes_recovery_and_running_precedes_queue(
    client: TestClient, settings: Settings,
) -> None:
    """同任务初审与活动补审只计一次，补审不修改旧 summary 兼容字段。"""

    store, _ = populate(client, settings, 4)
    with store.connection() as db:
        db.execute("UPDATE review_jobs SET status='partial',attempts=1 WHERE id IN (1,2)")
        db.execute("UPDATE review_jobs SET status='running',attempts=1 WHERE id=3")
        for job_id, state in ((1, "queued"), (2, "running"), (3, "queued")):
            db.execute("""INSERT INTO review_recoveries(job_id,source_attempt,source_revision,
                client_key,source_digest,source_result_json,config_snapshot,approved_json,
                token_budget,timeout_seconds,status) VALUES(?,1,0,?,'digest','{}','{}','[]',
                1000,60,?)""", (job_id, f"overview-{job_id}", state))
    result = client.get("/api/overview", headers=ADMIN).json()
    assert result["activity"] == {"total": 4, "queued": 2, "running": 2}
    assert result["summary"]["queued"] == 1 and result["summary"]["running"] == 1
    assert result["activity"]["total"] == client.get(
        "/api/task-search?view=active", headers=ADMIN).json()["total"]


def test_actionable_scope_applies_to_items_total_facets_and_latest_version(
    client: TestClient, settings: Settings,
) -> None:
    """列表默认历史范围不变；首页启用范围在所有投影中一致，先选最新再筛失败。"""

    store, repository_id = populate(client, settings, 2)
    with store.connection() as db:
        db.execute("UPDATE merge_events SET status='needs_attention' WHERE id=1")
    assert client.put(f"/api/repositories/{repository_id}/premerge", headers=ADMIN,
                      json={"enabled": True}).status_code == 200
    for sha in ("a", "b"):
        enqueue_premerge(store, repository_id, 7, sha * 40)
    with store.connection() as db:
        db.execute("UPDATE premerge_reviews SET status='failed' WHERE id=1")
        db.execute("UPDATE premerge_reviews SET status='partial' WHERE id=2")
    url = "/api/premerge-search?actionable_only=true&latest_only=true"
    scoped = client.get(url + "&status=failed", headers=ADMIN).json()
    assert scoped["items"] == [] and scoped["total"] == 0
    assert scoped["status_counts"] == {"all": 1, "partial": 1}
    snapshot = client.get("/api/overview", headers=ADMIN).json()
    assert snapshot["todo"]["premerge_partial"] == client.get(
        url + "&status=partial", headers=ADMIN).json()["total"] == 1
    assert snapshot["todo"]["events_attention"] == client.get(
        "/api/event-search?actionable_only=true&status=needs_attention", headers=ADMIN
    ).json()["total"] == 1
    with store.connection() as db:
        db.execute("UPDATE premerge_settings SET enabled=0")
    assert client.get(url, headers=ADMIN).json()["status_counts"] == {"all": 0}
    assert client.get("/api/premerge-search", headers=ADMIN).json()["total"] == 1
    with store.connection() as db:
        db.execute("UPDATE repositories SET enabled=0")
    for path in ("/api/event-search?actionable_only=true", url):
        result = client.get(path, headers=ADMIN).json()
        assert result["items"] == [] and result["total"] == 0
        assert result["status_counts"] == {"all": 0}
    assert client.get("/api/event-search", headers=ADMIN).json()["total"] == 2
    assert client.get("/api/overview", headers=ADMIN).json()["todo"] == {
        "events_attention": 0, "premerge_failed": 0, "premerge_partial": 0}


def test_empty_overview_has_confirmed_zero_summaries(client: TestClient) -> None:
    """真实空库明确返回零，与旧服务缺字段或读取失败不同。"""

    result = client.get("/api/overview", headers=ADMIN).json()
    assert result["activity"] == {"total": 0, "queued": 0, "running": 0}
    assert result["issue_todo"]["open_count"] == 0
    assert set(result["issue_todo"]["severity_counts"].values()) == {0}


def test_overview_issue_growth_does_not_add_per_issue_queries(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """合成五千条问题只增加聚合数据量，不增加 SQL 次数或返回问题正文。"""

    import json
    import time
    from contextlib import contextmanager
    from typing import Any

    store, repository_id = populate(client, settings, 1)
    original = Store.connection
    statements: list[str] = []

    @contextmanager
    def traced(self: Store) -> Any:
        with original(self) as db:
            db.set_trace_callback(statements.append)
            yield db

    monkeypatch.setattr(Store, "connection", traced)

    def measure() -> tuple[int, int, float]:
        statements.clear()
        start = time.perf_counter()
        response = client.get("/api/overview", headers=ADMIN)
        elapsed = time.perf_counter() - start
        assert response.status_code == 200
        assert "合成性能问题正文" not in response.text
        reads = sum(sql.lstrip().upper().startswith(("SELECT", "WITH")) for sql in statements)
        return reads, len(response.content), round(elapsed * 1000, 2)

    baseline = measure()
    with store.connection() as db:
        db.executemany("""INSERT INTO review_issues
            (repository_id,fingerprint,path,content,severity,status) VALUES(?,?,?,?,?,'open')""",
            [(repository_id, str(index), "synthetic.py", "合成性能问题正文", "high")
             for index in range(5000)])
    grown = measure()
    assert baseline[0] == grown[0]
    assert grown[1] - baseline[1] < 32
    assert client.get("/api/overview", headers=ADMIN).json()["issue_todo"]["open_count"] == 5000
    print(json.dumps({"empty_issues": baseline, "five_thousand_issues": grown,
                      "columns": ["read_queries", "response_bytes", "elapsed_ms"]}))
