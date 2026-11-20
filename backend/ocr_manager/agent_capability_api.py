"""注册自建 Agent 管理接口，网络和 Git 检查一律交给 Worker。"""

import json
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.params import Depends
from fastapi.responses import JSONResponse

from ocr_manager.agent_capabilities import (
    audit,
    catalog,
    check_scheme,
    discovered_tools,
    get_default,
    get_scheme,
    get_service,
    read_project,
    save_project,
)
from ocr_manager.agent_capability_checks import queue_check
from ocr_manager.agent_capability_contracts import (
    CapabilityCatalog,
    CapabilityCheck,
    DefaultSchemeInput,
    EnabledInput,
    McpGrant,
    McpInput,
    PreviewInput,
    ProjectAgentInput,
    ProjectAgentSettings,
    SchemeDocument,
    SchemeInput,
    SchemeTrial,
    SkillInput,
)
from ocr_manager.agent_mcp import validate_endpoint
from ocr_manager.agent_pilot import PilotConflict
from ocr_manager.config import Settings
from ocr_manager.secrets import SecretBox
from ocr_manager.storage import Store

PATH = "/api/agent-capabilities"
PROJECT = "/api/repositories/{repository_id}/agent-settings"


@contextmanager
def _business_errors() -> Iterator[None]:
    try:
        yield
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except PilotConflict as error:
        raise HTTPException(409, {"code": error.code, "message": str(error)}) from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


def _actor(request: Request) -> str:
    if request.state.identity["role"] != "admin":
        raise HTTPException(403, "只有管理员可以查看和管理 Agent 配置")
    return str(request.state.identity["username"])


