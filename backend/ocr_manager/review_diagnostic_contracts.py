"""声明失败诊断的安全投影；不包含请求正文、工具参数或模型推理，不决定重试。"""

from typing import Literal

from pydantic import BaseModel, Field


class RequestEvidence(BaseModel):
    """单个失败逻辑请求的有界事实；无法可靠关联分组时 group_id 为空。"""

    logical_request_id: str | None = Field(
        None, description="仅保留 OCR 的 64 位十六进制逻辑请求摘要；未知格式不透传")
    group_id: str | None
    task_type: Literal["plan_task", "main_task", "unknown"]
    request_no: int | None
    attempts: int
    http_statuses: list[int]
    error_classes: list[str]
    failure_phases: list[str]
    duration_to_headers_ms: list[int]
    observed_backoff_ms: list[int]


class FailureGroup(BaseModel):
    """分组路径仅来自可信覆盖集合；序号只在本次结果内稳定。"""

    group_id: str
    paths: list[str]
    failed_count: int


class DiagnosticSignal(BaseModel):
    """固定中文类别和出现次数，不把外部错误原文透传给页面。"""

    code: str
    message: str
    count: int


class FailureAnalysis(BaseModel):
    """版本化诊断，partial 的错误证据不授予平台整批重试资格。"""

    schema_version: Literal["platform.failure-analysis/v1"] = "platform.failure-analysis/v1"
    summary: str
    selected_count: int
    completed_count: int
    failed_count: int
    failed_group_count: int | None
    report_state: Literal["available", "missing", "unsupported", "malformed", "limited"]
    groups: list[FailureGroup]
    requests: list[RequestEvidence]
    signals: list[DiagnosticSignal]
    notes: list[str] = Field(description="缺失与截断边界；不推断成功请求的耗时分布")
