"""框架无关的结果、证据及逐块覆盖契约，供演示和两路替身共享。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ocr_manager.review_prototype.input import Side

Engine = Literal["ocr_fixture", "agent_fixture"]
TerminalState = Literal["complete", "partial", "failed", "skipped"]


@dataclass(frozen=True)
class Evidence:
    """定位到固定输入中的差异块和新旧侧行；摘录须与已交付内容一致。"""

    hunk_id: int
    path: str
    side: Side
    line: int
    excerpt: str


@dataclass(frozen=True)
class Finding:
    """本轮候选主张、触发条件、影响及一个可核对证据。"""

    title: str
    trigger: str
    impact: str
    evidence: Evidence


@dataclass(frozen=True)
class HunkCoverage:
    """已交付、已完成审核的连续区间均从零开始，末尾位置为半开区间。"""

    hunk_id: int
    total: int
    delivered_end: int = 0
    reviewed_end: int = 0


@dataclass(frozen=True)
class Step:
    """节点事件只包含状态、定位和计数，不含模型推理或工具正文。"""

    stage: str
    detail: str


@dataclass(frozen=True)
class ReviewResult:
    """引擎运行的终态事实；替身无付费调用，费用在演示中记为零。"""

    status: TerminalState
    reason: str
    coverage: tuple[HunkCoverage, ...]
    findings: tuple[Finding, ...] = ()
    steps: tuple[Step, ...] = ()
    cost_minor_units: int = 0
    schema_version: int = 1
