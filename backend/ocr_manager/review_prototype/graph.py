"""LangGraph 负责本次评审步骤；证据校验与覆盖由本地代码裁定。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Literal, Protocol, TypedDict

from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context

from ocr_manager.review_prototype.input import DiffPage, ReviewInput
from ocr_manager.review_prototype.result import Finding, HunkCoverage, ReviewResult, Step

Trace = Callable[[Step], None]
Destination = Literal["read", "finish"]


@dataclass(frozen=True)
class ReadRequest:
    """模型请求的差异块及起始位置；分页大小由图的预算决定。"""

    hunk_id: int
    offset: int


class PageModel(Protocol):
    """一次读取和单页推理的模型边界；工具执行权仍由图持有。"""

    def request_diff(self, available: ReadRequest) -> ReadRequest: ...

    def inspect(self, page: DiffPage) -> tuple[Finding, ...]: ...


class GraphState(TypedDict):
    """单次运行状态，消费顺序固定；图不领取 SQLite 中的尝试。"""

    coverage: tuple[HunkCoverage, ...]
    findings: tuple[Finding, ...]
    steps: tuple[Step, ...]
    reads: int
    hunk_index: int
    page: DiffPage | None
    reason: str


@dataclass(frozen=True)
class AgentProgress:
    """可持久化的已核对页进度，不带待发送、未返回或未验证的差异数据。"""

    coverage: tuple[HunkCoverage, ...]
    findings: tuple[Finding, ...]
    steps: tuple[Step, ...]
    reads: int
    hunk_index: int


class ModelPageFailure(Exception):
    """适配器已记录的终止原因，只允许稳定业务码进入图轨迹。"""

    def __init__(self, reason: Literal["model_budget", "model_unavailable", "model_response"]):
        self.reason = reason
        super().__init__(reason)


def _validate(page: DiffPage, findings: tuple[Finding, ...]) -> None:
    for finding in findings:
        evidence = finding.evidence
        if (
            evidence.hunk_id != page.hunk_id or evidence.path != page.path
            or not any(
                line.number(evidence.side) == evidence.line
                and line.text.rstrip("\n") == evidence.excerpt for line in page.lines
            )
        ):
            raise ValueError("证据不属于本次交付的差异页")


def run_agent(
    snapshot: ReviewInput, model: PageModel, *, page_lines: int, max_reads: int | None,
    trace: Trace | None = None, resume: AgentProgress | None = None,
    checkpoint: Callable[[AgentProgress], None] | None = None,
) -> ReviewResult:
    """运行有限读取和校验。保留超时、无效证据及预算停止时的真实覆盖。"""
    if page_lines < 1 or (max_reads is not None and max_reads < 1):
        raise ValueError("需要正数读取预算和分页大小")
    # 无配置页数门槛时，用冻结输入的实际页数约束图的执行步数。
    read_limit = max_reads if max_reads is not None else sum(
        (len(hunk.lines) + page_lines - 1) // page_lines for hunk in snapshot.hunks
    )

    def event(steps: tuple[Step, ...], stage: str, detail: str) -> tuple[Step, ...]:
        step = Step(stage, detail)
        if trace:
            trace(step)
        return (*steps, step)

    def route(state: GraphState) -> Destination:
        if state["reason"] or state["reads"] >= read_limit:
            return "finish"
        return "read" if state["hunk_index"] < len(state["coverage"]) else "finish"

    def read(state: GraphState) -> dict[str, object]:
        index = state["hunk_index"]
        coverage = state["coverage"]
        hunk = coverage[index]
        available = ReadRequest(hunk.hunk_id, hunk.delivered_end)
        try:
            request = model.request_diff(available)
        except TimeoutError:
            return {
                "reason": "model_timeout",
                "steps": event(state["steps"], "failed", "请求差异页时模型超时"),
            }
        if request != available:
            return {
                "reason": "invalid_read_request",
                "steps": event(state["steps"], "failed", "差异页请求超出当前计划"),
            }
        requested = event(
            state["steps"], "request", f"模型请求块 {request.hunk_id}，起始 {request.offset}",
        )
        page = snapshot.read_diff(request.hunk_id, request.offset, page_lines)
        updated = replace(hunk, delivered_end=page.end)
        return {
            "page": page, "reads": state["reads"] + 1,
            "coverage": (*coverage[:index], updated, *coverage[index + 1:]),
            "steps": event(
                requested, "read",
                f"{page.path} 块 {page.hunk_id} [{page.start},{page.end})/{page.total}"
                f"，续读位置 {page.next_offset if page.next_offset is not None else '无'}",
            ),
        }

    def inspect(state: GraphState) -> dict[str, object]:
        # 只有模型完成且全部引用有效时，才推进本页的实际审核范围。
        page = state["page"]
        assert page is not None
        steps = state["steps"]
        try:
            findings = model.inspect(page)
        except TimeoutError:
            return {"reason": "model_timeout", "steps": event(steps, "failed", "模型调用超时")}
        except ModelPageFailure as error:
            return {
                "reason": error.reason,
                "steps": event(steps, "stopped", error.reason),
            }
        try:
            _validate(page, findings)
        except ValueError:
            return {"reason": "invalid_evidence", "steps": event(steps, "failed", "证据校验失败")}
        index = state["hunk_index"]
        coverage = state["coverage"]
        updated = replace(coverage[index], reviewed_end=page.end)
        progress = AgentProgress(
            (*coverage[:index], updated, *coverage[index + 1:]),
            (*state["findings"], *findings),
            event(steps, "verified", f"本页已核对，保留 {len(findings)} 条发现"),
            state["reads"], index + (page.next_offset is None),
        )
        if checkpoint:
            checkpoint(progress)
        return {"coverage": progress.coverage, "hunk_index": progress.hunk_index,
                "findings": progress.findings, "steps": progress.steps}

    def start(state: GraphState) -> dict[str, object]:
        return {"steps": event(
            state["steps"], "resume" if resume else "start",
            f"从已核对的 {state['reads']} 页继续" if resume
            else f"冻结范围包含 {len(snapshot.hunks)} 个差异块",
        )}

    def finish(state: GraphState) -> dict[str, object]:
        reason = state["reason"]
        if not reason:
            if not state["coverage"]:
                reason = "no_text_diff"
            elif state["hunk_index"] < len(state["coverage"]):
                reason = "read_budget"
            else:
                reason = "covered"
        return {"reason": reason, "steps": event(state["steps"], "finish", reason)}

    def after_read(state: GraphState) -> Literal["inspect", "finish"]:
        return "finish" if state["reason"] else "inspect"

    # 1. 由条件边决定续读或终止，单页最多调用模型一次，不在图中自动重试。
    graph = StateGraph(GraphState)
    graph.add_node("start", start)
    graph.add_node("read", read)
    graph.add_node("inspect", inspect)
    graph.add_node("finish", finish)
    graph.add_edge(START, "start")
    graph.add_conditional_edges("start", route)
    graph.add_conditional_edges("read", after_read)
    graph.add_conditional_edges("inspect", route)
    graph.add_edge("finish", END)
    initial: GraphState = {
        "coverage": (resume.coverage if resume else
                     tuple(HunkCoverage(h.hunk_id, len(h.lines)) for h in snapshot.hunks)),
        "findings": resume.findings if resume else (), "steps": resume.steps if resume else (),
        "reads": resume.reads if resume else 0, "hunk_index": resume.hunk_index if resume else 0,
        "page": None, "reason": "",
    }
    # 2. 禁止继承外部 tracing 配置；差异和运行事件只交给当前调用方。
    with tracing_context(enabled=False):
        final = graph.compile().invoke(initial, {"recursion_limit": 2 * read_limit + 6})
    # 3. 预算停止与异常分别落在部分完成、失败等明确结果上。
    reason = final["reason"]
    status: Literal["complete", "partial", "failed", "skipped"]
    if reason == "covered":
        status = "complete"
    elif reason == "no_text_diff":
        status = "skipped"
    elif reason in {"read_budget", "model_budget"}:
        status = "partial"
    else:
        status = "failed"
    return ReviewResult(status, reason, final["coverage"], final["findings"], final["steps"])
