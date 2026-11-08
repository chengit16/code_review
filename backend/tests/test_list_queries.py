"""全局列表的分面、全历史分页、敏感投影与授权边界；只使用合成临时库。"""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from ocr_manager.chat_capture_store import inbox, ingest_messages
from ocr_manager.config import Settings
from ocr_manager.premerge_summary import premerge_summary
from test_chat_capture import _fixture, _message
from test_improvement_themes import _theme
from test_improvements import _payload
from test_task_operations import populate

ADMIN = {"X-Admin-Token": "test-admin-token"}


def test_issue_and_event_facets_preserve_scope(client: TestClient, settings: Settings) -> None:
    """分面忽略当前状态和分页，但保留项目、级别、文本或 MR；普通全部排除已合并。"""

    store, repository = populate(client, settings, 3)
    with store.connection() as db:
        for index, status in enumerate(("open", "open", "fixed", "ignored", "merged")):
            db.execute("""INSERT INTO review_issues
                (repository_id,fingerprint,path,content,severity,status) VALUES(?,?,?,?,?,?)""",
                (repository, str(index), "scope.py", "合成发现", "high", status))
        db.execute("UPDATE merge_events SET status='needs_attention' WHERE id=1")
    result = client.get("/api/review-issues?status=open&page_size=1&page=2&q=scope&severity=high",
                        headers=ADMIN).json()
    assert result["total"] == 2 and len(result["items"]) == 1
    assert result["status_counts"] == {"all": 4, "open": 2, "fixed": 1,
                                       "ignored": 1, "merged": 1}
    assert client.get("/api/review-issues?severity=low", headers=ADMIN).json()[
        "status_counts"]["all"] == 0
    events = client.get("/api/event-search?status=done&page_size=1&page=2", headers=ADMIN).json()
    assert events["total"] == 2 and events["status_counts"] == {
        "all": 3, "done": 2, "needs_attention": 1}
    scoped = client.get("/api/event-search?status=done&mr_iid=1", headers=ADMIN).json()
    assert scoped["total"] == 0 and scoped["status_counts"] == {"all": 1, "needs_attention": 1}


def test_premerge_latest_facets_and_safe_summary(client: TestClient, settings: Settings) -> None:
    """先挑每个 MR 最新版本再筛状态；摘要模式不携带正文、上下文和完整文件内容。"""

    store, repository = populate(client, settings, 0)
    with store.connection() as db:
        for index, (mr, status) in enumerate(((1, "failed"), (1, "complete"), (2, "failed"))):
            db.execute("""INSERT INTO premerge_reviews
                (repository_id,mr_iid,head_sha,status,result_json,context_json,changed_files)
                VALUES(?,?,?,?,?,?,?)""", (repository, mr, f"{index:040x}", status,
                json.dumps({"comments": [], "thinking": "synthetic-private-body"}),
                '{"private":"synthetic-private-context"}', '[]'))
    url = "/api/premerge-search?status=failed&page_size=1&summary_only=true"
    response = client.get(url, headers=ADMIN)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["total"] == 1 and result["status_counts"] == {
        "all": 2, "complete": 1, "failed": 1}
    assert "synthetic-private" not in response.text
    assert not {"result_json", "context_json", "changed_files"} & result["items"][0].keys()
    assert result["items"][0]["summary"]["coverage"] == "unknown"
    history = client.get(url + "&latest_only=false", headers=ADMIN).json()
    assert history["total"] == 2 and history["status_counts"]["all"] == 3


@pytest.mark.parametrize("endpoint,payload,statuses", [
    ("improvements", _payload, ("open", "investigating")),
    ("improvement-themes", _theme, ("planned", "active")),
])
def test_platform_facets_ignore_own_status(client: TestClient, endpoint: str,
                                         payload: Any, statuses: tuple[str, str]) -> None:
    """两类台账只统计当前分类与归档范围，不把当前页长度当总数。"""

    for status in statuses:
        response = client.post(f"/api/{endpoint}", headers=ADMIN,
                               json=payload(status=status, category="stability"))
        assert response.status_code == 201, response.text
    result = client.get(f"/api/{endpoint}?status={statuses[0]}&page_size=1&category=stability",
                        headers=ADMIN).json()
    assert result["total"] == 1
    assert result["status_counts"] == {"all": 2, statuses[0]: 1, statuses[1]: 1}
    assert client.get(f"/api/{endpoint}?category=integration", headers=ADMIN).json()[
        "status_counts"]["all"] == 0


def test_history_beyond_recent_hundred_and_redaction(client: TestClient,
                                                    settings: Settings) -> None:
    """全历史可到第一版；旧接口保留最近百条，筛选、时间、认证不能绕过。"""

    store, repository = populate(client, settings, 0)
    with store.connection() as db:
        for index in range(105):
            db.execute("UPDATE repositories SET name=? WHERE id=?",
                       (f"合成名称{index}", repository))
    assert len(client.get("/api/config-history/repository", headers=ADMIN).json()) == 100
    url = f"/api/config-history-search?kind=repository&object_id={repository}"
    result = client.get(url + "&page_size=100&page=2", headers=ADMIN)
    assert result.status_code == 200, result.text
    assert result.json()["total"] == 106 and len(result.json()["items"]) == 6
    assert result.json()["items"][-1]["action"] == "created"
    for secret in ("test-webhook-token", "gAAAA"):
        assert secret not in result.text
    assert client.get(url + "&action=updated", headers=ADMIN).json()["total"] == 105
    for suffix in ("&since=2026-01-01T00:00:00",
                   "&since=2026-11-09T00:00:00Z&until=2026-01-01T00:00:00Z", "&action=other"):
        assert client.get(url + suffix, headers=ADMIN).status_code == 422
    assert client.get(url).status_code == 401
    assert client.get(url + "&until=2000-01-01T00:00:00Z", headers=ADMIN).json()["total"] == 0


