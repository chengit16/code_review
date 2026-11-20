"""声明双评审的安全读模型与管理员裁定请求；工件和模型连接参数不进入 HTTP 契约。"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from ocr_manager.agent_capability_contracts import CapabilityEvent, CapabilityRun, Id
from ocr_manager.review_conclusion_contracts import ConclusionCoverage

FindingId = Annotated[str, StringConstraints(pattern=r"^(ocr|agent):[0-9]{1,6}$")]
Side = Literal["base", "head"]
Verdict = Literal["valid", "invalid", "insufficient"]
RunStatus = Literal["queued", "running", "complete", "partial", "failed", "skipped", "cancelled"]


class ComparisonCreate(BaseModel):
    """提交时确认当前 OCR 尝试与上一条 Agent 版本，按请求键去重。"""

    model_config = ConfigDict(extra="forbid", strict=True)
    source_attempt: int = Field(ge=1)
    previous_id: int | None = Field(ge=1)
    request_key: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,100}$")
    config_mode: Literal["current", "original"] = "current"
    trial_scheme_id: Id | None = None
    expected_scheme_id: Id | None = None
    original_run_id: Id | None = None


class ComparisonCreated(BaseModel):
    """返回已登记的尝试编号，任务领取及执行由 Worker 完成。"""

    id: int


class ComparisonSummary(BaseModel):
    """历史选择项；OCR 修订号固定为初审原始结果。"""

    id: int
    source_attempt: int
    previous_id: int | None
    status: RunStatus
    created_at: str
    finished_at: str | None
    trial: bool = False
    capability_recorded: bool = False


class ComparisonPilot(BaseModel):
    """当前任务所属仓库的试点状态与页面管理资格。"""

    repository_name: str
    enabled: bool
    manageable: bool


class ComparisonPilotUpdate(BaseModel):
    """管理员仅可修改任务所属仓库的试点开关。"""

    model_config = ConfigDict(extra="forbid", strict=True)
    enabled: bool


class ComparisonIndex(BaseModel):
    """返回当前可运行来源与按稳定编号倒序分页的历史。"""

    current_source_attempt: int | None
    previous_id: int | None
    active_id: int | None
    pilot: ComparisonPilot
    unavailable_reason: str | None
    items: list[ComparisonSummary]
    next_before_id: int | None
    current_scheme_id: int | None = None
    current_scheme_name: str | None = None


class ComparisonFinding(BaseModel):
    """当前比较内的发现身份；缺失或文件级证据不假定 Git 的一侧。"""

    id: FindingId
    path: str
    line: int | None
    side: Side | None = None
    title: str
    content: str = ""
    impact: str = ""
    excerpt: str = ""
    capability_refs: list[int] = Field(default_factory=list)


class ComparisonUsage(BaseModel):
    """仅汇总供应商已返回用量；未回执调用和费用保持独立。"""

    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    unknown_calls: int = 0
    cost: str | None = None
    currency: str | None = None


class OcrComparisonResult(BaseModel):
    """固定初审的文件覆盖与发现；历史缺失的覆盖显示为未知。"""

    status: str
    coverage: ConclusionCoverage | None
    findings: list[ComparisonFinding]
    usage: ComparisonUsage


class AgentRuleVersion(BaseModel):
    """仅展示解析出的规则来源、命中模式和内容摘要。"""

    source: str
    pattern: str
    sha256: str


class AgentCoverageFile(BaseModel):
    """按文件聚合实际送达、证据验收和清单记录数；单位是差异记录。"""

    path: str
    delivered: int = 0
    reviewed: int = 0
    total: int = 0
    rule: AgentRuleVersion | None = None


class AgentComparisonResult(BaseModel):
    """由冻结清单与已落库执行进度组成，不读取 Git 文件或模型原始回执。"""

    reason: str | None
    capabilities: CapabilityRun | None = None
    capability_events: list[CapabilityEvent] = Field(default_factory=list)
    workflow_steps: list[str] = Field(default_factory=list)
    files: list[AgentCoverageFile] | None
    excluded_paths: list[str]
    findings: list[ComparisonFinding]
    usage: ComparisonUsage


class FindingEvaluation(BaseModel):
    """正确性与处理价值独立；未判断处理价值时保持为空。"""

    model_config = ConfigDict(extra="forbid", strict=True)
    finding_id: FindingId
    verdict: Verdict
    worth_fixing: bool | None = None
    note: str = Field(default="", max_length=2000)


class FindingMatch(BaseModel):
    """同根因可以包含多条发现，每条发现最多属于一个组。"""

    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(pattern=r"^match:[a-z0-9:-]{1,50}$")
    label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    ocr_ids: list[FindingId] = Field(min_length=1, max_length=100)
    agent_ids: list[FindingId] = Field(min_length=1, max_length=100)


class MissedFinding(BaseModel):
    """人工补录的共同漏报，不参与任何引擎结果或发布。"""

    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(pattern=r"^missed:[a-z0-9-]{1,50}$")
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
    path: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    line: int | None = Field(default=None, ge=1)
    side: Side | None = None
    note: str = Field(default="", max_length=2000)


class ComparisonCuration(BaseModel):
    """每次保存追加完整裁定快照，以支持历史复核和乐观并发。"""

    model_config = ConfigDict(extra="forbid", strict=True)
    evaluations: list[FindingEvaluation] = Field(default_factory=list, max_length=10000)
    matches: list[FindingMatch] = Field(default_factory=list, max_length=500)
    missed: list[MissedFinding] = Field(default_factory=list, max_length=500)


class CurationUpdate(BaseModel):
    """覆盖前确认编辑起始版本，冲突由界面提示并保留草稿。"""

    model_config = ConfigDict(extra="forbid", strict=True)
    expected_version: int = Field(ge=0)
    document: ComparisonCuration


class CurationSnapshot(BaseModel):
    """版本零为空白比较；正版本保留实际修改时间和管理身份。"""

    version: int
    actor: str | None = None
    created_at: str | None = None
    document: ComparisonCuration


class AgentComparison(ComparisonSummary):
    """两路结果与人工裁定同一读快照，固定 Git 范围用于证据定位。"""

    base_sha: str
    head_sha: str
    ocr: OcrComparisonResult
    agent: AgentComparisonResult
    suggestions: list[FindingMatch]
    curation: CurationSnapshot
    latest_curation_version: int
