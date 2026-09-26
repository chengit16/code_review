"""验证 GitLab 连接测试使用只读凭据访问准确的项目与目标分支。"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from ocr_manager import gitlab
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
