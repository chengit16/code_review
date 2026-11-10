"""验证统一发现分页、历史关联、冻结批量版本及真实角色权限；仅用合成 SQLite。"""

from typing import Any

from fastapi.testclient import TestClient
from ocr_manager.api import create_app
from ocr_manager.config import Settings
from ocr_manager.storage import Store
from test_auth import create_user, enable_users, login
from test_review_conclusions import recovered as recovered
from test_review_effectiveness import ADMIN, _finding, _repository

BASE = "/api/review-findings"


def test_unified_counts_paging_and_independent_history(
    client: TestClient, settings: Settings,
) -> None:
    """处理与反馈交叉筛选先于分页；同问题多条发现分别计数，历史关闭不产生反馈。"""

    repo = _repository(client, "unified", 111)
    other = _repository(client, "other-unified", 112)
    store = Store(settings.data_dir / "app.db")
    jobs = [_finding(store, repo, i, "security") for i in range(1, 6)]
    _finding(store, other, 6, "style")
    for job, verdict in zip(jobs, ("helpful", "false_positive", "ignored"), strict=False):
        assert client.put(f"/api/jobs/{job}/finding-feedback/j{job}:a1:c0", headers=ADMIN,
                          json={"source_attempt": 1, "revision": 0,
                                "verdict": verdict}).status_code == 200
    with store.connection() as db:
        issue = db.execute("SELECT issue_id FROM review_issue_occurrences WHERE job_id=?",
                           (jobs[0],)).fetchone()[0]
        db.execute("UPDATE review_issue_occurrences SET issue_id=? WHERE job_id=?",
                   (issue, jobs[1]))
        db.execute("UPDATE review_issues SET status='fixed' WHERE id=?", (issue,))
    quality = client.get("/api/review-effectiveness", headers=ADMIN,
                         params={"repository_id": repo}).json()["quality"]
    window = {key: quality[key] for key in ("since", "until")}
    assert quality["summary"] == {"total": 5, "helpful": 1, "false_positive": 1,
                                   "ignored": 1, "unmarked": 2}
    assert sum(quality["pending_severity"].values()) == 2
    for handling, count in (("all", 5), ("pending", 2), ("handled", 3)):
        response = client.get(BASE, headers=ADMIN,
                              params=window | {"repository_id": repo, "handling": handling,
                                               "page_size": 1}).json()
        assert response["total"] == count and len(response["items"]) == 1
    first = client.get(BASE, headers=ADMIN, params={"handling": "all", "page_size": 2}).json()
    second = client.get(BASE, headers=ADMIN,
                        params={"handling": "all", "page_size": 2, "page": 2}).json()
    assert not ({r["finding_id"] for r in first["items"]} &
                {r["finding_id"] for r in second["items"]})
    related = client.get(BASE, headers=ADMIN,
                         params={"issue_id": issue, "handling": "all"}).json()
    assert related["total"] == 2
    assert {r["feedback"] for r in related["items"]} == {"helpful", "false_positive"}
    assert client.get(BASE, headers=ADMIN, params={"feedback": "ignored",
                      "handling": "handled"}).json()["total"] == 1
    assert client.get(BASE, headers=ADMIN, params={"feedback": "ignored"}).json()["total"] == 0
    detail = client.get(f"{BASE}/j{jobs[0]}:a1:c0", headers=ADMIN).json()
    assert detail["handling"] == "handled" and detail["content"].startswith("检查")
    assert "content" not in first["items"][0]
    assert client.get(BASE, headers=ADMIN, params={"q": "' OR 1=1--"}).json()["total"] == 0
    assert client.get("/api/task-search?feedback_state=handled", headers=ADMIN).json()["total"] == 3
    assert client.get("/api/task-search?feedback_state=pending", headers=ADMIN).json()["total"] == 3
    assert client.delete(f"/api/jobs/{jobs[0]}/finding-feedback/j{jobs[0]}:a1:c0",
                         headers=ADMIN, params={"source_attempt": 1,
                                                "revision": 0}).status_code == 200
    assert client.get(BASE, headers=ADMIN, params={"handling": "handled"}).json()["total"] == 2
    assert client.get(f"/api/review-issues/{issue}", headers=ADMIN).json()["status"] == "fixed"


