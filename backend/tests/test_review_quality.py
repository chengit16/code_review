"""隔离验证质量分母、来源版本、分页、反馈变化和真实读者权限，不访问正式数据或外部服务。"""

from __future__ import annotations

import json
import time
from typing import Any

from fastapi.testclient import TestClient
from ocr_manager.api import create_app
from ocr_manager.config import Settings
from ocr_manager.review_quality import quality_snapshot
from ocr_manager.review_recovery_store import claim, enqueue, finish
from ocr_manager.storage import Store
from test_auth import create_user, enable_users, login
from test_review_conclusions import recovered as recovered
from test_review_effectiveness import ADMIN, _finding, _repository
from test_review_recovery import child_result, command, make_source

BASE = "/api/review-effectiveness"


def test_quality_counts_and_samples_share_identity_and_denominator(
    client: TestClient, settings: Settings,
) -> None:
    """四类互斥且未标记不当误报；镜像只计一次，样本总量和筛选一致。"""

    repo = _repository(client, "quality", 71)
    store = Store(settings.data_dir / "app.db")
    jobs = [_finding(store, repo, index, "security" if index < 4 else "style")
            for index in range(1, 6)]
    for job, verdict in zip(jobs, ("helpful", "false_positive"), strict=False):
        store.set_review_feedback(job, 0, verdict)
    with store.connection() as db:
        db.execute("INSERT INTO review_feedback(job_id,comment_index,verdict) VALUES(?,0,'fixed')",
                   (jobs[2],))
    snapshot = client.get(BASE, headers=ADMIN).json()
    quality = snapshot["quality"]
    assert quality["summary"] == {"total": 5, "helpful": 1, "false_positive": 1,
                                  "ignored": 0, "unmarked": 3}
    assert sum(row["total"] for row in quality["trend"]) == 5
    assert sum(row["total"] for row in quality["categories"]) == 5
    assert sum(row["total"] for row in quality["projects"]) == 5
    assert snapshot["current_status_counts"] == {"open": 5, "fixed": 0,
                                                 "ignored": 0, "false_positive": 0, "merged": 0}
    window = {key: quality[key] for key in ("since", "until")}
    for feedback, total in (("all", 5), ("helpful", 1), ("false_positive", 1),
                            ("fixed", 3), ("unmarked", 3)):
        result = client.get(BASE + "/findings", headers=ADMIN,
                            params=window | {"feedback": feedback, "page_size": 5}).json()
        assert result["total"] == total and len(result["items"]) == total
        if result["items"]:
            assert len(result["items"][0]["excerpt"]) <= 160
            assert "result_json" not in result["items"][0]
    assert sum(row["total"] for row in quality["trend"]) == sum(
        row["helpful"] + row["false_positive"] + row["ignored"] + row["unmarked"]
        for row in quality["trend"])
    category = client.get(BASE + "/findings", headers=ADMIN,
                          params=window | {"category": "style"}).json()
    assert category["total"] == 2
    first = client.get(BASE + "/findings?page_size=2", headers=ADMIN).json()
    second = client.get(BASE + "/findings?page_size=2&page=2", headers=ADMIN).json()
    assert not ({row["finding_id"] for row in first["items"]} &
                {row["finding_id"] for row in second["items"]})
    assert client.get(BASE + "/findings?category=%27%20OR%201=1--",
                      headers=ADMIN).json()["total"] == 0
    assert client.get(BASE + "/findings?severity=high", headers=ADMIN).json()["total"] == 5
    assert client.get(BASE + "/findings?severity=low", headers=ADMIN).json()["total"] == 0
    assert client.get(BASE + "/findings?repository_id=999", headers=ADMIN).status_code == 404
    assert client.get(BASE + "/findings").status_code == 401
    for query in ("days=8", "page=0", "page_size=51", "feedback=not_valid",
                  "since=bad", "since=bad&until=bad",
                  "since=2026-1-1%2000:00:00&until=2026-01-02%2000:00:00",
                  "since=2020-01-01%2000:00:00&until=2026-01-01%2000:00:00"):
        assert client.get(BASE + "/findings?" + query, headers=ADMIN).status_code == 422


