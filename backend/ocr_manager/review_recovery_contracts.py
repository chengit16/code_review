"""声明默认可用的人工补审契约；客户端不能提交文件集合或伪造执行身份。"""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ocr_manager.recovery_budget import BudgetGate, RecoveryBudget
from ocr_manager.review_usage_contracts import KnownCost


class RecoveryCreate(BaseModel):
    """源版本与预算须由管理员确认，重试同一 HTTP 命令复用 client_key。"""

    model_config = ConfigDict(extra="forbid")
    client_key: UUID
    source_attempt: int = Field(ge=1, strict=True)
    source_revision: int = Field(ge=0, strict=True)
    token_budget: int = Field(ge=1, le=100_000_000, strict=True)
    timeout_seconds: int = Field(ge=1, le=3600, strict=True)


class RecoverySnapshot(BaseModel):
    """确认框所需冻结事实白名单，不输出端点、私有配置或规则正文。"""

    head_sha: str
    base_sha: str | None
    provider: str
    model: str
    model_version: int
    ocr_version: str | None
    rule_digest: str


class RecoveryEligibility(BaseModel):
    """仅由 SQLite 事实决定候选资格；正式执行仍须校验工件、Git 和当前快照。"""

    eligible: bool
    reason_code: str | None
    source_attempt: int | None = None
    source_revision: int | None = None
    remaining_count: int = 0
    max_token_budget: int = 0
    max_timeout_seconds: int = 0
    remaining_batches: int = 0
    remaining_paths: list[str] = Field(default_factory=list)
    active_recovery_id: int | None = None
    snapshot: RecoverySnapshot | None = None
    budget: RecoveryBudget | None = None
    route: Literal["independent_subset"] = "independent_subset"


class RecoveryRecord(BaseModel):
    """安全批次投影不包含内部路径、完整配置、原始结果或执行令牌。"""

    id: int
    job_id: int
    source_attempt: int
    source_revision: int
    status: Literal["queued", "running", "complete", "partial", "failed", "cancelled", "stale"]
    token_budget: int
    timeout_seconds: int
    cancel_requested: bool
    error_code: str | None
    failure_summary: str | None = Field(
        None, description="固定原因与可信覆盖计数，不包含原始响应；兼容读取旧失败批次")
    created_at: str
    started_at: str | None
    finished_at: str | None
    requested_by: str | None = None
    usage: dict[str, Any] | None
    estimated_cost: KnownCost | None = None
    budget_gate: BudgetGate | None = None


class RecoveryCandidate(BaseModel):
    """未接入消费者的候选只公开覆盖摘要，不返回完整发现或来源映射。"""

    source_attempt: int
    revision: int
    recovery_id: int
    terminal_state: Literal["complete", "partial"]
    coverage: dict[str, int]
    finding_count: int


class RecoveryCandidateResponse(BaseModel):
    """候选不是平台有效结论；消费者统一前始终明确标记未就绪。"""

    consumer_integration_ready: bool = False
    candidate: RecoveryCandidate | None


class RecoveryDelivery(BaseModel):
    """独立通知白名单，不包含冻结发现、凭据、工件或执行令牌。"""

    id: int
    source_attempt: int
    revision: int
    recovery_id: int
    status: Literal["pending", "sending", "sent", "failed", "superseded"]
    attempts: int
    error: str | None
    created_at: str
    sent_at: str | None
