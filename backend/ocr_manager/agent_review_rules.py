"""用初审版本的 OCR CLI 解析规则。仅从冻结快照和 Git 普通文件取数，不运行模型。"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Literal

from pydantic import BaseModel

from ocr_manager.agent_review_config import OCR_RULE_SNAPSHOT_KEYS
from ocr_manager.config import Settings
from ocr_manager.ocr import command_fingerprint
from ocr_manager.ocr_commands import execute_ocr_command
from ocr_manager.range_preflight import read_git_objects

RULE_PATH = ".opencodereview/rule.json"
MAX_RULE_BYTES = 32_000
RULE_FILE_EXTENSIONS = {".md", ".txt", ".markdown"}


@dataclass(frozen=True)
class FileRule:
    """规则正文仅活在 Worker 内存，持久化按文件记录来源和内容摘要。"""

    source: str
    pattern: str
    text: str = field(repr=False)

    def evidence(self) -> dict[str, str]:
        """只返回可在比较页公开的规则版本字段。"""

        return {"source": self.source, "pattern": self.pattern,
                "sha256": hashlib.sha256(self.text.encode()).hexdigest()}


class _Group(BaseModel):
    source: str
    pattern: str
    files: list[str]
    rule: str


class _Delegation(BaseModel):
    schema_version: Literal["1"]
    groups: list[_Group]


def _blob(root: Path, sha: str, path: str, deadline: float) -> tuple[str, bytes] | None:
    entry = read_git_objects(
        root, ["--literal-pathspecs", "ls-tree", "--format=%(objectmode) %(objectname)",
               sha, "--", path], deadline, 256,
    )
    if not entry:
        return None
    mode, object_id = entry.decode("ascii").split()
    if mode not in {"100644", "100755"}:
        raise ValueError("仓库规则必须是冻结提交中的普通文件")
    return object_id, read_git_objects(root, ["cat-file", "blob", object_id],
                                      deadline, MAX_RULE_BYTES)


def _stage_rule(
    content: bytes, location: Path, *, checkout: tuple[Path, Path, str] | None = None,
) -> None:
    # 固定版本 OCR 将无空格的单行 .md/.txt/.markdown 视作文件引用。
    # 仅仓库层具有可核对的 Git 文件身份，托管层引用无法从规则 JSON 还原。
    if len(content) > MAX_RULE_BYTES:
        raise ValueError("初审规则超过解析上限")
    document = json.loads(content)
    if (not isinstance(document, dict) or not document.keys() <= {"rules", "include", "exclude"}
            or not isinstance(document.get("rules", []), list)):
        raise ValueError("初审规则文档无效")
    deadline = time.monotonic() + 10
    for entry in document.get("rules", []):
        if (not isinstance(entry, dict)
                or not entry.keys() <= {"path", "rule", "merge_system_rule"}
                or not isinstance(entry.get("rule"), str)):
            raise ValueError("初审规则条目无效")
        rule = entry["rule"]
        path = PurePosixPath(rule)
        _, dot, extension = rule.rsplit("/", 1)[-1].rpartition(".")
        if "\n" in rule or " " in rule or dot + extension.lower() not in RULE_FILE_EXTENSIONS:
            continue
        if (checkout is None or path.is_absolute()
                or {"..", ".git"}.intersection(part.lower() for part in path.parts)
                or "\\" in rule or any(ord(char) < 32 for char in rule)):
            raise ValueError("初审规则引用了无法冻结的路径")
        repo, root, sha = checkout
        target = repo / path
        blob = _blob(root, sha, path.as_posix(), deadline)
        if blob is None:
            raise ValueError("初审仓库规则引用的文件不可用")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob[1])
    location.parent.mkdir(parents=True, exist_ok=True)
    location.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")


def resolve_file_rules(
    settings: Settings, root: Path, *, ocr_snapshot: str, checkout_sha: str,
    head_sha: str, paths: tuple[str, ...],
) -> dict[str, FileRule]:
    """按历史 OCR 安装及层级解析规则，确保每个差异路径都有明确结果。"""

    if not paths:
        return {}
    snapshot = json.loads(ocr_snapshot)
    if not isinstance(snapshot, dict) or not OCR_RULE_SNAPSHOT_KEYS <= snapshot.keys():
        raise ValueError("初审规则快照不完整")
    installed = command_fingerprint(settings.ocr_command)
    if "path" not in installed or installed != snapshot["command"]:
        raise ValueError("初审 OCR 规则引擎版本不可用")
    deadline = time.monotonic() + 10
    head_rule = _blob(root, head_sha, RULE_PATH, deadline)
    if (head_rule[0] if head_rule else "") != snapshot["rule_digest"]:
        raise ValueError("初审仓库规则版本不一致")
    checkout_rule = (head_rule if checkout_sha == head_sha
                     else _blob(root, checkout_sha, RULE_PATH, deadline))
    # 在临时 Git 仓库中解析，OCR 仅获得规则所需的文件和干净环境。
    with TemporaryDirectory(prefix="ocr-agent-rules-") as temporary:
        scratch = Path(temporary)
        repo, isolated_home = scratch / "repo", scratch / "home"
        repo.mkdir()
        isolated_home.mkdir()
        env = {"PATH": os.environ.get("PATH", os.defpath), "HOME": str(isolated_home),
               "OCR_NO_UPDATE": "1", "GIT_CONFIG_GLOBAL": os.devnull,
               "GIT_CONFIG_NOSYSTEM": "1"}
        code, _, _ = execute_ocr_command(["git", "init", "-q", "--template="], env, repo, 5)
        if code:
            raise ValueError("无法初始化规则解析目录")
        arguments = [installed["path"], "delegate", "rule", "--format", "json",
                     "--repo", str(repo)]
        project, global_rule = snapshot["project_rule"], snapshot["global_rule"]
        # OCR 匹配未命中时会继续查找下一层。完整恢复各层，交给其原生解析器选择。
        if global_rule is not None:
            if not isinstance(global_rule, str):
                raise ValueError("初审全局规则无效")
            _stage_rule(global_rule.encode(), isolated_home / RULE_PATH)
        if checkout_rule is not None:
            _stage_rule(checkout_rule[1], repo / RULE_PATH, checkout=(repo, root, checkout_sha))
        if project is not None:
            if not isinstance(project, str):
                raise ValueError("初审项目规则无效")
            location = scratch / "managed-rule.json"
            _stage_rule(project.encode(), location)
            arguments.extend(("--rule", str(location)))
        result = {}
        for path in paths:
            # OCR 的 .m 内置规则会检查文件头以区分 Objective-C 与 MATLAB。
            file_path = PurePosixPath(path)
            if file_path.suffix.lower() == ".m":
                if file_path.is_absolute() or {"..", ".git"}.intersection(file_path.parts):
                    raise ValueError("差异路径非法")
                file = _blob(root, head_sha, path, time.monotonic() + 5)
                if file is not None:
                    target = repo / file_path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(file[1])
            code, output, _ = execute_ocr_command([*arguments, "--", path], env, repo, 5)
            if code:
                raise ValueError("OCR 无法解析历史评审规则")
            group, = _Delegation.model_validate_json(output).groups
            if group.files != [path] or len(group.rule.encode()) > MAX_RULE_BYTES:
                raise ValueError("OCR 规则输出与固定差异不匹配")
            result[path] = FileRule(group.source, group.pattern, group.rule)
        return result
