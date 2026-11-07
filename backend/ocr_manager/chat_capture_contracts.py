"""定义管理员聊天收件箱的脱敏契约；不暴露会话路径或允许浏览器扩大采集范围。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatBinding(BaseModel):
    """显式绑定及后台事实；新鲜度由页面按最近检查时间判断，不能仅看 enabled。"""

    id: int
    thread_id: str
    enabled: bool
    version: int
    since_ms: int
    last_checked_at: str | None
    last_success_at: str | None
    last_error_code: str
    last_message_ms: int | None
    last_scan_count: int


class ChatEvent(BaseModel):
    """用户内容只返回有界脱敏摘要；助手仅保存答复存在的元数据，不作为验收事实。"""

    id: int
    binding_id: int
    turn_id: str
    message_id: str
    role: Literal["user", "assistant"]
    classification: Literal["issue", "pending", "progress"]
    excerpt: str
    source_ms: int
    improvement_id: int | None
    version: int
    created_at: str


class ChatInbox(BaseModel):
    """绑定状态、待核实计数和有界分页；后台未运行也必须可见。"""

    bindings: list[ChatBinding]
    items: list[ChatEvent]
    pending: int
    total: int
    page: int
    page_size: int


class ChatBindingChange(BaseModel):
    """仅暂停或恢复已有授权，不支持通过 HTTP 指定新路径或新会话。"""

    model_config = ConfigDict(extra="forbid")
    enabled: bool
    expected_version: int = Field(ge=1)


class ChatEventLink(BaseModel):
    """显式建立或解除关联；空关联与 promote 区分，错误关联可回退且保留审计。"""

    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    improvement_id: int | None = Field(default=None, ge=1)
    promote: bool = False
