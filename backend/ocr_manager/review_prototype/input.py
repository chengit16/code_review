"""冻结临时 Git 仓库的差异并提供分页取证，不读取分支当前内容或运行待审代码。"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from unidiff import PatchSet

Side = Literal["base", "head"]


def git(root: Path, *args: str) -> str:
    """在隔离夹具中执行 Git 参数数组；禁用外部 Git 配置和替代对象。"""
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    return subprocess.run(
        ["git", "--no-replace-objects", "-c", "core.hooksPath=/dev/null",
         "-c", "commit.gpgsign=false", "-c", "core.quotePath=false", *args],
        cwd=root, env=env, check=True, capture_output=True, encoding="utf-8", timeout=10,
    ).stdout


@dataclass(frozen=True)
class DiffLine:
    """单条差异内容及其在新旧侧的实际行号。"""

    text: str
    base_line: int | None
    head_line: int | None

    def number(self, side: Side) -> int | None:
        """按指定侧取行号，新增和删除行只存在于实际所在侧。"""
        return self.base_line if side == "base" else self.head_line


@dataclass(frozen=True)
class DiffHunk:
    """冻结输入内的差异块，重读时使用块编号与块内偏移。"""

    hunk_id: int
    path: str
    lines: tuple[DiffLine, ...]


@dataclass(frozen=True)
class ReviewInput:
    """固定双提交输入、差异及本轮规则和背景摘要；不保留工作区路径。"""

    repository_id: str
    base_sha: str
    head_sha: str
    rule_digest: str
    context_digest: str
    hunks: tuple[DiffHunk, ...]
    excluded_paths: tuple[str, ...]
    schema_version: int = 1
    mode: Literal["commit_range"] = "commit_range"

    def encode(self) -> str:
        """规范化为 SQLite 可保存的输入文档。"""
        return json.dumps(asdict(self), sort_keys=True, ensure_ascii=False)

    @property
    def key(self) -> str:
        """对实际差异、提交和输入策略计算内容身份。"""
        return hashlib.sha256(self.encode().encode()).hexdigest()

    def read_diff(self, hunk_id: int, offset: int, limit: int) -> DiffPage:
        """只从冻结清单读取一页；返回半开区间和下一页偏移。"""
        if not 1 <= hunk_id <= len(self.hunks) or limit < 1:
            raise ValueError("差异块或分页大小超出范围")
        hunk = self.hunks[hunk_id - 1]
        if not 0 <= offset < len(hunk.lines):
            raise ValueError("差异块偏移超出范围")
        end = min(offset + limit, len(hunk.lines))
        return DiffPage(hunk_id, hunk.path, offset, end, len(hunk.lines), hunk.lines[offset:end])


@dataclass(frozen=True)
class DiffPage:
    """差异块实际返回的范围，末尾未返回时可以按 next_offset 续读。"""

    hunk_id: int
    path: str
    start: int
    end: int
    total: int
    lines: tuple[DiffLine, ...]

    @property
    def next_offset(self) -> int | None:
        """有未读取的行时返回下一页位置。"""
        return self.end if self.end < self.total else None


def freeze_input(
    root: Path, repository_id: str, base_sha: str, head_sha: str, *,
    rule_digest: str, context_digest: str,
) -> ReviewInput:
    """仅接受完整提交标识；固定文件清单、差异块和排除路径。"""
    # 1. 先确认两个标识都是提交对象，拒绝分支名、标签和缩写。
    for sha in (base_sha, head_sha):
        if not re.fullmatch(r"[a-f0-9]{40}|[a-f0-9]{64}", sha):
            raise ValueError("需要完整提交 SHA")
        if git(root, "cat-file", "-t", sha).strip() != "commit":
            raise ValueError("评审范围必须引用提交")
    # 2. 用实际差异生成永久编号；无文本差异的条目保留在排除清单。
    patch = PatchSet(git(
        root, "diff", "--no-ext-diff", "--no-textconv", "--no-renames", "--no-color",
        "--src-prefix=a/", "--dst-prefix=b/", "--unified=3", base_sha, head_sha, "--",
    ))
    hunks: list[DiffHunk] = []
    excluded: list[str] = []
    for file in patch:
        if not file:
            excluded.append(file.path)
        for hunk in file:
            lines = tuple(
                DiffLine(line.value, line.source_line_no, line.target_line_no)
                for line in hunk if line.is_added or line.is_removed or line.is_context
            )
            hunks.append(DiffHunk(len(hunks) + 1, file.path, lines))
    return ReviewInput(
        repository_id, base_sha, head_sha, rule_digest, context_digest,
        tuple(hunks), tuple(excluded),
    )