def test_quality_changes_do_not_confuse_ignored_with_feedback(
    client: TestClient, settings: Settings,
) -> None:
    """问题直接忽略不产生误报反馈，同问题多次出现仍分别评价，状态只计一个编号。"""

    repo = _repository(client, "state", 72)
    store = Store(settings.data_dir / "app.db")
    one = _finding(store, repo, 1, "security")
    two = _finding(store, repo, 2, "security")
    with store.connection() as db:
        issue_ids = [row[0] for row in db.execute("SELECT id FROM review_issues ORDER BY id")]
        db.execute("UPDATE review_issue_occurrences SET issue_id=? WHERE job_id=?",
                   (issue_ids[0], two))
        db.execute("DELETE FROM review_issues WHERE id=?", (issue_ids[1],))
    store.set_review_feedback(one, 0, "helpful")
    assert client.patch(f"/api/review-issues/{issue_ids[0]}", headers=ADMIN,
                        json={"status": "ignored", "note": "暂不处理，并非误报"}).status_code == 200
    data = client.get(BASE, headers=ADMIN).json()
    assert data["quality"]["summary"]["helpful"] == 1
    assert data["quality"]["summary"]["unmarked"] == 1
    assert data["quality"]["summary"]["false_positive"] == 0
    assert data["current_status_counts"]["ignored"] == 1
    assert client.get(BASE + "/findings?feedback=helpful", headers=ADMIN).json()[
        "items"][0]["issue_status"] == "ignored"
    store.clear_review_feedback(one, 0)
    data = client.get(BASE, headers=ADMIN).json()
    assert data["quality"]["summary"]["unmarked"] == 2
    assert data["current_status_counts"]["ignored"] == 1


def test_quality_utc_window_legacy_fallback_and_empty_project(
    client: TestClient, settings: Settings,
) -> None:
    """初审时间使用任务完成时间；旧无稳定映射兼容，窗口外记录不进入同集合分母。"""

    repo = _repository(client, "window", 73)
    other = _repository(client, "empty", 74)
    store = Store(settings.data_dir / "app.db")
    old = _finding(store, repo, 1, "security")
    current = _finding(store, repo, 2, "style")
    store.set_review_feedback(current, 0, "helpful")
    with store.connection() as db:
        db.execute("UPDATE review_jobs SET finished_at='2020-01-01' WHERE id=?", (old,))
        db.execute("DELETE FROM review_issue_occurrences WHERE job_id=?", (current,))
    scoped = client.get(BASE + f"?repository_id={repo}&days=7", headers=ADMIN).json()
    assert scoped["quality"]["summary"]["total"] == 1
    assert scoped["quality"]["summary"]["helpful"] == 1
    legacy = client.get(BASE + "/findings?feedback=helpful", headers=ADMIN).json()["items"][0]
    assert legacy["finding_id"] == f"j{current}:a1:c0" and legacy["issue_id"] is None
    empty = client.get(BASE + f"?repository_id={other}", headers=ADMIN).json()
    assert empty["quality"]["summary"]["total"] == 0
    assert len(empty["quality"]["trend"]) == 30
    assert sum(empty["current_status_counts"].values()) == 0
    assert client.get(BASE + "/findings?feedback=all&page=999", headers=ADMIN).json()[
        "items"] == []


def test_quality_recovery_and_retry_keep_current_primary_sources(
    recovered: tuple[Store, Settings, dict[str, Any]],
) -> None:
    """有效补审主发现计数，镜像不双计；重审排队立即移除旧版本，显式版本仍在样本中。"""

    store, settings, _ = recovered
    store.set_review_feedback(1, 0, "helpful")
    with TestClient(create_app(settings)) as api:
        assert api.put("/api/jobs/1/finding-feedback/j1:a1:r1:c0", headers=ADMIN,
                       json={"source_attempt": 1, "revision": 2,
                             "verdict": "false_positive"}).status_code == 200
        quality = api.get(BASE, headers=ADMIN).json()["quality"]
        assert quality["summary"] == {"total": 3, "helpful": 1, "false_positive": 1,
                                      "ignored": 0, "unmarked": 1}
        rows = api.get(BASE + "/findings", headers=ADMIN).json()
        assert rows["total"] == 3
        assert {row["finding_id"] for row in rows["items"]} == {
            "j1:a1:c0", "j1:a1:r1:c0", "j1:a1:r2:c0"}
        assert all(row["revision"] == 2 for row in rows["items"])
        assert store.retry_job(1) == 1
        assert api.get(BASE, headers=ADMIN).json()["quality"]["summary"]["total"] == 0
        assert api.get(BASE + "/findings", headers=ADMIN).json()["total"] == 0


