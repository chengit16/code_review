"""管理台的方案、能力和执行记录契约。"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Id = Annotated[int, Field(ge=1, le=2**63 - 1)]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Pattern = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240,
                           pattern=r"^[^\x00-\x1f]+$"),
]
Tool = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_.-]{1,128}$")]
Node = Literal["skills", "read_file", "mcp"]


class StrictInput(BaseModel):
    """拒绝额外字段和隐式类型转换。"""

    model_config = ConfigDict(strict=True, extra="forbid")


class SkillInput(StrictInput):
    """每次保存形成不可变的检查方法版本。"""

    name: Label
    pattern: Pattern
    body: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class FileLookup(StrictInput):
    """当前差异文件匹配时，读同一仓库固定头提交的指定普通文件。"""

    pattern: Pattern
    path: Annotated[
        str, StringConstraints(min_length=1, max_length=240, pattern=r"^[^\x00-\x1f\\]+$"),
    ]
    start_line: int = Field(default=1, ge=1, le=100_000)
    lines: int = Field(default=30, ge=1, le=80)

    @model_validator(mode="after")
    def path_relative(self) -> "FileLookup":
        """仅接受无歧义的仓库相对路径。"""

        if any(part in {"", ".", "..", ".git"} for part in self.path.split("/")):
            raise ValueError("补查文件须为明确的仓库相对路径")
        return self


class McpLookup(StrictInput):
    """仅调用已发现并授权的单一规范检索工具。"""

    service_id: Id
    tool: Tool
    pattern: Pattern
    argument: Tool = "query"
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    failure: Literal["continue", "stop"] = "continue"


class SchemeDocument(StrictInput):
    """约束选项与节点依赖，基础差异读取及证据确认由执行器保留。"""

    steps: list[Node] = Field(default_factory=list, max_length=3)
    skill_ids: list[Id] = Field(default_factory=list, max_length=4)
    files: list[FileLookup] = Field(default_factory=list, max_length=3)
    mcp: McpLookup | None = None

    @model_validator(mode="after")
    def dependencies(self) -> "SchemeDocument":
        """发布的每个能力都须处于一个可执行节点中。"""

        expected = {step for step, enabled in (
            ("skills", self.skill_ids), ("read_file", self.files), ("mcp", self.mcp),
        ) if enabled}
        if (set(self.steps) != expected or len(self.steps) != len(expected)
                or len(set(self.skill_ids)) != len(self.skill_ids)
                or len({item.model_dump_json() for item in self.files}) != len(self.files)):
            raise ValueError("步骤须与已选能力一一对应，且不能重复")
        return self


class SchemeInput(SchemeDocument):
    """保存新的方案草稿。"""

    name: Label
    basis_id: Id | None = None


class SchemeSummary(BaseModel):
    """不变的方案修订与当前发布状态。"""

    id: int
    name: str
    basis_id: int | None
    state: Literal["draft", "published", "disabled"]
    document: SchemeDocument
    actor: str
    created_at: str


class SkillVersion(SkillInput):
    """可用于组装方案的 Skill 修订。"""

    id: int
    actor: str
    created_at: str


class McpInput(StrictInput):
    """外部服务登记，令牌仅写入。"""

    name: Label
    endpoint: Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=500)]
    token: str = Field(default="", max_length=2048, pattern=r"^[!-~]*$")
    timeout_seconds: int = Field(default=8, ge=1, le=15)


class McpService(BaseModel):
    """安全的服务元数据和已发现的工具。"""

    id: int
    name: str
    endpoint: str
    timeout_seconds: int
    enabled: bool
    has_token: bool
    tools: dict[str, dict[str, object]]
    grants: list["McpGrant"]


class McpGrant(StrictInput):
    """工具授权仅在一个仓库内有效。"""

    repository_id: Id
    tool: Tool


class EnabledInput(StrictInput):
    """显式的开关操作。"""

    enabled: bool


class ProjectAgentInput(StrictInput):
    """以界面读取的版本检测项目保存冲突。"""

    version: int = Field(ge=0)
    scheme_id: Id | None = None
    model_profile_id: Id | None = None
    enabled: bool


class ProjectAgentSettings(ProjectAgentInput):
    """项目选择以及解析后的有效方案和模型。"""

    manageable: bool
    effective_scheme: SchemeSummary
    effective_model: str | None
    unavailable_reason: str | None = None


class CapabilityCatalog(BaseModel):
    """发布中心的管理目录。"""

    default_id: int
    inheriting_projects: list[int]
    project_bindings: dict[int, int]
    schemes: list[SchemeSummary]
    skills: list[SkillVersion]
    services: list[McpService]


class SchemeTrial(BaseModel):
    """方案的最新试跑链接和持久化状态。"""

    id: int
    job_id: int
    status: str
    created_at: str


class DefaultSchemeInput(StrictInput):
    """切换平台默认前确认此前读取的版本。"""

    expected_id: Id


class PreviewInput(StrictInput):
    """选择有固定差异范围的历史任务。"""

    job_id: Id


class CapabilityCheck(BaseModel):
    """后台检查只公开结构化结果。"""

    id: int
    kind: Literal["preview", "mcp"]
    status: Literal["queued", "running", "complete", "failed"]
    result: dict[str, object] | None


class CapabilityRun(BaseModel):
    """按次记录，仅展示选择及版本，不包含提示或凭据。"""

    scheme_id: int
    name: str
    trial: bool
    config_mode: Literal["current", "original"] = "current"
    original_run_id: int | None = None
    steps: list[Node]
    skills: list[str]
    mcp: str | None
    mcp_signature: str | None = None
    model_profile_id: int | None
    model_profile_version: int | None


class CapabilityEvent(BaseModel):
    """执行步骤及持久化的辅助证据。"""

    id: int
    step: str
    path: str
    source: str
    status: str
    evidence: dict[str, object] | None
    created_at: str
