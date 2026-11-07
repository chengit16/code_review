"""声明初审与补审候选的只读契约；来源身份不等于旧反馈或发布接口的评论索引。"""

from typing import Literal

from pydantic import BaseModel, Field

from ocr_manager.review_usage_contracts import CumulativeUsage


class ConclusionCoverage(BaseModel):
    """覆盖数量来自持久化集合；历史缺失时整个覆盖对象为空而非伪造零。"""

    selected: int
    completed: int
    reused: int
    failed: int
    waived: int


class ConclusionVersion(BaseModel):
    """revision=0 是根尝试，正数是候选版本；不改变任务执行状态。"""

    source_attempt: int
    revision: int
    recovery_id: int | None = None
    terminal_state: str
    coverage: ConclusionCoverage | None
    finding_count: int


class ConclusionOverview(BaseModel):
    """所有消费者使用同一选择规则；仅经过完整验证提升的候选标记为有效。"""

    consumer_integration_ready: bool = False
    initial: ConclusionVersion | None
    candidate: ConclusionVersion | None
    effective: ConclusionVersion | None = None


class FindingOrigin(BaseModel):
    """身份固定到根尝试或独立补审批次，不随聚合评论位置变化。"""

    kind: Literal["attempt", "recovery"]
    source_attempt: int
    recovery_id: int | None = None
    comment_index: int = Field(ge=0)


class ConclusionFinding(BaseModel):
    """只读发现白名单；finding_id 供后续版本化反馈使用，不能提交到旧索引接口。"""

    finding_id: str
    origin: FindingOrigin
    also_seen_in: list[FindingOrigin]
    path: str
    content: str
    start_line: int | None = None
    end_line: int | None = None
    severity: str | None = None
    category: str | None = None


class ConclusionDocument(BaseModel):
    """管理员只读版本，不透出工件、配置或外部正文，不触发反馈/问题/投递副作用。"""

    schema_version: Literal["platform.review-conclusion/v1"] = "platform.review-conclusion/v1"
    consumer_integration_ready: bool = False
    job_id: int
    version: ConclusionVersion
    role: Literal["initial", "candidate", "effective"]
    is_current_source: bool
    findings: list[ConclusionFinding]
    input_filter_excluded_count: int | None
    execution_usage: CumulativeUsage
    usage_through_recovery_id: int | None
