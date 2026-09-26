"""通过只读 GitLab API 查询合并结果和 MR 提交列表。"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from urllib.parse import quote, urlparse

import httpx


class GitLabClient:
    """统一 GitLab API 认证、超时与分页，避免信任 webhook 中的提交范围。"""

    def __init__(self, base_url: str, token: str) -> None:
        if not token:
            raise RuntimeError("缺少 GitLab API 只读凭据")
        self.base_url = base_url.rstrip("/")
        self.token = token

    def check_access(self, project_id: int, branch: str, remote_url: str) -> None:
        """确认只读凭据、项目路径与目标分支一致，防止 SSH 指向同实例的别处仓库。"""

        branch_path = quote(branch, safe="")
        base = f"{self.base_url}/api/v4/projects/{project_id}"
        with httpx.Client(timeout=20, headers={"PRIVATE-TOKEN": self.token}) as client:
            project = client.get(base)
            project.raise_for_status()
            branch_response = client.get(f"{base}/repository/branches/{branch_path}")
            branch_response.raise_for_status()
        project_data = project.json()
        branch_data = branch_response.json()
        if not isinstance(project_data, dict) or not isinstance(branch_data, dict):
            raise ValueError("GitLab 项目或目标分支响应无效")
        scp = re.fullmatch(r"git@[^:]+:(.+)", remote_url)
        remote_path = scp.group(1) if scp else urlparse(remote_url).path.lstrip("/")
        expected_path = project_data.get("path_with_namespace")
        if (
            project_data.get("id") != project_id
            or branch_data.get("name") != branch
            or not isinstance(expected_path, str)
            or remote_path.removesuffix(".git") != expected_path
        ):
            raise ValueError("GitLab 项目或目标分支与配置不符")

    def get_merge_request(self, project_id: int, mr_iid: int) -> dict[str, Any]:
        """从 GitLab 重新读取 MR 末态与最终合并 SHA。"""

        url = f"{self.base_url}/api/v4/projects/{project_id}/merge_requests/{mr_iid}"
        with httpx.Client(timeout=20, headers={"PRIVATE-TOKEN": self.token}) as client:
            response = client.get(url)
            response.raise_for_status()
            data = response.json()
        if not isinstance(data, dict):
            raise ValueError("GitLab MR 响应无效")
        return data

    def list_commits(self, project_id: int, mr_iid: int) -> list[str]:
        """读取完整 MR 提交列表，不把第一页误当成全部范围。"""

        url = f"{self.base_url}/api/v4/projects/{project_id}/merge_requests/{mr_iid}/commits"
        commits: list[str] = []
        page = 1
        with httpx.Client(timeout=20, headers={"PRIVATE-TOKEN": self.token}) as client:
            while True:
                response = client.get(url, params={"per_page": 100, "page": page})
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, list):
                    raise ValueError("GitLab MR 提交响应无效")
                for item in data:
                    if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                        raise ValueError("GitLab MR 提交 SHA 无效")
                    commits.append(item["id"])
                next_page = response.headers.get("x-next-page", "")
                if not next_page:
                    return commits
                page = int(next_page)

    def list_merged_requests(
        self, project_id: int, since: datetime, until: datetime
    ) -> list[int]:
        """扫描更新过的已合并 MR，按 merged_at 二次过滤；最多 100 页防止无界任务。"""

        url = f"{self.base_url}/api/v4/projects/{project_id}/merge_requests"
        result: list[int] = []
        with httpx.Client(timeout=20, headers={"PRIVATE-TOKEN": self.token}) as client:
            for page in range(1, 101):
                response = client.get(url, params={"state": "merged", "updated_after":
                                      since.isoformat(), "per_page": 100, "page": page})
                response.raise_for_status()
                rows = response.json()
                if not isinstance(rows, list):
                    raise ValueError("GitLab MR 列表响应无效")
                for row in rows:
                    if not isinstance(row, dict) or not isinstance(row.get("iid"), int):
                        raise ValueError("GitLab MR 列表缺少 IID")
                    raw = row.get("merged_at")
                    if not isinstance(raw, str):
                        raise ValueError("GitLab MR 列表缺少合并时间")
                    merged = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                    if since <= merged <= until:
                        result.append(row["iid"])
                next_page = response.headers.get("x-next-page", "")
                if not next_page:
                    return result
            raise ValueError("补审范围超过 100 页，请缩小时间区间")


def project_web_url(gitlab_url: str, remote_url: str) -> str:
    """从已验证的 SSH remote 生成 GitLab 项目页面地址，供评审链接使用。"""

    scp = re.fullmatch(r"git@[^:]+:(.+)", remote_url)
    remote_path = scp.group(1) if scp else urlparse(remote_url).path.lstrip("/")
    return f"{gitlab_url.rstrip('/')}/{quote(remote_path.removesuffix('.git'), safe='/-_.~')}"
