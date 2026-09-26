"""验证行内位置、默认关闭、独立重试与重复投递防护；不访问真实 GitLab。"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from ocr_manager.config import Settings
from ocr_manager.gitlab import GitLabClient
from ocr_manager.publications import inline_position, next_publication, publish_one
from ocr_manager.secrets import SecretBox
from test_task_operations import populate

ADMIN = {"X-Admin-Token": "test-admin-token"}
REFS = {"base_sha": "a" * 40, "start_sha": "b" * 40, "head_sha": "c" * 40}
DIFF = [{"old_path": "app.py", "new_path": "app.py",
         "diff": "@@ -1,1 +1,2 @@\n old\n+added\n"}]


def test_inline_position_only_added_lines() -> None:
    """MR diff 中的新增行才具备可信定位，文件级和旧行跳过。"""

    mr = {"diff_refs": REFS}
    position = inline_position(mr, DIFF, {"path": "app.py", "start_line": 2})
    assert position and position["new_line"] == "2"
    assert inline_position(mr, DIFF, {"path": "app.py", "start_line": 1}) is None
    assert inline_position(mr, DIFF, {"path": "app.py", "start_line": 0}) is None


def test_publication_queue_is_independent(client: TestClient, settings: Settings,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
    """关闭时不建发布项；开启后只发布一次，未知位置记录跳过且不重跑 OCR。"""

    store, repository_id = populate(client, settings, 2)
    with store.connection() as db:
        db.execute("UPDATE repositories SET gitlab_token_ciphertext=? WHERE id=?",
                   (SecretBox(settings.master_key).encrypt("synthetic-token"), repository_id))
    assert client.get(f"/api/repositories/{repository_id}/gitlab-publication",
                      headers=ADMIN).json() == {"enabled": False}
    assert client.put(f"/api/repositories/{repository_id}/gitlab-publication", headers=ADMIN,
                      json={"enabled": True}).status_code == 200
    job = store.next_job()
    assert job and job["id"] == 1
    store.finish_job(1, "complete", None, {"comments": [
        {"path": "app.py", "start_line": 2, "content": "发现"},
        {"path": "app.py", "start_line": 1, "content": "旧行"},
    ]}, None)
    calls: list[tuple[str, str]] = []

    class FakeGitLab:
        """只记录已验证位置的发布调用。"""

        def __init__(self, _base: str, _token: str) -> None:
            pass

        def get_merge_request(self, _project: int, _iid: int) -> dict[str, Any]:
            return {"state": "merged", "target_project_id": 42,
                    "target_branch": "main", "diff_refs": REFS}

        def list_merge_request_diffs(self, _project: int, _iid: int) -> list[dict[str, Any]]:
            return DIFF

        def post_inline_discussion(self, _project: int, _iid: int, body: str,
                                   position: dict[str, str], marker: str) -> str:
            calls.append((body, position["new_line"]))
            assert marker.startswith("<!-- open-code-review:")
            return "discussion-1"

    monkeypatch.setattr("ocr_manager.publications.GitLabClient", FakeGitLab)
    first = next_publication(store)
    assert first
    publish_one(store, settings, first)
    second = next_publication(store)
    assert second
    publish_one(store, settings, second)
    assert next_publication(store) is None
    assert calls == [("发现", "2")]
    detail = store.get_job(1)
    assert detail is not None
    states = [item["status"] for item in detail["publications"]]
    assert states == ["sent", "skipped"]
    assert client.post("/api/jobs/1/gitlab-publications/prepare", headers=ADMIN).json() == {
        "created": 0}
    assert detail["delivery"]["status"] == "pending"


def test_discussion_retry_recognizes_previous_post(monkeypatch: pytest.MonkeyPatch) -> None:
    """服务端已创建但响应丢失时按 marker 查找，不重复调用 POST。"""

    marker = "<!-- open-code-review:1:1:0 -->"
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        return httpx.Response(200, json=[{"id": "discussion-1", "notes": [
            {"body": f"发现\n\n{marker}"}]}])

    real = httpx.Client
    monkeypatch.setattr("ocr_manager.gitlab.httpx.Client", lambda **kwargs: real(
        transport=httpx.MockTransport(handler), **kwargs))
    result = GitLabClient("https://gitlab.example.test", "synthetic-token").post_inline_discussion(
        42, 7, "发现", {"position_type": "text"}, marker)
    assert result == "discussion-1" and calls == ["GET"]
