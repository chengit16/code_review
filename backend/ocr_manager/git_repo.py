"""维护受控本地 Git 仓库并以不可变 SHA 确定审查输入。"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any


class GitRepository:
    """只执行参数数组形式的 Git 命令，工作目录固定在服务数据目录。"""

    def __init__(self, root: Path, repository: dict[str, Any]) -> None:
        self.path = root / "repositories" / str(repository["id"])
        self.remote_url = str(repository["remote_url"])
        self.branch = str(repository["target_branch"])

    def _git(self, *args: str, cwd: Path | None = None) -> str:
        """执行有截止时间的 Git 查询，保留可诊断的 stderr。"""

        result = subprocess.run(
            ["git", "-c", "core.hooksPath=/dev/null", *args],
            cwd=cwd or self.path,
            env=self._git_environment(),
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(f"Git 命令失败：{result.stderr.strip()[:500]}")
        return result.stdout.strip()

    def _git_environment(self) -> dict[str, str]:
        """隔离服务用户的 Git 过滤器和 hooks；SSH deploy key 仍由 SSH 自身管理。"""

        return os.environ.copy() | {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
        }

    def _commit_sha(self, sha: str) -> str:
        """仅允许完整 SHA 作为 Git 对象参数，阻止外部数据解释成命令选项。"""

        if not re.fullmatch(r"[0-9a-fA-F]{40}", sha):
            raise ValueError("Git 提交 SHA 无效")
        return sha

    def fetch(self) -> None:
        """初次克隆或更新目标分支；历史必须完整才能比较 merge 父提交。"""

        if not (self.path / ".git").exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._git(
                "clone", "--no-checkout", self.remote_url, str(self.path), cwd=self.path.parent
            )
        # 明确使用已配置的只读地址，避免本地仓库 origin 被改写后拉取别处代码。
        self._git(
            "fetch", self.remote_url, f"+refs/heads/{self.branch}:refs/remotes/origin/{self.branch}"
        )

    def check_access(self) -> None:
        """验证只读 Git 访问和目标分支存在，不创建评审任务。"""

        self.fetch()
        self._git("rev-parse", "--verify", f"refs/remotes/origin/{self.branch}^{{commit}}")

    def is_on_target(self, sha: str) -> bool:
        """确保 webhook 或 MR API 指向的提交属于配置目标分支。"""

        sha = self._commit_sha(sha)
        result = subprocess.run(
            [
                "git",
                "-c",
                "core.hooksPath=/dev/null",
                "merge-base",
                "--is-ancestor",
                sha,
                f"origin/{self.branch}",
            ],
            cwd=self.path,
            env=self._git_environment(),
            capture_output=True,
            timeout=30,
            check=False,
        )
        if result.returncode not in (0, 1):
            raise RuntimeError("无法验证提交与目标分支的关系")
        return result.returncode == 0

    def merge_commits(self, merge_sha: str) -> list[str]:
        """按第一父基准列出普通 merge 本次引入的所有提交。"""

        merge_sha = self._commit_sha(merge_sha)
        parents = self._git("rev-list", "--parents", "-n", "1", merge_sha).split()
        if len(parents) < 3:
            raise ValueError("GitLab 提供的 merge SHA 不是合并提交")
        return self._git(
            "rev-list", "--reverse", "--topo-order", f"{merge_sha}^1..{merge_sha}"
        ).splitlines()

    def order_commits(self, commits: list[str]) -> list[str]:
        """将 fast-forward 的 MR 提交按祖先顺序排列并去重。"""

        unique = {self._commit_sha(sha) for sha in commits}
        if not unique:
            return []
        output = self._git("rev-list", "--reverse", "--topo-order", f"origin/{self.branch}")
        return [sha for sha in output.splitlines() if sha in unique]

    def rule_digest(self, sha: str) -> str:
        """取指定提交中规则文件的 Git blob 摘要；缺失规则使用稳定空摘要。"""

        sha = self._commit_sha(sha)
        return self._git("ls-tree", "--object-only", sha, "--", ".opencodereview/rule.json")

    def checkout(self, sha: str, target: Path) -> None:
        """为 OCR 建立与目标 SHA 一致的隔离工作目录。"""

        sha = self._commit_sha(sha)
        target.parent.mkdir(parents=True, exist_ok=True)
        self._git("worktree", "add", "--detach", str(target), sha)

    def remove_checkout(self, target: Path) -> None:
        """评审结束后释放 worktree，原始结果工件仍保留。"""

        if target.exists():
            self._git("worktree", "remove", "--force", str(target))
