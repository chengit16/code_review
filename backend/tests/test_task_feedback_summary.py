"""临时数据库验证列表与详情的反馈计数；不修改真实任务或调用外部服务。"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from ocr_manager.api import create_app
from ocr_manager.config import Settings
from ocr_manager.storage import Store
from test_review_conclusions import recovered as recovered
from test_review_recovery import ADMIN
from test_task_issue_summary import _seed
from test_task_operations import populate


def test_feedback_counts_findings_not_problem_states(
    client: TestClient, settings: Settings,
) -> None:
    """同问题多条发现分别计数，问题被忽略不会伪造忽略反馈，历史修复仍属未评价。"""

    store, _ = populate(client, settings, 3)
    _seed(store, 1, [{"path": "a.py", "content": "同一合成问题"}] * 5)
    _seed(store, 2, [])
    with store.connection() as db:
        db.execute("UPDATE review_issues SET status='ignored'")
        choices = ["helpful", "helpful", "false_positive", "ignored", "fixed"]
        for index, verdict in enumerate(choices):
            db.execute("INSERT INTO review_feedback(job_id,comment_index,verdict) VALUES(1,?,?)",
                       (index, verdict))
    headers = {"X-Admin-Token": settings.admin_token}
    rows = {item["id"]: item for item in client.get(
        "/api/task-search", headers=headers).json()["items"]}
    assert rows[1]["issue_summary"]["ignored_count"] == 1
    assert rows[1]["feedback_summary"] == {
        "available": True, "total": 5, "helpful": 2, "false_positive": 1,
        "ignored": 1, "unmarked": 1,
    }
    assert rows[1]["feedback_summary"] == client.get(
        "/api/jobs/1", headers=headers).json()["feedback_summary"]
    assert rows[2]["feedback_summary"] == {
        "available": True, "total": 0, "helpful": 0, "false_positive": 0,
        "ignored": 0, "unmarked": 0,
    }
    assert rows[3]["feedback_summary"]["available"] is False
    assert rows[3]["feedback_summary"]["total"] is None
    assert client.put("/api/jobs/1/feedback/0", headers=headers,
                      json={"verdict": "ignored"}).status_code == 200
    summary = client.get("/api/jobs/1", headers=headers).json()["feedback_summary"]
    assert summary["helpful"] == 1 and summary["ignored"] == 2
    assert client.delete("/api/jobs/1/feedback/0", headers=headers).status_code == 200
    assert client.get("/api/jobs/1", headers=headers).json()["feedback_summary"]["unmarked"] == 2


def test_feedback_facets_count_tasks_before_paging(
    client: TestClient, settings: Settings,
) -> None:
    """部分反馈仍属待反馈；分面保留其他筛选，排除零发现和缺损，撤销后实时更新。"""

    store, repository = populate(client, settings, 5)
    _seed(store, 1, [{"path": "a.py", "content": "合成发现"}] * 2)
    _seed(store, 2, [{"path": "b.py", "content": "合成发现"}])
    _seed(store, 3, [])
    _seed(store, 4, [{"path": "c.py", "content": "合成发现"}])
    with store.connection() as db:
        db.execute("UPDATE review_jobs SET finished_at=CURRENT_TIMESTAMP WHERE id<=4")
        db.execute("INSERT INTO review_feedback(job_id,comment_index,verdict) "
                   "VALUES(1,0,'helpful'),(2,0,'ignored')")
    headers = {"X-Admin-Token": settings.admin_token}
    filters = {"page_size": 1, "repository_id": repository}
    for state, total in (("pending", 2), ("handled", 1)):
        result = client.get("/api/task-search", headers=headers,
                            params=filters | {"feedback_state": state}).json()
        assert result["total"] == total and len(result["items"]) == 1
        assert result["feedback_counts"] == {"pending": 2, "handled": 1}
    result = client.get("/api/task-search", headers=headers,
                        params=filters | {"status": "queued"}).json()
    assert result["feedback_counts"] == {"pending": 0, "handled": 0}
    assert client.delete("/api/jobs/2/feedback/0", headers=headers).status_code == 200
    result = client.get("/api/task-search", headers=headers, params=filters).json()
    assert result["feedback_counts"] == {"pending": 3, "handled": 0}


def test_promoted_feedback_uses_main_identities_and_hides_old_attempt(
    recovered: tuple[Store, Settings, dict[str, Any]],
) -> None:
    """初审镜像不双计、补审身份不与相同下标串写，重新排队立即隐藏历史反馈。"""

    store, settings, _ = recovered
    with TestClient(create_app(settings)) as api:
        for identity, verdict in zip(
            ["j1:a1:c0", "j1:a1:r1:c0", "j1:a1:r2:c0"],
            ["helpful", "false_positive", "ignored"], strict=True,
        ):
            assert api.put(f"/api/jobs/1/finding-feedback/{identity}", headers=ADMIN, json={
                "source_attempt": 1, "revision": 2, "verdict": verdict,
            }).status_code == 200
        detail = api.get("/api/jobs/1", headers=ADMIN).json()
        listing = api.get("/api/task-search", headers=ADMIN).json()["items"][0]
        assert listing["feedback_summary"] == detail["feedback_summary"] == {
            "available": True, "total": 3, "helpful": 1, "false_positive": 1,
            "ignored": 1, "unmarked": 0,
        }
        assert detail["issue_summary"]["open_count"] == 3
        assert store.retry_job(1) == 1
        current = api.get("/api/task-search", headers=ADMIN).json()["items"][0]
        assert current["feedback_summary"] == {
            "available": False, "total": None, "helpful": 0, "false_positive": 0,
            "ignored": 0, "unmarked": 0,
        }
