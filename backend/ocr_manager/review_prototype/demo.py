"""可重复的离线双评审演示；只操作新建临时 Git 仓库和独立 SQLite。"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ocr_manager.review_prototype.graph import ReadRequest, run_agent
from ocr_manager.review_prototype.input import DiffPage, ReviewInput, freeze_input, git
from ocr_manager.review_prototype.result import Evidence, Finding, HunkCoverage, ReviewResult, Step
from ocr_manager.review_prototype.store import OCR_FIXTURE_CONFIGURATION, Comparison, PrototypeStore

Scenario = Literal["protected", "unprotected", "long_diff"]
Log = Callable[[str], None]


def create_fixture(root: Path, scenario: Scenario) -> ReviewInput:
    """提交两份合成 Python 文本，订单函数只作差异输入，不运行。"""
    root.mkdir()
    git(root, "init", "-q")
    path = root / "orders.py"
    path.write_text("def retry_order(order_id):\n    pass\n", encoding="utf-8")
    base = _commit(root, "before retry change")
    padding = "    # 合成上下文\n" * 22 if scenario == "long_diff" else ""
    operation = "record_once" if scenario == "protected" else "record_order"
    path.write_text(
        f"def retry_order(order_id):\n{padding}    {operation}(order_id)\n", encoding="utf-8",
    )
    head = _commit(root, "synthetic retry change")
    return freeze_input(
        root, scenario, base, head,
        rule_digest="fixture-rule-v1", context_digest="fixture-context-v1",
    )


def _commit(root: Path, message: str) -> str:
    git(root, "add", "--", "orders.py")
    git(root, "-c", "user.name=Review Demo", "-c", "user.email=demo@example.invalid",
        "commit", "-qm", message)
    return git(root, "rev-parse", "HEAD").strip()


@dataclass(frozen=True)
class ScriptedModel:
    """离线模型替身，按计划请求下一页，检查响应可替换为异常夹具。"""

    inspect: Callable[[DiffPage], tuple[Finding, ...]]

    def request_diff(self, available: ReadRequest) -> ReadRequest:
        """回传下一页请求，由图校验并执行。"""
        return available


def scripted_findings(page: DiffPage) -> tuple[Finding, ...]:
    """只在已收到的新增行识别固定夹具标记。用于演示，不能评价模型质量。"""
    return tuple(
        Finding(
            "重试可能重复登记订单",
            "首次登记完成后响应丢失，调用方再次执行登记",
            "相同订单可能产生两条记录",
            Evidence(page.hunk_id, page.path, "head", line.head_line, line.text.rstrip("\n")),
        )
        for line in page.lines
        if line.head_line is not None and line.base_line is None
        and line.text.strip() == "record_order(order_id)"
    )


def _timeout(_page: DiffPage) -> tuple[Finding, ...]:
    raise TimeoutError("演示中的模型超时")


def _ocr_fixture(snapshot: ReviewInput) -> ReviewResult:
    coverage = tuple(
        HunkCoverage(h.hunk_id, len(h.lines), len(h.lines), len(h.lines)) for h in snapshot.hunks
    )
    return ReviewResult(
        "complete", "synthetic_ocr_fixture", coverage,
        steps=(Step("finish", "保存无发现的合成 OCR 结果"),),
    )


def _run(
    store: PrototypeStore, snapshot: ReviewInput, log: Log, *, variant: str, max_reads: int,
    previous: Comparison | None = None,
) -> Comparison:
    model = ScriptedModel(_timeout if variant == "timeout" else scripted_findings)
    request_key = f"{snapshot.repository_id}:{variant}"
    config = f"script-v1:{variant}:page_lines=5:max_reads={max_reads}"
    comparison = store.enqueue(
        snapshot, request_key=request_key, configuration=config, previous=previous,
    )
    log(f"比较 #{comparison.id}：输入 {snapshot.key[:12]}，{snapshot.base_sha[:8]}"
        f" → {snapshot.head_sha[:8]}，OCR #{comparison.ocr_id} / Agent #{comparison.agent_id}")
    if previous is None:
        log("  OCR：queued → running")
        store.execute(
            comparison.ocr_id, snapshot, "ocr_fixture", lambda: _ocr_fixture(snapshot),
            configuration=OCR_FIXTURE_CONFIGURATION,
        )
        log("  OCR：running → complete（合成结果）")
    else:
        log(f"  OCR：复用比较 #{previous.id} 的尝试 #{comparison.ocr_id}")
    log("  Agent：queued → running")
    agent_result = store.execute(
        comparison.agent_id, snapshot, "agent_fixture",
        lambda: run_agent(
            snapshot, model, page_lines=5, max_reads=max_reads,
            trace=lambda step: log(f"    {step.stage} · {step.detail}"),
        ),
        configuration=config,
    )
    assert agent_result is not None
    reviewed = sum(block.reviewed_end for block in agent_result.coverage)
    total = sum(block.total for block in agent_result.coverage)
    log(f"  Agent：running → {agent_result.status}，"
        f"已核对 {reviewed}/{total} 条差异记录，{len(agent_result.findings)} 条发现")
    replay = store.enqueue(
        snapshot, request_key=request_key, configuration=config, previous=previous,
    )
    assert comparison == replay
    log(f"  重复请求 → 原比较 #{replay.id}")
    return comparison


def run_demo(root: Path, log: Log) -> Path:
    """运行正反例与超时、部分覆盖、单侧重跑，返回生成的 JSON 报告路径。"""
    # 1. 三份临时 Git 输入及一个空库，无网络或生产数据依赖。
    store = PrototypeStore.create(root / "review.sqlite3")
    protected = create_fixture(root / "protected", "protected")
    unprotected = create_fixture(root / "unprotected", "unprotected")
    long_diff = create_fixture(root / "long_diff", "long_diff")
    # 2. 正反例各执行一次；长差异通过新比较版本演示错误和恢复路径。
    safe = _run(store, protected, log, variant="full", max_reads=12)
    unsafe = _run(store, unprotected, log, variant="full", max_reads=12)
    timed_out = _run(store, long_diff, log, variant="timeout", max_reads=12)
    partial = _run(store, long_diff, log, variant="partial", max_reads=1, previous=timed_out)
    complete = _run(store, long_diff, log, variant="full", max_reads=12, previous=partial)
    # 3. 重新打开数据库生成报告，证明历史可从持久结果重建。
    reopened = PrototypeStore(store.path)
    reports = [reopened.report(run.id) for run in (safe, unsafe, timed_out, partial, complete)]
    output = root / "report.json"
    output.write_text(json.dumps(reports, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def main() -> None:
    """创建每次演示专属目录，并输出状态流转与可查询的产物路径。"""
    root = Path(tempfile.mkdtemp(prefix="ocr-dual-review-"))
    print("阶段一：合成 Git 差异、OCR 替身、脚本化模型")
    report = run_demo(root, print)
    print(f"JSON 报告：{report}\nSQLite：{root / 'review.sqlite3'}")


if __name__ == "__main__":
    main()
