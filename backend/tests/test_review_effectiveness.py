"""验证评审效果的时间、项目和人工反馈口径，不连接外部服务。"""

from __future__ import annotations

from fastapi.testclient import TestClient
from ocr_manager.config import Settings
from ocr_manager.storage import SCHEMA_VERSION, Store

ADMIN = {"X-Admin-Token": "test-admin-token"}


def _repository(client: TestClient, name: str, project_id: int) -> int:
    """用合成项目隔离统计数据。"""

    response = client.post("/api/repositories", headers=ADMIN, json={
        "name": name, "gitlab_url": "https://gitlab.example.test",
        "project_id": project_id,
        "remote_url": f"git@gitlab.example.test:team/{name}.git",
        "target_branch": "main", "auth_kind": "secret",
        "webhook_token": "local-secret-token-123",
    })
    assert response.status_code == 201
    return int(response.json()["id"])


def _finding(store: Store, repository_id: int, mr_iid: int, category: str) -> int:
    """完成一次评审，保留真实任务与问题外键。"""

    sha = f"{mr_iid:040x}"
    assert store.add_event(repository_id, mr_iid, f"delivery-{repository_id}-{mr_iid}",
                           sha, None)
    event = store.next_event()
    assert event is not None
    store.finish_event(event["id"], [sha], {sha: ("snapshot", "")}, None)
    job = store.next_job()
    assert job is not None
    store.finish_job(job["id"], "complete", None, {"comments": [{
        "path": "src/app.py", "start_line": 4, "severity": "high",
        "category": category, "content": f"检查 {category} 边界 {mr_iid}",
    }]}, None)
    return int(job["id"])


def test_effectiveness_separates_generated_published_and_feedback(
    client: TestClient, settings: Settings,
) -> None:
    """GitLab 发布、价值反馈与问题状态分别统计；误报不自动关闭问题。"""

    first = _repository(client, "first", 41)
    second = _repository(client, "second", 42)
    store = Store(settings.data_dir / "app.db")
    one = _finding(store, first, 7, "security")
    two = _finding(store, first, 8, "security")
    _finding(store, second, 9, "style")
    with store.connection() as db:
        db.execute("""INSERT INTO gitlab_publications(job_id,attempt_number,comment_index,
            status) VALUES(?,?,0,'sent')""", (one, 1))
    assert client.put(f"/api/jobs/{one}/feedback/0", headers=ADMIN,
                      json={"verdict": "false_positive"}).status_code == 200
    assert client.put(f"/api/jobs/{two}/feedback/0", headers=ADMIN,
                      json={"verdict": "helpful"}).status_code == 200
    response = client.get(f"/api/review-effectiveness?repository_id={first}&days=7",
                          headers=ADMIN)
    assert response.status_code == 200
    data = response.json()
    assert {key: data["summary"][key] for key in
            ("generated", "published", "feedback_marked", "false_positive")} == {
                "generated": 2, "published": 1, "feedback_marked": 2, "false_positive": 1}
    assert data["categories"] == [{"category": "security", "generated": 2,
                                    "issues": 2, "open_issues": 2}]
    assert data["summary"]["ignored"] == 0 and data["summary"]["fixed"] == 0
    assert len(data["projects"]) == 1 and data["projects"][0]["id"] == first
    assert client.get("/api/review-effectiveness", headers=ADMIN).json()[
        "summary"]["generated"] == 3
    assert client.get("/api/review-effectiveness").status_code == 401
    assert client.get("/api/review-effectiveness?days=8", headers=ADMIN).status_code == 422
    assert client.get("/api/review-effectiveness?repository_id=999",
                      headers=ADMIN).status_code == 404


def test_effectiveness_empty_and_old_occurrences(
    client: TestClient, settings: Settings,
) -> None:
    """窗口外的出现记录不进入生成数；空结果有零值和完整趋势。"""

    repository_id = _repository(client, "empty", 43)
    store = Store(settings.data_dir / "app.db")
    empty = client.get(f"/api/review-effectiveness?repository_id={repository_id}&days=7",
                       headers=ADMIN).json()
    assert empty["summary"]["generated"] == 0
    assert empty["summary"]["feedback_marked"] == 0
    assert len(empty["trend"]) == 7
    _finding(store, repository_id, 10, "security")
    with store.connection() as db:
        db.execute("UPDATE review_issue_occurrences SET created_at='2020-01-01 00:00:00'")
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    data = client.get(f"/api/review-effectiveness?repository_id={repository_id}&days=7",
                      headers=ADMIN).json()
    assert data["summary"]["generated"] == 0
    assert data["categories"] == []
    assert data["summary"]["new_issues"] == 1


def test_project_overview_filters_period_flows_but_keeps_current_risk(
    client: TestClient, settings: Settings,
) -> None:
    """项目筛选覆盖所有业务数据；旧开放问题不被时间窗口裁掉。"""

    first = _repository(client, "risk", 51)
    second = _repository(client, "other", 52)
    empty = _repository(client, "empty", 53)
    store = Store(settings.data_dir / "app.db")
    old = _finding(store, first, 20, "security")
    fixed = _finding(store, first, 21, "style")
    _finding(store, second, 22, "security")
    with store.connection() as db:
        db.execute("""UPDATE review_issues SET severity='critical',first_seen_at='2020-01-01'
            WHERE id IN (SELECT issue_id FROM review_issue_occurrences WHERE job_id=?)""", (old,))
        db.execute("UPDATE review_jobs SET finished_at='2020-01-01' WHERE id=?", (old,))
        db.execute("""UPDATE review_issues SET status='fixed',closed_at=datetime('now')
            WHERE id IN (SELECT issue_id FROM review_issue_occurrences WHERE job_id=?)""", (fixed,))
    scoped = client.get(f"/api/review-effectiveness?repository_id={first}&days=7",
                        headers=ADMIN).json()
    assert scoped["summary"]["reviews"] == 1
    assert scoped["summary"]["new_issues"] == 1
    assert scoped["summary"]["fixed"] == 1
    assert scoped["summary"]["open_now"] == 1
    assert scoped["current_issues"] == {
        "open_count": 1,
        "severity_counts": {"critical": 1, "high": 0, "medium": 0, "low": 0, "unclassified": 0},
    }
    project = scoped["projects"][0]
    assert project["reviews"] == project["new_issues"] == project["fixed_issues"] == 1
    assert project["critical_issues"] == 1 and project["high_issues"] == 0
    assert sum(row["new"] for row in scoped["trend"]) == 1
    all_data = client.get("/api/review-effectiveness?days=30", headers=ADMIN).json()
    assert all_data["summary"]["open_now"] == 2
    assert sum(row["open_issues"] for row in all_data["projects"]) == 2
    assert sum(row["reviews"] for row in all_data["projects"]) == 2
    assert all_data["projects"][-1]["id"] == empty
    with store.connection() as db:
        db.execute("""UPDATE review_issues SET severity='unknown'
            WHERE id IN (SELECT issue_id FROM review_issue_occurrences WHERE job_id=?)""", (old,))
    unknown = client.get(f"/api/review-effectiveness?repository_id={first}&days=90",
                         headers=ADMIN).json()
    assert unknown["current_issues"]["severity_counts"]["unclassified"] == 1
    assert unknown["summary"]["open_now"] == 1
