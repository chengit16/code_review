"""声明评审可观测性的响应契约；不查询数据库、不计算状态，也不负责权限校验。"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ocr_manager.review_conclusion_contracts import (
    ConclusionDocument,
    ConclusionOverview,
    ConclusionVersion,
)
from ocr_manager.review_diagnostic_contracts import FailureAnalysis
from ocr_manager.review_usage_contracts import CumulativeUsage as CumulativeUsage
from ocr_manager.review_usage_contracts import KnownCost as KnownCost


class ReviewTiming(BaseModel):
    """服务端同一 UTC 时刻计算的时间口径；空值表示无法从历史事实恢复。"""

    first_queue_seconds: float | None
    latest_execution_seconds: float | None
    cumulative_execution_seconds: float | None
    execution_complete: bool
    known_attempts: int
    total_attempts: int
    total_elapsed_seconds: float | None
    retry_backoff_seconds: float | None
    retry_ready_wait_seconds: float | None
    schedule_complete: bool
    calculated_at: str


class ReviewReason(BaseModel):
    """稳定原因码与安全摘要；不承载上游原始响应。"""

    code: str
    message: str


class TaskIssueSummary(BaseModel):
    """当前有效发现按最终问题身份去重；未知关联与没有可用结论不得冒充已处置。"""

    available: bool
    finding_count: int | None
    highest_severity: str | None
    open_count: int
    fixed_count: int
    ignored_count: int
    false_positive_count: int = 0
    unknown_count: int
    complete: bool
    no_findings: bool
    coverage_complete: bool
    coverage_limited: bool


class TaskExecutionResponse(BaseModel):
    """保留已有动态任务字段，新增可观测性字段提供明确 OpenAPI 契约。"""

    model_config = ConfigDict(extra="allow")
    id: int
    list_status: str | None = Field(None, description="活动补审优先，其次为当前有效评审状态")
    active_recovery_status: str | None = None
    issue_summary: TaskIssueSummary | None = None
    effective_status: str | None = None
    effective_conclusion: ConclusionVersion | None = None
    effective_document: ConclusionDocument | None = None
    initial_cumulative_usage: CumulativeUsage | None = None
    recovery_execution_count: int = 0
    active_recovery_id: int | None = None
    recovery_delivery_failed_count: int = 0
    conclusions: ConclusionOverview | None = Field(
        None, description="统一初审/当前候选摘要；有效版本另列，保留初审状态和原始反馈索引")
    failure_summary: str | None = Field(None, description="已持久化安全摘要；旧结果缺失时不回填")
    failure_analysis: FailureAnalysis | None = Field(
        None, description="详情的分层失败证据，列表省略")
    failure_analysis_imported_at: str | None = Field(
        None, description="受控历史诊断导入时间；导入不修改初审结果或触发模型")
    timing: ReviewTiming
    reason: ReviewReason
    cumulative_usage: CumulativeUsage
    scope_analysis: dict[str, Any] | None = Field(
        None, description="仅含固定范围、计数及仓库相对路径；列表省略逐文件路径，不含代码正文")


class TaskSearchResponse(BaseModel):
    """全量检索的稳定分页响应，条目保留既有兼容字段。"""

    items: list[TaskExecutionResponse]
    total: int
    page: int
    page_size: int
    status_counts: dict[str, int] = Field(default_factory=dict)
