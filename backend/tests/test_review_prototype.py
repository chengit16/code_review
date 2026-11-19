"""用合成提交验证隔离原型的覆盖、证据和结果版本，不加载业务配置。"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from contextlib import closing
from dataclasses import replace
from pathlib import Path

import pytest
from ocr_manager.review_prototype.demo import (
    ScriptedModel,
    create_fixture,
    run_demo,
    scripted_findings,
)
from ocr_manager.review_prototype.graph import ReadRequest, run_agent
from ocr_manager.review_prototype.input import DiffPage, freeze_input, git
from ocr_manager.review_prototype.result import Finding, ReviewResult
from ocr_manager.review_prototype.store import PrototypeStore


def test_demo_preserves_independent_results_and_coverage(tmp_path: Path) -> None:
    """检查可执行演示的真实输出和数据库，而非仅比较图节点的返回值。"""
    timeline: list[str] = []
    output = run_demo(tmp_path, timeline.append)
    protected, missing_guard, timeout, partial, complete = json.loads(output.read_text())
    assert protected["attempts"][1]["result"]["findings"] == []
    assert len(missing_guard["attempts"][1]["result"]["findings"]) == 1
    assert all(item["input"] == complete["input"] for item in (timeout, partial))
    assert all(item["attempts"][0] == timeout["attempts"][0] for item in (partial, complete))
    assert [item["attempts"][1]["status"] for item in (timeout, partial, complete)] == [
        "failed", "partial", "complete",
    ]
    assert timeout["attempts"][1]["result"]["coverage"] == [
        {"hunk_id": 1, "total": 25, "delivered_end": 5, "reviewed_end": 0},
    ]
    assert partial["attempts"][1]["result"]["coverage"][0]["reviewed_end"] == 5
    assert partial["attempts"][1]["result"]["findings"] == []
    result = complete["attempts"][1]["result"]
    assert result["coverage"][0]["reviewed_end"] == 25
    assert result["findings"][0]["evidence"]["line"] == 24
    assert complete["comparison"]["previous_id"] == partial["comparison"]["id"]
    assert any("[20,25)/25" in step for step in timeline)
    with closing(sqlite3.connect(tmp_path / "review.sqlite3")) as db:
        assert db.execute("SELECT count(*) FROM inputs").fetchone() == (3,)
        assert db.execute("SELECT count(*) FROM attempts").fetchone() == (8,)
        assert db.execute("SELECT count(*) FROM comparisons").fetchone() == (5,)
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_frozen_git_input_ignores_new_head_and_dirty_files(tmp_path: Path) -> None:
    """后续提交和未提交改动不会改变已记录的范围、证据或输入身份。"""
    root = tmp_path / "repo"
    snapshot = create_fixture(root, "unprotected")
    (root / "orders.py").write_text("changed at a later HEAD\n")
    git(root, "add", "--", "orders.py")
    git(root, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
        "commit", "-qm", "later commit")
    (root / "orders.py").write_text("dirty\n")
    reloaded = freeze_input(
        root, snapshot.repository_id, snapshot.base_sha, snapshot.head_sha,
        rule_digest=snapshot.rule_digest, context_digest=snapshot.context_digest,
    )
    assert reloaded == snapshot
    assert run_agent(reloaded, ScriptedModel(scripted_findings), page_lines=5, max_reads=3).findings
    with pytest.raises(ValueError, match="完整提交 SHA"):
        freeze_input(
            root, snapshot.repository_id, snapshot.base_sha, "HEAD",
            rule_digest=snapshot.rule_digest, context_digest=snapshot.context_digest,
        )


def test_reference_to_unread_real_line_fails_verification(tmp_path: Path) -> None:
    """即使行号真实存在，第一页模型也不能用末页从未收到的行作为证据。"""
    snapshot = create_fixture(tmp_path / "repo", "long_diff")
    finding, = scripted_findings(snapshot.read_diff(1, 20, 5))

    def cite_unread(_page: DiffPage) -> tuple[Finding, ...]:
        return (finding,)

    result = run_agent(snapshot, ScriptedModel(cite_unread), page_lines=5, max_reads=5)
    assert (result.status, result.reason, result.findings) == ("failed", "invalid_evidence", ())
    assert (result.coverage[0].delivered_end, result.coverage[0].reviewed_end) == (5, 0)


def test_model_cannot_jump_to_unplanned_offset(tmp_path: Path) -> None:
    """模型选错工具参数时，图直接失败且没有交付差异内容。"""
    snapshot = create_fixture(tmp_path / "repo", "long_diff")

    class JumpModel(ScriptedModel):
        def request_diff(self, available: ReadRequest) -> ReadRequest:
            return replace(available, offset=20)

    result = run_agent(snapshot, JumpModel(scripted_findings), page_lines=5, max_reads=5)
    assert (result.status, result.reason) == ("failed", "invalid_read_request")
    assert result.coverage[0].delivered_end == result.coverage[0].reviewed_end == 0


def test_request_conflicts_and_attempt_claim(tmp_path: Path) -> None:
    """同请求不同快照或配置不能混用；独立读连接可看到已提交的领取状态。"""
    snapshot = create_fixture(tmp_path / "repo", "protected")
    store = PrototypeStore.create(tmp_path / "review.sqlite3")
    comparison = store.enqueue(snapshot, request_key="same", configuration="cfg")
    assert store.enqueue(snapshot, request_key="same", configuration="cfg") == comparison
    with pytest.raises(ValueError, match="请求键已绑定"):
        store.enqueue(snapshot, request_key="same", configuration="other")
    with pytest.raises(ValueError, match="请求键已绑定"):
        store.enqueue(replace(snapshot, rule_digest="different"), request_key="same",
                      configuration="cfg")
    with pytest.raises(ValueError, match="两路已结束"):
        store.enqueue(snapshot, request_key="rerun", configuration="cfg", previous=comparison)

    def execute(run: Callable[[], ReviewResult], configuration: str) -> ReviewResult | None:
        return store.execute(
            comparison.agent_id, snapshot, "agent_fixture", run, configuration=configuration,
        )

    def unexpected() -> ReviewResult:
        pytest.fail("重复或不匹配的尝试不应运行")

    def inspect_running() -> ReviewResult:
        assert execute(unexpected, "cfg") is None
        report = PrototypeStore(store.path).report(comparison.id)
        attempts = report["attempts"]
        assert isinstance(attempts, list)
        assert [attempt["status"] for attempt in attempts] == ["queued", "running"]
        return run_agent(snapshot, ScriptedModel(scripted_findings), page_lines=5, max_reads=1)

    assert execute(unexpected, "wrong") is None
    assert execute(inspect_running, "cfg") is not None
    assert execute(unexpected, "cfg") is None
    with pytest.raises(FileExistsError):
        PrototypeStore.create(store.path)