def test_batch_freezes_each_version_and_retains_partial_failures(
    recovered: tuple[Store, Settings, dict[str, Any]],
) -> None:
    """补审主身份只计一次；混合合法、过期、错任务及缺失身份时逐项返回，不改写其他来源。"""

    store, settings, _ = recovered
    with TestClient(create_app(settings)) as api:
        listing = api.get(BASE, headers=ADMIN, params={"handling": "all"}).json()
        assert listing["total"] == 3
        keys = ("job_id", "finding_id", "source_attempt", "revision")
        targets = [{key: item[key] for key in keys} for item in listing["items"]]
        targets[1]["revision"] = 0
        targets[2]["job_id"] = 999
        response = api.post(BASE + "/batch-feedback", headers=ADMIN,
                            json={"targets": targets, "verdict": "ignored"})
        assert response.status_code == 200
        assert response.json()["updated"] == 1
        assert {r["status"] for r in response.json()["results"]} == {
            "updated", "conflict", "not_found"}
        assert api.get(BASE, headers=ADMIN, params={"handling": "handled"}).json()["total"] == 1
        assert api.post(BASE + "/batch-feedback", headers=ADMIN, json={
            "targets": [targets[0], targets[0]], "verdict": "helpful"}).status_code == 422
        assert api.post(BASE + "/batch-feedback", headers=ADMIN, json={
            "targets": targets, "verdict": "fixed"}).status_code == 422
        store.retry_job(1)
        assert api.get(BASE, headers=ADMIN, params={"handling": "all"}).json()["total"] == 0
        assert api.get(BASE + "/j1:a1:c0", headers=ADMIN).status_code == 404
        retry = api.post(BASE + "/batch-feedback", headers=ADMIN,
                         json={"targets": [targets[0]], "verdict": "helpful"}).json()
        assert retry["updated"] == 0 and retry["results"][0]["status"] == "conflict"


def test_findings_window_and_auth(client: TestClient) -> None:
    """全时查询与显式窗口区分；读者可读取但不能批量写入，畸形范围不回退到全时。"""

    assert client.get(BASE).status_code == 401
    for params in ({"since": "bad"},
                   {"since": "2026-11-01 00:00:00", "until": "2026-11-01 00:00:00"},
                   {"handling": "open"}, {"page_size": 101}, {"repository_id": 999}):
        assert client.get(BASE, headers=ADMIN, params=params).status_code in {404, 422}
    create_user(client, "administrator", "admin")
    create_user(client, "findings-reader", "reader")
    enable_users(client)
    identity = login(client, "findings-reader")
    headers = {"Authorization": f"Bearer {identity['token']}"}
    assert client.get(BASE, headers=headers).status_code == 200
    assert client.post(BASE + "/batch-feedback", headers=headers, json={}).status_code == 403


def test_legacy_only_feedback_can_be_undone_without_history_rewrite(
    client: TestClient, settings: Settings,
) -> None:
    """旧入口无稳定镜像时仍可按当前版本撤销，原问题的修复记录保持不变。"""

    repo = _repository(client, "legacy-undo", 113)
    store = Store(settings.data_dir / "app.db")
    job = _finding(store, repo, 1, "security")
    with store.connection() as db:
        db.execute("INSERT INTO review_feedback(job_id,comment_index,verdict) "
                   "VALUES(?,0,'helpful')", (job,))
        db.execute("UPDATE review_issues SET status='fixed'")
    assert client.get(BASE, headers=ADMIN,
                      params={"handling": "handled"}).json()["total"] == 1
    assert client.delete(f"/api/jobs/{job}/finding-feedback/j{job}:a1:c0", headers=ADMIN,
                         params={"source_attempt": 1, "revision": 0}).status_code == 200
    assert client.get(BASE, headers=ADMIN).json()["total"] == 1
    with store.connection() as db:
        assert db.execute("SELECT status FROM review_issues").fetchone()[0] == "fixed"
        assert db.execute("SELECT COUNT(*) FROM review_feedback").fetchone()[0] == 0
