"""验证 GitLab 提交引用在进入 Git 子进程前受到严格限制。"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from ocr_manager.git_repo import GitRepository


def test_invalid_commit_ref_never_reaches_git(tmp_path: Path) -> None:
    """参数数组仍可能接受 Git 选项，外部 SHA 必须先通过格式校验。"""

    git = GitRepository(
        tmp_path,
        {"id": 1, "remote_url": "git@example.test:team/repo.git", "target_branch": "main"},
    )
    with pytest.raises(ValueError, match="SHA"):
        git.is_on_target("--help")
    with pytest.raises(ValueError, match="SHA"):
        git.merge_commits("main")
    with pytest.raises(ValueError, match="SHA"):
        git.order_commits(["a" * 40, "--help"])
    with pytest.raises(ValueError, match="SHA"):
        git.checkout("bad", tmp_path / "checkout")


def test_rule_digest_tracks_content_at_each_commit(tmp_path: Path) -> None:
    """规则摘要绑定目标提交内容，后续分支规则变化不改写旧评审输入。"""

    root = tmp_path / "repositories" / "1"
    root.mkdir(parents=True)

    def command(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, check=True
        ).stdout.strip()

    command("init", "-q")
    command("config", "user.name", "Test")
    command("config", "user.email", "test@example.test")
    (root / "README.md").write_text("demo", encoding="utf-8")
    command("add", "README.md")
    command("commit", "-qm", "initial")
    first = command("rev-parse", "HEAD")
    rules = root / ".opencodereview" / "rule.json"
    rules.parent.mkdir()
    rules.write_text('{"level":"one"}', encoding="utf-8")
    command("add", ".opencodereview/rule.json")
    command("commit", "-qm", "add rules")
    second = command("rev-parse", "HEAD")
    rules.write_text('{"level":"two"}', encoding="utf-8")
    command("commit", "-qam", "change rules")
    third = command("rev-parse", "HEAD")

    git = GitRepository(
        tmp_path,
        {"id": 1, "remote_url": "git@example.test:team/repo.git", "target_branch": "main"},
    )
    assert git.rule_digest(first) == ""
    assert git.rule_digest(second) != git.rule_digest(third)
    assert git.rule_digest(second) == command("rev-parse", f"{second}:.opencodereview/rule.json")
