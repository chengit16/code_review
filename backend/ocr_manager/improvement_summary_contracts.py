"""定义平台复盘的只读投影；当前存量与北京时间窗口内活动分开计数。"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from ocr_manager.improvement_contracts import ImprovementCategory


class ImprovementDistribution(BaseModel):
    """按实体当前字段计数，固定枚举补零；不统计历史快照的重复实体。"""

    total: int
    by_status: dict[str, int]
    by_category: dict[str, int]
    by_code_state: dict[str, int]
    by_verification_state: dict[str, int]
    by_deployment_state: dict[str, int]


class ImprovementRecordSummary(ImprovementDistribution):
    """问题和阶段改进共同构成台账；显式关联的记录按编号去重。"""

    by_kind: dict[str, int]
    linked_records: int


class ImprovementThemeSummary(BaseModel):
    """主题和阶段使用各自分母；阶段归属范围由主题当前分类决定。"""

    total: int
    by_status: dict[str, int]
    by_category: dict[str, int]
    phases: ImprovementDistribution


class ImprovementActivityDay(BaseModel):
    """每日新增与历史追加次数（含归档、恢复）；初始版本不重复计为追加。"""

    date: date
    records_created: int = 0
    record_updates: int = 0
    themes_created: int = 0
    theme_updates: int = 0


class ImprovementAttentionItem(BaseModel):
    """仅投影定位信息，不返回问题正文、内部证据或操作者。"""

    id: int
    title: str
    status: str
    updated_at: str
    archived_at: str | None = None


class ImprovementAttentionGroup(BaseModel):
    """每组返回最久未更新的前十条；总数来自完整筛选而非样本长度。"""

    total: int
    items: list[ImprovementAttentionItem]


class ImprovementSummary(BaseModel):
    """同一 SQLite 读取快照中的累计统计、活动趋势和待办，不执行任何写入。"""

    generated_at: datetime
    timezone: str = "Asia/Shanghai"
    start_date: date
    end_date: date
    category: ImprovementCategory | None
    archived_records: int = 0
    archived_themes: int = 0
    records: ImprovementRecordSummary
    themes: ImprovementThemeSummary
    activity: list[ImprovementActivityDay]
    unresolved: ImprovementAttentionGroup
    verification_attention: ImprovementAttentionGroup
    deployment_pending: ImprovementAttentionGroup = Field(
        description="仅本地验证通过且部署未确认的记录，不包含部署不适用"
    )
    unfinished_themes: ImprovementAttentionGroup
