"""平台台账和主题的归档契约；归档是收纳，不是解决、部署或删除。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ArchiveFilter = Literal["active", "archived", "all"]
ArchiveAction = Literal["create", "update", "archive", "restore"]


class ArchiveMetadata(BaseModel):
    """当前归档事实；恢复后清空，归档和恢复原因仍永久保留在历史中。"""

    archived_at: str | None = None
    archived_by: str = ""
    archive_reason: str = ""


class ArchiveChange(BaseModel):
    """显式指定目标状态及读取版本；重复或过期请求拒绝，不重复追加历史。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    archived: bool = Field(strict=True)
    expected_version: int = Field(ge=1, strict=True)
    reason: str = Field(min_length=1, max_length=2000)