def register_agent_capability_api(app: FastAPI, store: Store, settings: Settings,
                                  access: Depends) -> None:
    """复用管理台会话并限制能力目录和设置读取权限。"""

    @app.exception_handler(RequestValidationError)
    async def safe_validation(request: Request, error: RequestValidationError) -> Response:
        if request.url.path == f"{PATH}/services" and request.method == "POST":
            return JSONResponse(status_code=422, content={"detail": "MCP 服务参数格式不正确"})
        return await request_validation_exception_handler(request, error)

    @app.get(PATH, dependencies=[access])
    def read_catalog(request: Request, response: Response) -> CapabilityCatalog:
        _actor(request)
        response.headers["Cache-Control"] = "no-store"
        with store.connection() as db:
            db.execute("BEGIN")
            return catalog(db)

    @app.post(f"{PATH}/skills", dependencies=[access], status_code=201)
    def create_skill(body: SkillInput, request: Request) -> dict[str, int]:
        actor = _actor(request)
        with store.connection() as db:
            ident = db.execute("""INSERT INTO agent_skills(name,pattern,body,actor)
                VALUES (?,?,?,?)""", (body.name, body.pattern, body.body, actor)).lastrowid
            assert ident is not None
            audit(db, actor, "skill_version", ident)
            return {"id": ident}

    @app.post(f"{PATH}/schemes", dependencies=[access], status_code=201)
    def create_scheme(body: SchemeInput, request: Request) -> dict[str, int]:
        actor = _actor(request)
        document = SchemeDocument.model_validate(body.model_dump(exclude={"name", "basis_id"}))
        with _business_errors(), store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if body.basis_id is not None:
                get_scheme(db, body.basis_id)
            ident = db.execute("""INSERT INTO agent_schemes(name,basis_id,document,state,actor)
                VALUES (?,?,?,'draft',?)""",
                (body.name, body.basis_id, document.model_dump_json(), actor)).lastrowid
            assert ident is not None
            check_scheme(db, get_scheme(db, ident), trial=True)
            audit(db, actor, "scheme_draft", ident)
            return {"id": ident}

    @app.put(f"{PATH}/schemes/{{scheme_id}}/publication", dependencies=[access], status_code=204)
    def set_publication(scheme_id: int, body: EnabledInput, request: Request) -> Response:
        actor = _actor(request)
        with _business_errors(), store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            scheme = get_scheme(db, scheme_id)
            state = "published" if body.enabled else "disabled"
            if scheme.state == state:
                return Response(status_code=204)
            if body.enabled:
                if scheme.state != "draft":
                    raise ValueError("停用版本请复制为新草稿后发布")
                check_scheme(db, scheme, trial=True)
            elif get_default(db) == scheme_id or scheme_id == 1:
                raise ValueError("请先切换默认方案；内置基础方案始终可用")
            db.execute("UPDATE agent_schemes SET state=? WHERE id=?", (state, scheme_id))
            audit(db, actor, "scheme_state", scheme_id, before=scheme.state, after=state)
        return Response(status_code=204)

    @app.put(f"{PATH}/schemes/{{scheme_id}}/default", dependencies=[access], status_code=204)
    def set_default(scheme_id: int, body: DefaultSchemeInput, request: Request) -> Response:
        actor = _actor(request)
        with _business_errors(), store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            before = get_default(db)
            if before != body.expected_id:
                raise ValueError("平台默认方案已更新，请刷新后重试")
            scheme = get_scheme(db, scheme_id)
            check_scheme(db, scheme, trial=False)
            if scheme.document.mcp:
                for row in db.execute("""SELECT p.repository_id FROM agent_review_pilots p
                    LEFT JOIN agent_project_settings a USING(repository_id)
                    WHERE a.scheme_id IS NULL"""):
                    check_scheme(db, scheme, trial=False, repository_id=row[0])
            db.execute("UPDATE agent_scheme_default SET scheme_id=? WHERE id=1", (scheme_id,))
            audit(db, actor, "scheme_default", scheme_id, before=before, after=scheme_id)
        return Response(status_code=204)

    @app.get(PROJECT, dependencies=[access])
    def get_project(repository_id: int, request: Request, response: Response
                    ) -> ProjectAgentSettings:
        _actor(request)
        response.headers["Cache-Control"] = "no-store"
        with _business_errors(), store.connection() as db:
            db.execute("BEGIN")
            return read_project(store, settings, db, repository_id)

    @app.put(PROJECT, dependencies=[access])
    def update_project(repository_id: int, body: ProjectAgentInput,
                       request: Request) -> ProjectAgentSettings:
        actor = _actor(request)
        with _business_errors():
            return save_project(store, settings, repository_id, body, actor)

    @app.post(f"{PATH}/services", dependencies=[access], status_code=201)
    def create_service(body: McpInput, request: Request) -> dict[str, int]:
        actor = _actor(request)
        with _business_errors(), store.connection() as db:
            validate_endpoint(body.endpoint)
            ciphertext = SecretBox(settings.master_key).encrypt(body.token) if body.token else None
            ident = db.execute("""INSERT INTO agent_mcp_services
                (name,endpoint,token_ciphertext,timeout_seconds,actor) VALUES (?,?,?,?,?)""",
                (body.name, body.endpoint, ciphertext, body.timeout_seconds, actor)).lastrowid
            assert ident is not None
            audit(db, actor, "mcp_service", ident)
            return {"id": ident}

    @app.put(f"{PATH}/services/{{service_id}}/enabled", dependencies=[access], status_code=204)
    def set_service_enabled(service_id: int, body: EnabledInput, request: Request) -> Response:
        actor = _actor(request)
        with _business_errors(), store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            service = get_service(db, service_id)
            db.execute("UPDATE agent_mcp_services SET enabled=? WHERE id=?",
                       (body.enabled, service_id))
            audit(db, actor, "mcp_enabled", service_id, before=bool(service["enabled"]),
                  after=body.enabled)
        return Response(status_code=204)

    @app.put(f"{PATH}/services/{{service_id}}/grants", dependencies=[access], status_code=204)
    def grant(service_id: int, body: McpGrant, request: Request) -> Response:
        actor = _actor(request)
        with _business_errors(), store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            service = get_service(db, service_id)
            if not service["enabled"] or body.tool not in discovered_tools(db, service_id):
                raise ValueError("请先测试连接并发现可用工具")
            if not db.execute("SELECT 1 FROM repositories WHERE id=?",
                              (body.repository_id,)).fetchone():
                raise LookupError("仓库不存在")
            db.execute("INSERT OR IGNORE INTO agent_mcp_grants VALUES (?,?,?)",
                       (service_id, body.repository_id, body.tool))
            audit(db, actor, "mcp_grant", service_id, repository_id=body.repository_id,
                  tool=body.tool)
        return Response(status_code=204)

    @app.delete(f"{PATH}/services/{{service_id}}/grants/{{repository_id}}/{{tool}}",
                dependencies=[access], status_code=204)
    def revoke(service_id: int, repository_id: int, tool: str, request: Request) -> Response:
        actor = _actor(request)
        with _business_errors(), store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            get_service(db, service_id)
            db.execute("DELETE FROM agent_mcp_grants WHERE service_id=? "
                       "AND repository_id=? AND tool=?", (service_id, repository_id, tool))
            audit(db, actor, "mcp_revoke", service_id, repository_id=repository_id, tool=tool)
        return Response(status_code=204)

    @app.post(f"{PATH}/services/{{service_id}}/checks", dependencies=[access], status_code=202)
    def check_service(service_id: int, request: Request) -> dict[str, int]:
        actor = _actor(request)
        with _business_errors(), store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if not get_service(db, service_id)["enabled"]:
                raise ValueError("请先启用 MCP 服务")
            ident = queue_check(db, "mcp", service_id)
            audit(db, actor, "mcp_check", service_id, check_id=ident)
            return {"id": ident}

    @app.post(f"{PATH}/schemes/{{scheme_id}}/previews", dependencies=[access], status_code=202)
    def preview(scheme_id: int, body: PreviewInput, request: Request) -> dict[str, int]:
        actor = _actor(request)
        with _business_errors(), store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            check_scheme(db, get_scheme(db, scheme_id), trial=True)
            ident = queue_check(db, "preview", scheme_id, body.job_id)
            audit(db, actor, "scheme_preview", scheme_id, check_id=ident, job_id=body.job_id)
            return {"id": ident}

    @app.get(f"{PATH}/schemes/{{scheme_id}}/trials", dependencies=[access])
    def trials(scheme_id: int, request: Request, response: Response) -> list[SchemeTrial]:
        _actor(request)
        response.headers["Cache-Control"] = "no-store"
        with _business_errors(), store.connection() as db:
            get_scheme(db, scheme_id)
            return [SchemeTrial.model_validate(dict(row)) for row in db.execute("""
                SELECT a.id,a.job_id,a.status,a.created_at FROM agent_run_capabilities c
                JOIN agent_reviews a ON a.id=c.run_id
                WHERE json_extract(c.snapshot,'$.scheme_id')=?
                  AND json_extract(c.snapshot,'$.trial')=1
                ORDER BY c.run_id DESC LIMIT 10""", (scheme_id,))]

    @app.get(f"{PATH}/checks/{{check_id}}", dependencies=[access])
    def get_check(check_id: int, request: Request, response: Response) -> CapabilityCheck:
        _actor(request)
        response.headers["Cache-Control"] = "no-store"
        with store.connection() as db:
            row = db.execute("SELECT * FROM agent_capability_checks WHERE id=?",
                             (check_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "检查记录不存在")
        return CapabilityCheck(id=row["id"], kind=row["kind"], status=row["status"],
                               result=json.loads(row["result_json"] or "null"))
