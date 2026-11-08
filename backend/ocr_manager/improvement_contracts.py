"""定义平台问题与改进的记录契约；修改、验证和部署证据分别校验。"""

from __future__ import annotations

from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ocr_manager.improvement_archive_contracts import ArchiveAction, ArchiveMetadata

ImprovementStatus = Literal["open", "investigating", "planned", "verifying", "resolved", "deferred"]
ImprovementKind = Literal["problem", "improvement"]
ImprovementCategory = Literal["stability", "performance", "integration", "deployment", "experience",
                              "security", "other"]
VerificationState = Literal["not_run", "passed", "failed", "blocked", "not_applicable"]
DeploymentState = Literal["not_deployed", "confirmed", "unknown", "not_applicable"]


class ImprovementContent(BaseModel):
    """完整保存当前摘要；历史快照单独追加，不能以修改摘要抹去原结论。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=160)
    kind: ImprovementKind = "problem"
    category: ImprovementCategory = "other"
    status: ImprovementStatus = "open"
    scope: str = Field(default="平台", min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=10000)
    analysis: str = Field(default="", max_length=10000)
    solution: str = Field(default="", max_length=10000)
    code_state: Literal["unchanged", "modified", "not_applicable"] = "unchanged"
    verification_state: VerificationState = "not_run"
    validation_evidence: str = Field(default="", max_length=10000)
    deployment_state: DeploymentState = "not_deployed"
    deployment_evidence: str = Field(default="", max_length=10000)
    next_steps: str = Field(default="", max_length=10000)
    references: str = Field(default="", max_length=5000)

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        """验证通过和部署确认必须有证据；解决状态不隐含已部署。"""

        if self.verification_state in {"passed", "failed", "blocked", "not_applicable"}:
            if not self.validation_evidence:
                raise ValueError("本地验证状态需要填写检查结果、受阻原因或不适用说明")
        if (self.deployment_state in {"confirmed", "not_applicable"}
            and not self.deployment_evidence):
            raise ValueError("请填写部署环境及生效证据，或说明部署不适用的原因")
        if self.status == "resolved" and (
            not self.solution or self.verification_state not in {"passed", "not_applicable"}
        ):
            raise ValueError("已解决需要处理方案及通过的验证，或验证不适用的说明")
        return self


class ImprovementCreate(ImprovementContent):
    """创建键由调用方生成；网络重试复用同一键，防止重复建档。"""

    client_key: UUID


class ImprovementUpdate(ImprovementContent):
    """按读取版本保存；并发冲突保留调用方草稿，不静默覆盖。"""

    expected_version: int = Field(ge=1, strict=True)
    progress_note: str = Field(min_length=1, max_length=2000)


class ImprovementRecord(ArchiveMetadata, ImprovementContent):
    """当前记录及其版本；创建键不作为列表或详情公开字段。"""

    id: int
    version: int
    created_at: str
    updated_at: str


class ImprovementPage(BaseModel):
    """同一读取快照中的分页记录和总数。"""

    items: list[ImprovementRecord]
    total: int
    page: int
    page_size: int
    status_counts: dict[str, int] = Field(
        default_factory=dict, description="忽略状态和分页、保留其他条件的全量数量")


class ImprovementRevision(ArchiveMetadata):
    """保留每次保存时的完整事实与操作者，旧快照不会被新摘要覆盖。"""

    action: ArchiveAction = "update"
    version: int
    actor: str
    note: str
    created_at: str
    snapshot: ImprovementContent


class ImprovementHistory(BaseModel):
    """历史按版本倒序分页，不一次返回所有长文本。"""

    items: list[ImprovementRevision]
    total: int
    page: int
    page_size: int