def test_quality_real_reader_can_only_read(client: TestClient) -> None:
    """新样本路由使用真实会话鉴权，读者可读但不存在写反馈捷径。"""

    create_user(client, "administrator", "admin")
    create_user(client, "quality-reader", "reader")
    enable_users(client)
    identity = login(client, "quality-reader")
    headers = {"Authorization": f"Bearer {identity['token']}"}
    assert client.get(BASE, headers=headers).status_code == 200
    assert client.get(BASE + "/findings", headers=headers).status_code == 200
    assert client.put(BASE + "/findings", headers=headers, json={}).status_code == 405


def test_quality_recovery_duplicates_and_missing_source_are_visible(
    client: TestClient, settings: Settings,
) -> None:
    """补审附加重复来源不增分母；来源丢失不冒充零样本，不在读取时修复数据。"""

    store, enabled, raw = make_source(client, settings)
    enqueue(store, enabled, 1, command())
    task = claim(store)
    assert task
    result = child_result(raw)
    result["comments"] *= 2
    assert finish(store, task, result)
    with TestClient(create_app(enabled)) as api:
        quality = api.get(BASE, headers=ADMIN).json()["quality"]
        assert quality["summary"]["total"] == 2
        assert quality["unavailable_sources"] == 0
        with store.connection() as db:
            db.execute("DELETE FROM review_issue_occurrences WHERE recovery_id IS NOT NULL")
        quality = api.get(BASE, headers=ADMIN).json()["quality"]
        assert quality["summary"]["total"] == 1
        assert quality["unavailable_sources"] == 1


def test_quality_invalid_document_is_not_a_trustworthy_zero(
    client: TestClient, settings: Settings,
) -> None:
    """损坏来源不能因 JSON 回退而变成可信空态，诊断不暴露原始内容。"""

    repo = _repository(client, "invalid", 75)
    store = Store(settings.data_dir / "app.db")
    job = _finding(store, repo, 1, "security")
    with store.connection() as db:
        db.execute("UPDATE review_jobs SET result_json='broken' WHERE id=?", (job,))
    data = client.get(BASE, headers=ADMIN).json()
    assert data["quality"]["summary"]["total"] == 0
    assert data["quality"]["unavailable_sources"] == 1


def test_quality_query_count_does_not_grow_with_findings(
    client: TestClient, settings: Settings,
) -> None:
    """合成大量发现检查固定聚合查询与响应规模；计时只作本机证据，不设生产 SLA。"""

    repo = _repository(client, "volume", 76)
    store = Store(settings.data_dir / "app.db")
    job = _finding(store, repo, 1, "security")
    measurements = []
    for count in (1, 2000):
        with store.connection() as db:
            db.execute("UPDATE review_jobs SET result_json=? WHERE id=?", (json.dumps({
                "comments": [{"path": "src/app.py", "content": "合成发现",
                              "category": "security", "severity": "high"}] * count}), job))
        queries: list[str] = []
        with store.connection() as db:
            db.execute("BEGIN")
            db.set_trace_callback(queries.append)
            start = time.perf_counter()
            snapshot = quality_snapshot(db, repo, 7)
            elapsed = time.perf_counter() - start
            db.set_trace_callback(None)
        assert snapshot["summary"]["total"] == count
        measurements.append((len(queries), len(json.dumps(snapshot)), round(elapsed * 1000, 2)))
        assert "合成发现" not in json.dumps(snapshot, ensure_ascii=False)
    assert measurements[0][0] == measurements[1][0] == 9
    assert measurements[1][1] - measurements[0][1] < 200
    print(f"质量聚合 SQL数/响应字节/毫秒：{measurements}")
