"""短事务管理 Agent 方案发布、项目选择和运行授权。"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, cast

from ocr_manager.agent_capability_contracts import (
    CapabilityCatalog,
    CapabilityRun,
    McpGrant,
    McpLookup,
    McpService,
    ProjectAgentInput,
    ProjectAgentSettings,
    SchemeDocument,
    SchemeSummary,
    SkillVersion,
)
from ocr_manager.agent_pilot import can_manage_pilot, repository_agent_config, set_repository_pilot
from ocr_manager.agent_review_config import AgentReviewConfig
from ocr_manager.agent_review_profile import resolve_model
from ocr_manager.config import Settings
from ocr_manager.storage import Store


def audit(db: sqlite3.Connection, actor: str, action: str, ident: int,
          **changes: object) -> None:
    """与业务写入同事务记录操作者及前后版本。"""

    db.execute("""INSERT INTO agent_capability_audit(actor,action,subject_id,change_json)
        VALUES (?,?,?,?)""", (actor, action, ident, json.dumps(changes, ensure_ascii=False)))


def _scheme(row: sqlite3.Row) -> SchemeSummary:
    return SchemeSummary.model_validate({
        **dict(row), "document": SchemeDocument.model_validate_json(row["document"]),
    })


def get_scheme(db: sqlite3.Connection, ident: int) -> SchemeSummary:
    """按版本获取方案；运行和发布分别校验允许的状态。"""

    row = db.execute("SELECT * FROM agent_schemes WHERE id=?", (ident,)).fetchone()
    if row is None:
        raise LookupError("评审方案版本不存在")
    return _scheme(row)


def get_skills(db: sqlite3.Connection, document: SchemeDocument) -> list[SkillVersion]:
    """保持方案指定的 Skill 顺序。"""

    versions = []
    for ident in document.skill_ids:
        row = db.execute("SELECT * FROM agent_skills WHERE id=?", (ident,)).fetchone()
        if row is None:
            raise ValueError("所选 Skill 版本不存在")
        versions.append(SkillVersion.model_validate(dict(row)))
    return versions


def discovered_tools(db: sqlite3.Connection, service_id: int) -> dict[str, dict[str, Any]]:
    """最近一次成功发现仅提供可用于规范检索的工具。"""

    row = db.execute("""SELECT result_json FROM agent_capability_checks WHERE kind='mcp'
        AND subject_id=? AND status='complete' ORDER BY id DESC LIMIT 1""",
                     (service_id,)).fetchone()
    return json.loads(row[0])["tools"] if row else {}


def get_service(db: sqlite3.Connection, ident: int) -> sqlite3.Row:
    """读取服务版本，凭据只供后端执行器使用。"""

    row = db.execute("SELECT * FROM agent_mcp_services WHERE id=?", (ident,)).fetchone()
    if row is None:
        raise LookupError("MCP 服务不存在")
    return cast(sqlite3.Row, row)


def check_mcp(db: sqlite3.Connection, lookup: McpLookup,
              repository_id: int | None = None) -> sqlite3.Row:
    """连接前检查禁用、工具签名和仓库授权。"""

    service = get_service(db, lookup.service_id)
    if not service["enabled"]:
        raise ValueError("MCP 服务已停用")
    tool = discovered_tools(db, lookup.service_id).get(lookup.tool)
    if tool is None or lookup.argument not in tool["arguments"]:
        raise ValueError("请先发现可用的 MCP 只读工具并核对查询参数")
    if repository_id is not None and not db.execute("""SELECT 1 FROM agent_mcp_grants
        WHERE service_id=? AND repository_id=? AND tool=?""",
        (lookup.service_id, repository_id, lookup.tool)).fetchone():
        raise ValueError("此仓库未获得该 MCP 工具的授权")
    return service


def tool_signature(tool: dict[str, Any]) -> str:
    """摘要绑定获准的输入契约，忽略说明文案的修改。"""

    return str(tool["signature"])


def check_scheme(db: sqlite3.Connection, scheme: SchemeSummary, *, trial: bool,
                 repository_id: int | None = None) -> list[SkillVersion]:
    """检查方案状态与版本引用，草稿仅能用于试跑。"""

    if scheme.state == "disabled" or (not trial and scheme.state != "published"):
        raise ValueError("该评审方案未发布或已停用")
    skills = get_skills(db, scheme.document)
    if scheme.document.mcp:
        check_mcp(db, scheme.document.mcp, repository_id)
    return skills


def get_default(db: sqlite3.Connection) -> int:
    """读取平台当前默认方案。"""

    row = db.execute("SELECT scheme_id FROM agent_scheme_default WHERE id=1").fetchone()
    return int(row[0])


def project_selection(db: sqlite3.Connection, repository_id: int) -> sqlite3.Row | None:
    """空绑定代表继承默认方案及项目模型。"""

    return cast(sqlite3.Row | None, db.execute(
        "SELECT * FROM agent_project_settings WHERE repository_id=?", (repository_id,),
    ).fetchone())


def effective_scheme(db: sqlite3.Connection, repository_id: int) -> SchemeSummary:
    """固定版优先，空绑定继承当前平台默认。"""

    selected = project_selection(db, repository_id)
    return get_scheme(db, (selected["scheme_id"] if selected else None) or get_default(db))


def read_project(store: Store, settings: Settings, db: sqlite3.Connection,
                 repository_id: int) -> ProjectAgentSettings:
    """解析管理页实际生效的方案、模型和不可用原因。"""

    repository = db.execute("SELECT enabled FROM repositories WHERE id=?",
                            (repository_id,)).fetchone()
    if repository is None:
        raise LookupError("仓库不存在")
    selected = project_selection(db, repository_id)
    scheme = effective_scheme(db, repository_id)
    model_id = selected["model_profile_id"] if selected else None
    config = repository_agent_config(db, settings, repository_id)
    resolved = None
    reason = None
    if not repository["enabled"]:
        reason = "请先启用该仓库"
    try:
        check_scheme(db, scheme, trial=False, repository_id=repository_id)
    except ValueError as error:
        reason = reason or str(error)
    try:
        resolved = resolve_model(
            store, config or AgentReviewConfig("", "", frozenset({repository_id}), "",
                                                model_source="project"),
            repository_id, profile_id=model_id, db=db,
        ).model
    except ValueError as error:
        reason = reason or str(error)
    return ProjectAgentSettings(
        version=selected["version"] if selected else 0, enabled=config is not None,
        manageable=can_manage_pilot(settings, repository_id), effective_scheme=scheme,
        scheme_id=selected["scheme_id"] if selected else None, model_profile_id=model_id,
        effective_model=resolved, unavailable_reason=reason,
    )


def save_project(store: Store, settings: Settings, repository_id: int,
                 body: ProjectAgentInput, actor: str) -> ProjectAgentSettings:
    """在同一写锁内保存配置与既有试点授权。"""

    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        before = read_project(store, settings, db, repository_id)
        if before.version != body.version:
            raise ValueError("项目设置已更新，请刷新后重试")
        scheme = get_scheme(db, body.scheme_id or get_default(db))
        if body.enabled or body.scheme_id != before.scheme_id:
            check_scheme(db, scheme, trial=False, repository_id=repository_id)
        if body.enabled or body.model_profile_id is not None:
            resolve_model(store, AgentReviewConfig("", "", frozenset({repository_id}), "",
                         model_source="project"), repository_id,
                         profile_id=body.model_profile_id, db=db)
        repository = db.execute("SELECT id,enabled FROM repositories WHERE id=?",
                                (repository_id,)).fetchone()
        set_repository_pilot(db, store, settings, repository, body.enabled, actor,
                             body.model_profile_id)
        db.execute("""INSERT INTO agent_project_settings VALUES (?,?,?,?)
            ON CONFLICT(repository_id) DO UPDATE SET scheme_id=excluded.scheme_id,
            model_profile_id=excluded.model_profile_id,version=excluded.version""",
            (repository_id, body.scheme_id, body.model_profile_id, body.version + 1))
        audit(db, actor, "project", repository_id, previous=before.version,
              version=body.version + 1, from_scheme=before.scheme_id, to_scheme=body.scheme_id,
              from_model=before.model_profile_id, to_model=body.model_profile_id,
              from_enabled=before.enabled, to_enabled=body.enabled)
        return read_project(store, settings, db, repository_id)


def freeze_capabilities(db: sqlite3.Connection, scheme: SchemeSummary, repository_id: int,
                        config: AgentReviewConfig, *, trial: bool) -> CapabilityRun:
    """记录不可变版本引用和用于显示的名称。"""

    skills = check_scheme(db, scheme, trial=trial, repository_id=repository_id)
    lookup = scheme.document.mcp
    service = get_service(db, lookup.service_id) if lookup else None
    profile_id, version = config.profile_reference or (None, None)
    return CapabilityRun(
        scheme_id=scheme.id, name=scheme.name, trial=trial, steps=scheme.document.steps,
        skills=[f"{item.name} #{item.id}" for item in skills],
        mcp=f"{service['name']} #{service['id']} / {lookup.tool}" if lookup and service else None,
        mcp_signature=(tool_signature(discovered_tools(db, lookup.service_id)[lookup.tool])
                       if lookup else None),
        model_profile_id=profile_id, model_profile_version=version,
    )


def catalog(db: sqlite3.Connection) -> CapabilityCatalog:
    """枚举管理台目录，任何服务令牌都不离开存储层。"""

    services = list(db.execute("SELECT * FROM agent_mcp_services ORDER BY id DESC"))
    return CapabilityCatalog(default_id=get_default(db),
        inheriting_projects=[row[0] for row in db.execute("""
            SELECT r.id FROM repositories r LEFT JOIN agent_project_settings a
            ON a.repository_id=r.id WHERE a.scheme_id IS NULL ORDER BY r.id""")],
        project_bindings={row[0]: row[1] for row in db.execute("""
            SELECT repository_id,scheme_id FROM agent_project_settings WHERE scheme_id IS NOT NULL
            ORDER BY repository_id""")},
        schemes=[_scheme(row) for row in db.execute(
            "SELECT * FROM agent_schemes ORDER BY id DESC")],
        skills=[SkillVersion.model_validate(dict(row)) for row in db.execute(
            "SELECT * FROM agent_skills ORDER BY id DESC")],
        services=[McpService(
            id=row["id"], name=row["name"], endpoint=row["endpoint"], enabled=bool(row["enabled"]),
            timeout_seconds=row["timeout_seconds"], has_token=bool(row["token_ciphertext"]),
            tools=discovered_tools(db, row["id"]),
            grants=[McpGrant.model_validate(dict(grant)) for grant in db.execute(
                """SELECT repository_id,tool FROM agent_mcp_grants WHERE service_id=?
                ORDER BY repository_id,tool""", (row["id"],))],
        ) for row in services])
