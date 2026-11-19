"""真实本地 Git 图验证 merge、squash、快进及 rebase 后的差异证明，不连接网络。"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from ocr_manager.config import Settings
from ocr_manager.git_repo import GitRepository
from ocr_manager.merge_review_reuse import merged_range
from ocr_manager.premerge import enqueue_premerge
from test_premerge import ADMIN, create_repository


@pytest.mark.parametrize("mode", ["merge", "squash", "ff", "rebase", "conflict"])
def test_exact_merged_diff_proof(
    client: TestClient,
    settings: Settings,
    tmp_path: Path,
    mode: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """相同净差异才复用；冲突解决引入未审变化时拒绝，二进制也纳入摘要。"""

    from ocr_manager.storage import Store

    rid = create_repository(client)
    client.put(f"/api/repositories/{rid}/premerge", headers=ADMIN, json={"enabled": True})
    root = tmp_path / "repositories" / str(rid)
    root.mkdir(parents=True)

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=root, check=True, capture_output=True, text=True
        ).stdout.strip()

    git("init", "-q", "-b", "main")
    git("config", "user.name", "合成测试")
    git("config", "user.email", "synthetic@example.invalid")
    (root / "app.txt").write_text("base\n")
    git("add", ".")
    git("commit", "-qm", "初始")
    base = git("rev-parse", "HEAD")
    git("checkout", "-qb", "feature")
    (root / "app.txt").write_text("reviewed\n")
    (root / "binary.bin").write_bytes(bytes([0, 1, 2, 255]))
    git("add", ".")
    git("commit", "-qm", "已审变更")
    head = git("rev-parse", "HEAD")
    git("checkout", "-q", "main")
    if mode in {"merge", "squash", "rebase", "conflict"}:
        (root / "unrelated.txt").write_text("其他目标分支变更")
        git("add", ".")
        git("commit", "-qm", "其他变更")
    before = git("rev-parse", "HEAD")
    if mode in {"merge", "conflict"}:
        git("merge", "--no-ff", "--no-commit", "feature")
        if mode == "conflict":
            (root / "app.txt").write_text("unreviewed conflict resolution\n")
        git("add", ".")
        git("commit", "-qm", "合并")
    elif mode == "squash":
        git("merge", "--squash", "feature")
        git("commit", "-qm", "压缩")
    elif mode == "rebase":
        git("checkout", "-q", "feature")
        git("rebase", "main")
        git("checkout", "-q", "main")
        git("merge", "--ff-only", "feature")
    else:
        git("merge", "--ff-only", "feature")
    after = git("rev-parse", "HEAD")
    git("update-ref", "refs/remotes/origin/main", after)
    store = Store(settings.data_dir / "app.db")
    assert enqueue_premerge(store, rid, 7, head)
    repository = store.get_repository(rid)
    assert repository
    adapter = GitRepository(tmp_path, repository)
    monkeypatch.setattr(adapter, "fetch_mr_head", lambda *_: None)
    mr: dict[str, Any] = {
        "iid": 7,
        "state": "merged",
        "sha": head,
        "target_project_id": 42,
        "target_branch": "main",
        "diff_refs": {"base_sha": base, "head_sha": head},
    }
    if mode == "squash":
        mr["squash_commit_sha"] = after
    elif mode != "ff":
        mr["merge_commit_sha"] = after

    class Client:
        """快进时固定 GitLab 提交列表。"""

        def list_commits(self, *_: Any) -> list[str]:
            return [head]

    if mode == "conflict":
        with pytest.raises(ValueError, match="不一致"):
            merged_range(store, repository, mr, adapter, Client())
    else:
        assert merged_range(store, repository, mr, adapter, Client()) == (
            before,
            after,
            store.list_jobs()[0]["id"],
        )
        assert adapter.first_parent_range(before, after) == [after]