def test_audit_search_is_literal_and_authorized(client: TestClient, settings: Settings) -> None:
    """只搜索审计元数据，通配符按文本处理；页总数与返回行一致。"""

    store, _ = populate(client, settings, 0)
    for index in range(3):
        store.record_audit("合成动作", "synthetic_object", index, "ok", actor_name="合成人员")
    result = client.get("/api/audit-logs?q=合成人员&page_size=2&page=2", headers=ADMIN).json()
    assert result["total"] == 3 and len(result["items"]) == 1
    assert client.get("/api/audit-logs?q=%25", headers=ADMIN).json()["total"] == 0
    assert client.get("/api/audit-logs?q=合成人员").status_code == 401


def test_chat_classification_does_not_shrink_pending_or_expand_binding(settings: Settings) -> None:
    """分类仅缩小列表；全范围待核实计数和绑定授权保持原事实。"""

    store, binding = _fixture(settings)
    ingest_messages(store, binding, 1, [_message("请比较方案", "pending"),
        _message("确认报错", "issue"), _message("合成完成", "assistant", role="assistant")])
    result = inbox(store, classification="issue")
    assert result.total == 1 and result.items[0].classification == "issue"
    assert result.pending == inbox(store).pending == 1
    assert [item.id for item in result.bindings] == [binding]


@pytest.mark.parametrize("change,expected", [
    ({}, "complete"),
    ({"terminal_state": "partial"}, "partial"),
    ({"coverage": {"selected": [{"item_id": "a"}, {"item_id": "a"}],
                    "completed": [{"item_id": "a"}], "reused": [],
                    "failed": [], "waived": []}}, "partial"),
    ({"coverage": {}}, "unknown"),
])
def test_premerge_coverage_requires_unique_evidence(change: dict[str, Any], expected: str) -> None:
    """缺证、重复身份或部分覆盖均不显示完整覆盖。"""

    manifest = {"terminal_state": "complete", "coverage": {"selected": [{"item_id": "a"}],
        "completed": [{"item_id": "a"}], "reused": [], "failed": [], "waived": []}, **change}
    result = premerge_summary(json.dumps({"comments": [{
        "path": "a", "content": "合成发现", "severity": "high"}],
        "manifest": manifest, "input_filter": {"excluded_count": 2}}))
    assert result["coverage"] == expected and result["highest_severity"] == "high"
    assert result["excluded_count"] == 2
    assert premerge_summary("malformed")["result_available"] is False


def test_summary_payload_and_constant_query_count(client: TestClient, settings: Settings,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    """百行摘要无逐行查询；对比响应体积，不把本地耗时当生产性能承诺。"""

    from contextlib import contextmanager
    from time import perf_counter

    from ocr_manager.workspace_queries import search_premerge

    store, repository = populate(client, settings, 0)
    with store.connection() as db:
        for index in range(100):
            db.execute("""INSERT INTO premerge_reviews
                (repository_id,mr_iid,head_sha,status,result_json,context_json)
                VALUES(?,?,?,?,?,?)""", (repository, index + 1, f"{index:040x}", "complete",
                json.dumps({"comments": [{"path": "a.py", "content": "合成正文" * 1000}]}),
                json.dumps({"synthetic_context": "合成上下文" * 1000})))
    statements: list[str] = []
    original = store.connection

    @contextmanager
    def traced() -> Any:
        with original() as db:
            db.set_trace_callback(statements.append)
            yield db

    monkeypatch.setattr(store, "connection", traced)
    started = perf_counter()
    full = search_premerge(store, repository, None, None, True, 1, 100)
    full_ms = (perf_counter() - started) * 1000
    statements.clear()
    started = perf_counter()
    summary = search_premerge(store, repository, None, None, True, 1, 100, summary_only=True)
    summary_ms = (perf_counter() - started) * 1000
    assert len([sql for sql in statements if sql.lstrip().startswith("SELECT")]) == 3
    full_bytes = len(json.dumps(full, ensure_ascii=False).encode())
    summary_bytes = len(json.dumps(summary, ensure_ascii=False).encode())
    assert summary_bytes < full_bytes / 10
    print(f"合成百行响应：完整 {full_bytes} 字节 / 摘要 {summary_bytes} 字节；"
          f"查询含解析 {full_ms:.1f} / {summary_ms:.1f} 毫秒；摘要固定三条 SELECT")


@pytest.mark.parametrize("endpoint", ["event-search", "config-history-search?kind=repository"])
def test_list_range_rejects_mixed_timezones(client: TestClient, endpoint: str) -> None:
    """混合无时区和带时区输入返回协议错误，不能进入比较抛出 500。"""

    separator = "&" if "?" in endpoint else "?"
    response = client.get(f"/api/{endpoint}{separator}since=2026-01-01T00:00:00"
                          "&until=2026-01-02T00:00:00Z", headers=ADMIN)
    assert response.status_code == 422
