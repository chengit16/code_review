"""验证 GitLab 连接测试使用只读凭据访问准确的项目与目标分支。"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from ocr_manager import gitlab
from ocr_manager.execution_guard import WorkerStopping, stopping_scope
from ocr_manager.gitlab import GitLabClient, project_web_url


def test_check_access_encodes_branch_and_checks_project_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """分支斜杠按路径段编码，API 返回项目不匹配时不能报告连接成功。"""

    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.raw_path.endswith(b"release%2Fmain"):
            return httpx.Response(200, json={"name": "release/main"})
        return httpx.Response(200, json={"id": 42, "path_with_namespace": "team/repo"})

    original_client = httpx.Client

    def client(**kwargs: Any) -> httpx.Client:
        return original_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(gitlab.httpx, "Client", client)
    client = GitLabClient("https://gitlab.example.test", "private-api-token")
    client.check_access(42, "release/main", "git@gitlab.example.test:team/repo.git")
    assert len(requests) == 2
    assert all(request.headers["PRIVATE-TOKEN"] == "private-api-token" for request in requests)
    assert requests[1].url.raw_path.endswith(b"release%2Fmain")
    with pytest.raises(ValueError, match="不符"):
        client.check_access(41, "release/main", "git@gitlab.example.test:team/repo.git")
    with pytest.raises(ValueError, match="不符"):
        client.check_access(42, "release/main", "git@gitlab.example.test:other/repo.git")


def test_project_web_url_supports_ssh_remote_forms() -> None:
    """网页链接应指向仓库 namespace，而非 GitLab API 的项目数字 ID。"""

    base = "https://gitlab.example.test/team/repo"
    assert (
        project_web_url("https://gitlab.example.test", "git@gitlab.example.test:team/repo.git")
        == base
    )
    assert (
        project_web_url(
            "https://gitlab.example.test", "ssh://git@gitlab.example.test/team/repo.git"
        )
        == base
    )


@pytest.mark.parametrize("method", ["commits", "backfill", "diffs", "discussion"])
def test_worker_stop_between_gitlab_pages_does_not_issue_next_request(
    monkeypatch: pytest.MonkeyPatch, method: str,
) -> None:
    """停止只等待当前 HTTP 边界，不继续扫描后续百页或继续发布评论。"""

    stopping = threading.Event()
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        stopping.set()
        return httpx.Response(200, json=[], headers={"x-next-page": "2"})

    original_client = httpx.Client
    monkeypatch.setattr(gitlab.httpx, "Client", lambda **kwargs: original_client(
        transport=httpx.MockTransport(handler), **kwargs))
    client = GitLabClient("https://gitlab.example.test", "synthetic-token")
    with stopping_scope(stopping), pytest.raises(WorkerStopping):
        if method == "commits":
            client.list_commits(42, 7)
        elif method == "backfill":
            client.list_merged_requests(42, datetime(2026, 1, 1, tzinfo=UTC),
                                        datetime(2026, 1, 2, tzinfo=UTC))
        elif method == "diffs":
            client.list_merge_request_diffs(42, 7)
        else:
            client.post_inline_discussion(42, 7, "合成评论", {}, "synthetic-marker")
    assert len(calls) == 1
