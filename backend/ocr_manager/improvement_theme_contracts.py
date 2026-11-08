"""定义优化主题、阶段和问题关联契约；阶段验证不自动推断主题成效。"""

from __future__ import annotations

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ocr_manager.improvement_archive_contracts import ArchiveAction, ArchiveMetadata
from ocr_manager.improvement_contracts import (
    DeploymentState,
    ImprovementCategory,
    VerificationState,
)

ThemeStatus = Literal["planned", "active", "paused", "completed", "deferred"]
PhaseStatus = Literal["planned", "active", "completed", "deferred"]
ImprovementThemeStatus = ThemeStatus
RecordId = Annotated[int, Field(gt=0, strict=True)]


class ImprovementPhase(BaseModel):
    """主题中的有序工作阶段及其独立证据。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=160)
    goal: str = Field(min_length=1, max_length=5000)
    status: PhaseStatus = "planned"
    solution: str = Field(default="", max_length=10000)
    code_state: Literal["unchanged", "modified", "not_applicable"] = "unchanged"
    verification_state: VerificationState = "not_run"
    validation_evidence: str = Field(default="", max_length=10000)
    deployment_state: DeploymentState = "not_deployed"
    deployment_evidence: str = Field(default="", max_length=10000)
    next_steps: str = Field(default="", max_length=5000)

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        """已完成阶段必须说明方案与本地验证边界，不等于生产部署完成。"""

        if self.verification_state in {"passed", "failed", "blocked", "not_applicable"}:
            if not self.validation_evidence:
                raise ValueError("阶段验证状态需要记录结果、阻塞原因或不适用说明")
        if (self.deployment_state in {"confirmed", "not_applicable"}
            and not self.deployment_evidence):
            raise ValueError("部署确认或不适用状态需要填写证据或原因")
        if self.status == "completed" and (not self.solution or self.verification_state not in {
            "passed", "not_applicable",
        }):
            raise ValueError("完成阶段需要记录解决办法及验证结果或不适用说明")
        return self


class ImprovementThemeContent(BaseModel):
    """主题摘要及完整有序阶段；关联问题单独存为关系表。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=160)
    category: ImprovementCategory = "other"
    status: ThemeStatus = "planned"
    scope: str = Field(default="平台", min_length=1, max_length=120)
    objective: str = Field(min_length=1, max_length=10000)
    rationale: str = Field(default="", max_length=10000)
    outcome: str = Field(default="", max_length=10000)
    next_steps: str = Field(default="", max_length=10000)
    references: str = Field(default="", max_length=5000)
    phases: list[ImprovementPhase] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validate_completion(self) -> Self:
        """主题完成须有至少一个完整阶段，不能仅修改下拉状态。"""

        if self.status == "completed" and (
            not self.outcome.strip() or not self.phases
            or any(phase.status != "completed" for phase in self.phases)
        ):
            raise ValueError("主题完成需要总体结果且所有阶段均已完成")
        return self


class ImprovementThemeCreate(ImprovementThemeContent):
    """创建幂等键和问题关联列表。"""

    client_key: UUID
    improvement_ids: list[RecordId] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def unique_links(self) -> Self:
        """创建时同样拒绝重复关联编号。"""

        if len(set(self.improvement_ids)) != len(self.improvement_ids):
            raise ValueError("同一问题不能在主题关联列表中重复")
        return self


class ImprovementThemeUpdate(ImprovementThemeContent):
    """完整快照更新按主题版本保护，并追加变更说明。"""

    expected_version: int = Field(ge=1, strict=True)
    progress_note: str = Field(min_length=1, max_length=2000)
    improvement_ids: list[RecordId] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def unique_links(self) -> Self:
        """重复编号会造成阶段回顾含糊，整体拒绝而非静默去重。"""

        if len(set(self.improvement_ids)) != len(self.improvement_ids):
            raise ValueError("同一问题不能在主题关联列表中重复")
        return self


class ImprovementThemeRecord(ArchiveMetadata, ImprovementThemeContent):
    """当前主题、阶段和问题关联及乐观并发版本。"""

    id: int
    version: int
    improvement_ids: list[int]
    created_at: str
    updated_at: str


class ImprovementThemePage(BaseModel):
    """主题卡片的分页摘要与总数。"""

    items: list[ImprovementThemeRecord]
    total: int
    page: int
    page_size: int
    status_counts: dict[str, int] = Field(
        default_factory=dict, description="忽略状态和分页、保留其他条件的全量数量")


class ImprovementThemeRevision(ArchiveMetadata):
    """主题的历史摘要、完整阶段及当时关联编号。"""

    action: ArchiveAction = "update"
    version: int
    actor: str
    note: str
    created_at: str
    snapshot: ImprovementThemeContent
    improvement_ids: list[int]


class ImprovementThemeHistory(BaseModel):
    """主题历史独立分页。"""

    items: list[ImprovementThemeRevision]
    total: int
    page: int
    page_size: int
