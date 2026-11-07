"""用临时 Git 对象验证严格换行分析与限额；不访问真实仓库或模型。"""

from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from ocr_manager import ocr, range_preflight
from ocr_manager.cancellation import ReviewCancelled, cancellation_scope
from ocr_manager.config import Settings
from ocr_manager.range_preflight import INPUT_POLICY, inspect_range, save_preflight
from ocr_manager.review_failures import ReviewFailure


def git(root: Path, *args: str) -> str:
    """只在临时合成仓库执行参数数组命令，并固定测试作者与换行配置。"""

    return subprocess.check_output(["git", "-c", "core.autocrlf=false", *args], cwd=root,
                                   text=True, stderr=subprocess.DEVNULL).strip()


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    """隔离测试仓库，无远程地址或用户脚本。"""

    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.name", "合成作者")
    git(tmp_path, "config", "user.email", "synthetic@example.invalid")
    return tmp_path


def commit(root: Path, message: str) -> str:
    """提交合成字节，测试生产实现不创建或修改任何提交。"""

    git(root, "add", "--all")
    git(root, "commit", "-qm", message)
    return git(root, "rev-parse", "HEAD")


def test_strict_newline_detection_preserves_all_other_changes(repository: Path) -> None:
    """换行混逻辑、缩进、末尾换行、二进制、增删、权限和符号链接均不获免审。"""

    before = {"pure space,名.py": b"x=1\ny=2\n", "mixed.py": b"x=1\n",
              "indent.py": b" x=1\n", "eof.py": b"x=1\n", "binary.py": b"\0x\n",
              "mode.py": b"x=1\n", "delete.py": b"x=1\n", "rename.py": b"x=1\n"}
    for name, content in before.items():
        (repository / name).write_bytes(content)
    (repository / "link").symlink_to("mixed.py")
    base = commit(repository, "base")
    after = {"pure space,名.py": b"x=1\r\ny=2\r\n", "mixed.py": b"x=2\r\n",
             "indent.py": b"  x=1\r\n", "eof.py": b"x=1", "binary.py": b"\0x\r\n",
             "mode.py": b"x=1\r\n", "new.py": b"x=1\r\n"}
    for name, content in after.items():
        (repository / name).write_bytes(content)
    (repository / "mode.py").chmod(0o755)
    (repository / "delete.py").unlink()
    (repository / "rename.py").rename(repository / "renamed.py")
    (repository / "link").unlink()
    (repository / "link").symlink_to("indent.py")
    head = commit(repository, "head")
    report = inspect_range(repository, head, base)
    assert report["status"] == "complete"
    assert report["newline_only_paths"] == ["pure space,名.py"]
    assert report["filter_enabled"] is False and report["excluded_count"] == 0
    assert git(repository, "status", "--porcelain") == ""
    save_preflight(repository / "evidence", report)
    path = repository / "evidence/scope-analysis.json"
    assert path.stat().st_mode & 0o777 == 0o600
    assert b"x=1" not in path.read_bytes()


def test_commit_first_parent_empty_root_and_fixed_input(repository: Path) -> None:
    """根提交无父对象、空范围和当前 HEAD 移动不改变固定范围的分析结论。"""

    (repository / "a.py").write_bytes(b"x=1\n")
    base = commit(repository, "root")
    assert inspect_range(repository, base)["newline_only_count"] == 0
    (repository / "a.py").write_bytes(b"x=1\r\n")
    head = commit(repository, "newline")
    (repository / "a.py").write_bytes(b"different\n")
    commit(repository, "later")
    assert inspect_range(repository, head)["newline_only_paths"] == ["a.py"]
    assert inspect_range(repository, head, head)["original_count"] == 0


