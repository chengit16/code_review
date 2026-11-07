"""后台台账维护的管理员契约；只返回运行事实，不暴露来源路径或正文。"""

from pydantic import BaseModel, ConfigDict, Field

from ocr_manager.improvement_log_sync import LogSyncResult


class MaintenancePolicy(BaseModel):
    """策略变更使用严格版本；启用仅授权后台归档，不隐含已执行。"""

    model_config = ConfigDict(extra="forbid")
    enabled: bool = Field(strict=True)
    archive_after_days: int = Field(ge=1, le=3650, strict=True)
    expected_version: int = Field(ge=1, strict=True)


class MaintenanceResult(BaseModel):
    """本轮同步和归档的实际提交数；错误码独立于成功时间。"""

    sync: LogSyncResult = Field(default_factory=LogSyncResult)
    archived_records: int = 0
    archived_themes: int = 0


class MaintenanceStatus(BaseModel):
    """候选数是读取时预览，后台仍需在短写事务内重新核对。"""

    enabled: bool
    archive_after_days: int
    version: int
    source_configured: bool
    last_checked_at: str | None
    last_success_at: str | None
    last_error_code: str
    last_result: MaintenanceResult
    candidate_records: int
    candidate_themes: int
