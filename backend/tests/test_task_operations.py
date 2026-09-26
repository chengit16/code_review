"""验证任务全量检索、时间边界及报告权限和敏感内容过滤。"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from ocr_manager.config import Settings
from ocr_manager.storage import Store


def populate(client: TestClient, settings: Settings, count: int = 251) -> tuple[Store, int]:
    """创建合成历史，所有接口验证只使用测试数据库。"""

    response = client.post("/api/repositories", headers={"X-Admin-Token": settings.admin_token},
                           json={"name": "检索项目", "gitlab_url": "https://gitlab.example.test",
                                 "project_id": 42, "remote_url": "git@gitlab.example.test:a/b.git",
                                 "target_branch": "main", "webhook_token": "test-webhook-token"})
    repository_id = response.json()["id"]
    store = Store(settings.data_dir / "app.db")
    for number in range(1, count + 1):
        store.add_event(repository_id, number, None, None, None)
        event = store.next_event()
        assert event is not None
        sha = f"{number:040x}"
        store.finish_event(event["id"], [sha], {sha: ("snapshot", "")}, None)
    return store, repository_id


def test_search_reaches_old_tasks_and_validates_ranges(
    client: TestClient, settings: Settings,
) -> None:
    """第十一页仍可见旧任务；参数不进入 SQL 表达式且时间区间必须有效。"""

    _store, repository_id = populate(client, settings)
    headers = {"X-Admin-Token": settings.admin_token}
    assert client.get("/api/task-search").status_code == 401
    result = client.get("/api/task-search?page=11", headers=headers).json()
    assert result["total"] == 251
    assert [item["id"] for item in result["items"]] == [1]
    response = client.get("/api/task-search", headers=headers, params={
        "repository_id": repository_id, "mr_iid": 1, "target_branch": "main", "sha": "0000",
    })
    assert response.json()["items"][0]["id"] == 1
    assert client.get("/api/task-search?sha=%27&page_size=1000", headers=headers).status_code == 422
    assert client.get("/api/task-search?since=2026-02-01&until=2026-01-01",
                      headers=headers).status_code == 422


def test_report_omits_thinking_paths_and_credentials(
    client: TestClient, settings: Settings,
) -> None:
    """下载固定投影，不因模型返回嵌套字段而包含推理或管理凭据。"""

    store, _repository_id = populate(client, settings, 1)
    job = store.next_job()
    assert job is not None
    payload: dict[str, Any] = {"comments": [{"path": "a.py", "content": settings.admin_token,
                                            "thinking": "private-reasoning"}],
                               "manifest": {"terminal_state": "complete", "coverage": {
                                   "selected": [{"thinking": "private-reasoning"}],
                               }}}
    store.finish_job(job["id"], "complete", "/private/internal/result.json", payload, None)
    assert client.get("/api/jobs/1/report").status_code == 401
    response = client.get("/api/jobs/1/report", headers={"X-Admin-Token": settings.admin_token})
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    for secret in (settings.admin_token, "private-reasoning", "/private/internal"):
        assert secret not in response.text
    assert "[REDACTED]" in response.text