def test_preflight_limits_and_unknown_inputs_keep_files_included(
    repository: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """字节和路径预算只限制分析，不能把未检查部分推断为纯换行。"""

    for name in ("a.py", "b.py"):
        (repository / name).write_bytes(b"x=1\n")
    base = commit(repository, "base")
    for name in ("a.py", "b.py"):
        (repository / name).write_bytes(b"x=1\r\n")
    head = commit(repository, "head")
    monkeypatch.setitem(INPUT_POLICY, "max_paths", 1)
    report = inspect_range(repository, head, base)
    assert report["status"] == "limited" and report["newline_only_count"] == 1
    monkeypatch.setitem(INPUT_POLICY, "max_blob_bytes", 2)
    assert inspect_range(repository, head, base)["newline_only_count"] == 0
    assert inspect_range(repository, "--all")["status"] == "unavailable"
    with cancellation_scope(lambda: False):
        assert inspect_range(repository, head, base)["filter_enabled"] is False
    with pytest.raises(ReviewCancelled), cancellation_scope(lambda: True):
        inspect_range(repository, head, base)


def test_preflight_does_not_execute_external_diff(repository: Path) -> None:
    """仓库配置的外部 diff 和 textconv 不得在预检中执行。"""

    (repository / "a.py").write_bytes(b"x\n")
    base = commit(repository, "base")
    (repository / "a.py").write_bytes(b"x\r\n")
    head = commit(repository, "head")
    marker = repository / "executed"
    script = repository / "malicious.sh"
    script.write_text(f"#!/bin/sh\ntouch '{marker}'\n")
    script.chmod(0o755)
    git(repository, "config", "diff.external", str(script))
    report = inspect_range(repository, head, base)
    assert report["newline_only_paths"] == ["a.py"] and not marker.exists()


def test_submodule_type_change_and_total_byte_limit_remain_unconfirmed(
    repository: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """子模块、普通文件变符号链接与总字节预算不能被换行分析绕过。"""

    (repository / "a.py").write_bytes(b"x\n")
    base = commit(repository, "base")
    git(repository, "update-index", "--add", "--cacheinfo", f"160000,{base},module")
    git(repository, "commit", "-qm", "submodule")
    middle = git(repository, "rev-parse", "HEAD")
    (repository / "a.py").unlink()
    (repository / "a.py").symlink_to("elsewhere.py")
    head = commit(repository, "type")
    assert inspect_range(repository, head, base)["newline_only_count"] == 0
    (repository / "a.py").unlink()
    (repository / "a.py").write_bytes(b"x\r\n")
    final = commit(repository, "newlines")
    monkeypatch.setitem(INPUT_POLICY, "max_total_bytes", 1)
    report = inspect_range(repository, final, middle)
    assert report["newline_only_count"] == 0 and report["status"] == "limited"


@pytest.mark.parametrize("preview", [
    {"reviewable_count": 0, "files": [{"path": "a.py", "will_review": True}]},
    {"reviewable_count": 1, "files": [{"path": "a.py"}]},
    {"reviewable_count": 2, "files": [{"path": "a.py", "will_review": True}] * 2},
])
def test_preview_cannot_lie_about_selected_paths(tmp_path: Path, preview: dict[str, Any]) -> None:
    """预览分母和实际选中路径必须一致，不能因计数为零而假跳过。"""

    path = tmp_path / "preview.json"
    path.write_text(json.dumps(preview))
    with pytest.raises(ReviewFailure):
        ocr.read_preview(path)


def test_201_selected_files_fail_before_model(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """文件上限不是截断评审，预览超限时不启动正式模型命令。"""

    calls: list[list[str]] = []

    def execute(command: list[str], *_args: Any) -> tuple[int, str]:
        calls.append(command)
        if "--preview" in command:
            Path(command[command.index("--output") + 1]).write_text(json.dumps({
                "reviewable_count": 201, "files": [
                    {"path": f"{number}.py", "will_review": True} for number in range(201)]}))
        return 0, ""

    monkeypatch.setattr(ocr, "run_ocr_command", execute)
    with pytest.raises(ReviewFailure) as failure:
        ocr.run_review(replace(settings, ocr_max_files=200), tmp_path, tmp_path / "run", "a" * 40)
    assert failure.value.category == "scope_limit"
    assert len([command for command in calls if command[1] == "review"]) == 1
    assert all("--exclude" not in command for command in calls)


def test_stage_deadlines_are_short_and_share_total_budget(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """配置整体三十秒、预览六十秒，同时受项目总预算约束。"""

    now = [10.0]
    budgets: list[float] = []
    monkeypatch.setattr(range_preflight.time, "monotonic", lambda: now[0])

    def execute(command: list[str], *_args: Any) -> tuple[int, str]:
        budgets.append(_args[-1])
        now[0] += 5
        if "--preview" in command:
            Path(command[command.index("--output") + 1]).write_text(
                '{"reviewable_count":0,"files":[]}')
        return 0, ""

    monkeypatch.setattr(ocr, "run_ocr_command", execute)
    ocr.run_review(replace(settings, ocr_timeout_seconds=3600,
                           ocr_base_url="https://synthetic.invalid/v1"),
                   tmp_path, tmp_path / "run", "a" * 40)
    assert budgets == [30, 25, 20, 15, 60]
