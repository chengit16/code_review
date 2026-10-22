"""暴露管理 API 与轻量 GitLab webhook 接收端。"""

from __future__ import annotations

import hmac
import json
import logging
import re
import sqlite3
from decimal import Decimal
from pathlib import Path, PurePosixPath
from secrets import token_urlsafe
from typing import Any, Literal
from urllib.parse import urlparse

from cryptography.fernet import InvalidToken
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.routing import APIRoute
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles

from ocr_manager.alerts_api import register_alerts
from ocr_manager.auth import register_auth, session_identity, users_mode
from ocr_manager.config import Settings, load_settings
from ocr_manager.event_search import register_event_search
from ocr_manager.gitlab import project_web_url
from ocr_manager.model_pricing import estimate_cost
from ocr_manager.operations_api import register_operations
from ocr_manager.premerge import (
    enqueue_premerge,
    invalidate_premerge,
    parse_premerge_event,
    register_premerge,
)
from ocr_manager.project_limits_api import register_project_limits
from ocr_manager.publications import register_publications
from ocr_manager.review_effectiveness import register_effectiveness
from ocr_manager.review_issues import register_review_issues
from ocr_manager.secrets import SecretBox
from ocr_manager.storage import Store
from ocr_manager.task_control import register_task_control
from ocr_manager.webhook import parse_merge_event, verify_webhook
from ocr_manager.worker import config_hash, worker_is_running

LOGGER = logging.getLogger(__name__)


class RepositoryCreate(BaseModel):
    """接入 GitLab 项目；Secret token 可省略并由服务端生成。"""

    name: str = Field(min_length=1, max_length=120)
    gitlab_url: str
    project_id: int = Field(gt=0)
    remote_url: str
    target_branch: str = Field(min_length=1, max_length=200)
    auth_kind: Literal["signing", "secret"] = "secret"
    webhook_token: str | None = Field(default=None, min_length=16)
    feishu_webhook: str | None = None
    feishu_target_id: int | None = Field(default=None, gt=0)
    path_with_namespace: str | None = None
    gitlab_token: str | None = None
    enable_merge_requests: bool = True
    enable_default_branch_pushes: bool = False

    model_config = {"extra": "forbid"}


class RepositoryUpdate(BaseModel):
    """接入设置；项目身份只允许在业务投递前纠正。"""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    gitlab_url: str | None = None
    project_id: int | None = Field(default=None, gt=0)
    remote_url: str | None = None
    path_with_namespace: str | None = None
    target_branch: str | None = Field(default=None, min_length=1, max_length=200)
    enabled: bool | None = None
    auth_kind: Literal["signing", "secret"] | None = None
    webhook_token: str | None = Field(default=None, min_length=16)
    feishu_webhook: str | None = None
    feishu_target_id: int | None = Field(default=None, gt=0)
    webhook_id: str | None = Field(default=None, max_length=100)
    gitlab_token: str | None = None
    enable_merge_requests: bool | None = None
    enable_default_branch_pushes: bool | None = None

    model_config = {"extra": "forbid"}


class ReviewRuleEntry(BaseModel):
    """按声明顺序匹配文件路径；合并开关只合并 OCR 内置规则。"""

    path: str = Field(min_length=1, max_length=500)
    rule: str = Field(min_length=1, max_length=20000)
    merge_system_rule: bool = False

    model_config = {"extra": "forbid"}


class ReviewRuleDocument(BaseModel):
    """与 OCR rule.json 格式一致，避免管理页保存无法解析的自由结构。"""

    include: list[str] = Field(default_factory=list, max_length=100)
    exclude: list[str] = Field(default_factory=list, max_length=100)
    rules: list[ReviewRuleEntry] = Field(default_factory=list, max_length=100)

    model_config = {"extra": "forbid"}


class ProjectNotificationPolicy(BaseModel):
    """项目通知卡片的重点发现级别；完整结论仍包含所有发现。"""

    minimum_severity: Literal["critical", "high", "medium", "low"]

    model_config = {"extra": "forbid"}


class ReviewFeedbackInput(BaseModel):
    """人工标记单条发现，可在重评审前修改或撤销。"""

    verdict: Literal["helpful", "false_positive", "fixed"]

    model_config = {"extra": "forbid"}


class RulePreviewInput(BaseModel):
    """规则预览只接受仓库内相对文件路径，不能选择外部工作目录。"""

    file_path: str = Field(min_length=1, max_length=500)

    model_config = {"extra": "forbid"}


class ModelProfileCreate(BaseModel):
    """OCR 模型可来自内置 provider 或 OpenAI 兼容端点。"""

    name: str = Field(min_length=1, max_length=120)
    model: str = Field(min_length=1, max_length=160)
    base_url: str = ""
    api_key: str = Field(min_length=1)
    provider: str = Field(default="dashscope", pattern=r"^[a-zA-Z0-9_-]+$")
    price_currency: Literal["CNY", "USD"] = "CNY"
    input_price_per_million: Decimal | None = Field(default=None, ge=0, max_digits=14,
                                                    decimal_places=6)
    output_price_per_million: Decimal | None = Field(default=None, ge=0, max_digits=14,
                                                     decimal_places=6)

    model_config = {"extra": "forbid"}


class ModelProfileUpdate(BaseModel):
    """编辑模型时省略 API key 表示沿用加密保存的原密钥。"""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    model: str | None = Field(default=None, min_length=1, max_length=160)
    base_url: str | None = None
    api_key: str | None = Field(default=None, min_length=1)
    provider: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9_-]+$")
    price_currency: Literal["CNY", "USD"] | None = None
    input_price_per_million: Decimal | None = Field(default=None, ge=0, max_digits=14,
                                                    decimal_places=6)
    output_price_per_million: Decimal | None = Field(default=None, ge=0, max_digits=14,
                                                     decimal_places=6)

    model_config = {"extra": "forbid"}


class NotificationTargetCreate(BaseModel):
    """独立的飞书机器人配置，可由多个仓库引用。"""

    name: str = Field(min_length=1, max_length=120)
    webhook_url: str
    signing_secret: str = ""

    model_config = {"extra": "forbid"}


class NotificationTargetUpdate(BaseModel):
    """空签名密钥表示关闭签名；省略凭据表示保留原值。"""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    webhook_url: str | None = None
    signing_secret: str | None = None

    model_config = {"extra": "forbid"}


class ConnectionCheckInput(BaseModel):
    """诊断目标由服务端配置决定，浏览器不能传入外部 URL。"""

    kind: Literal["git", "gitlab", "model", "feishu"]
    repository_id: int | None = Field(default=None, gt=0)

    model_config = {"extra": "forbid"}


class FrontendFiles(StaticFiles):
    """前端深链路回退到入口页；带扩展名的缺失资源仍返回 404。"""

    async def get_response(self, path: str, scope: Any) -> Response:
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as error:
            if error.status_code == 404 and "." not in Path(path).name:
                return await super().get_response("index.html", scope)
            raise
        if response.status_code == 404 and "." not in Path(path).name:
            return await super().get_response("index.html", scope)
        return response


def validate_remote(gitlab_url: str, remote_url: str) -> bool:
    """只接受同源且无内嵌口令的 Git 地址；新配置优先使用 HTTPS。"""

    gitlab = urlparse(gitlab_url)
    host = gitlab.hostname
    scp = re.fullmatch(r"git@([a-zA-Z0-9.-]+):([^\s]+)", remote_url)
    if scp:
        return scp.group(1).lower() == host and not scp.group(2).startswith("-")
    remote = urlparse(remote_url)
    if remote.scheme == "https":
        try:
            # 端口也是 GitLab 实例身份的一部分；无效端口应作为输入错误返回。
            return (
                remote.hostname == host
                and remote.port == gitlab.port
                and remote.username is None
                and remote.password is None
                and bool(remote.path.strip("/"))
                and remote.path.endswith(".git")
                and not remote.query
                and not remote.fragment
            )
        except ValueError:
            return False
    return (
        remote.scheme == "ssh"
        and remote.username == "git"
        and remote.password is None
        and remote.hostname == host
        and bool(remote.path.strip("/"))
        and not remote.path.startswith("/-")
        and not remote.query
        and not remote.fragment
    )


def validate_repository_source(
    gitlab_url: str,
    remote_url: str,
    path_with_namespace: str | None,
    target_branch: str,
    has_gitlab_token: bool,
) -> tuple[str, str]:
    """新增与修改共用来源校验，避免编辑绕过同源、分支和凭据约束。"""

    gitlab = urlparse(gitlab_url)
    if (
        gitlab.scheme != "https"
        or not gitlab.hostname
        or gitlab.username
        or gitlab.password
        or gitlab.query
        or gitlab.fragment
    ):
        raise HTTPException(status_code=422, detail="GitLab 地址必须是 HTTPS 主机")
    if not validate_remote(gitlab_url, remote_url):
        raise HTTPException(
            status_code=422, detail="Git 地址必须是同一 GitLab 主机的无凭据 HTTPS 或 SSH 地址"
        )
    remote_path = (
        urlparse(remote_url).path.lstrip("/")
        if remote_url.startswith("https://")
        else remote_url.split(":", 1)[-1].lstrip("/")
    ).removesuffix(".git")
    if path_with_namespace and path_with_namespace != remote_path:
        raise HTTPException(status_code=422, detail="仓库路径与 Clone URL 不一致")
    if remote_url.startswith("https://") and not has_gitlab_token:
        raise HTTPException(status_code=422, detail="HTTPS 仓库必须填写 GitLab Token")
    if (
        not re.fullmatch(r"[a-zA-Z0-9._/-]+", target_branch)
        or target_branch.startswith(("-", "/", "."))
        or target_branch.endswith(("/", "."))
        or ".." in target_branch
        or "//" in target_branch
    ):
        raise HTTPException(status_code=422, detail="目标分支名称无效")
    return gitlab_url.rstrip("/"), remote_path


def validate_feishu_webhook(url: str) -> bool:
    """只接受飞书官方 HTTPS webhook，避免服务器向任意地址发送投递内容。"""

    parsed = urlparse(url)
    return (
        parsed.scheme == "https"
        and parsed.hostname in {"open.feishu.cn", "open.larksuite.com"}
        and parsed.username is None
        and parsed.password is None
        and parsed.path.startswith("/open-apis/bot/v2/hook/")
    )


def public_repository(row: dict[str, Any], public_url: str) -> dict[str, Any]:
    """生成不含密钥或密文的管理页仓库信息，并标记飞书 Hook 是否已配置。"""

    return {
        key: value
        for key, value in row.items()
        if key not in {"webhook_secret", "feishu_webhook", "gitlab_token_ciphertext"}
    } | {
        "webhook_url": f"{public_url}/api/webhooks/gitlab",
        "has_feishu_webhook": bool(row.get("feishu_target_id") or row.get("feishu_webhook")),
        "has_gitlab_token": bool(row.get("gitlab_token_ciphertext")),
    }


def public_notification_target(row: dict[str, Any]) -> dict[str, Any]:
    """管理列表只返回通道元数据，密文和明文均不进入浏览器缓存。"""

    return {
        key: value
        for key, value in row.items()
        if key not in {"webhook_ciphertext", "signing_secret_ciphertext"}
    } | {"has_signing_secret": bool(row["signing_secret_ciphertext"])}


def public_model_profile(row: dict[str, Any]) -> dict[str, Any]:
    """模型列表只暴露 provider、端点和是否配置密钥。"""

    return {key: value for key, value in row.items() if key != "api_key_ciphertext"} | {
        "has_api_key": bool(row["api_key_ciphertext"])
    }


def validate_model_endpoint(base_url: str) -> str:
    """自定义 OCR 端点只能使用无凭据 HTTPS 地址。"""

    endpoint = base_url.strip().rstrip("/")
    if endpoint:
        parsed = urlparse(endpoint)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise HTTPException(status_code=422, detail="Base URL 必须是无凭据的 HTTPS 地址")
    return endpoint


def validate_model_prices(input_price: object, output_price: object) -> None:
    """输入和输出单价须成对提供，否则详情页无法给出完整费用。"""

    if (input_price is None) != (output_price is None):
        raise HTTPException(status_code=422, detail="请同时填写或清空输入、输出 Token 单价")


def create_app(settings: Settings | None = None) -> FastAPI:
    """组装 API、数据库和密钥边界；测试可传入隔离配置。"""

    config = settings or load_settings()
    store = Store(config.data_dir / "app.db")
    store.migrate()
    secrets = SecretBox(config.master_key)
    app = FastAPI(title="Open Code Review 管理平台")

    @app.middleware("http")
    async def audit_management(request: Request, call_next: Any) -> Response:
        """管理写操作按稳定路由记录结果；请求体与密钥从不进入审计表。"""

        response: Response = await call_next(request)
        route = request.scope.get("route")
        if request.method in {"POST", "PATCH", "PUT", "DELETE"} and isinstance(route, APIRoute):
            if route.path.startswith("/api/") and not route.path.startswith("/api/webhooks/"):
                resource = route.path.split("/")[2]
                object_type = {
                    "repositories": "repository",
                    "review-rules": "review_rule",
                    "notification-targets": "notification_target",
                    "model-profiles": "model_profile",
                    "connection-checks": "connection_check",
                    "events": "merge_event",
                    "jobs": "review_job",
                }.get(resource, "management")
                params = request.path_params
                object_id = next(
                    (
                        params[name]
                        for name in (
                            "repository_id", "target_id", "event_id", "job_id",
                            "profile_id", "object_id",
                        )
                        if name in params
                    ),
                    None,
                )
                outcome = (
                    "success" if response.status_code < 400 else f"http_{response.status_code}"
                )
                try:
                    identity = getattr(request.state, "identity", None)
                    store.record_audit(
                        f"{request.method} {route.path}", object_type, object_id, outcome,
                        identity["id"] if identity else None,
                        identity["username"] if identity else None,
                    )
                except sqlite3.Error:
                    # 审计写入异常不能让已提交的配置操作向客户端伪装成失败。
                    LOGGER.exception("管理操作审计记录失败")
        return response

    def require_admin(request: Request) -> dict[str, Any]:
        """账号模式按角色授权；默认模式兼容本机开发与共享口令。"""

        if users_mode(store):
            header = request.headers.get("authorization", "")
            token = header.removeprefix("Bearer ") if header.startswith("Bearer ") else ""
            identity = session_identity(store, token) if token else None
            if identity is None:
                raise HTTPException(status_code=401, detail="管理会话无效或已过期")
        elif config.dev_mode:
            identity = {"id": None, "username": "本机开发", "role": "admin"}
        else:
            token = request.headers.get("x-admin-token", "")
            if not token or not hmac.compare_digest(token, config.admin_token):
                raise HTTPException(status_code=401, detail="管理口令无效")
            identity = {"id": None, "username": "共享管理员", "role": "admin"}
        request.state.identity = identity
        if (identity["role"] != "admin" and request.method not in {"GET", "HEAD"}
            and request.url.path != "/api/auth/logout"):
            raise HTTPException(status_code=403, detail="只读用户不能修改配置或任务")
        if (identity["role"] != "admin" and
            request.url.path.endswith("/webhook-token")):
            raise HTTPException(status_code=403, detail="只有管理员可以查看 Webhook Token")
        return identity

    admin = Depends(require_admin)
    register_auth(app, store, require_admin)
    register_operations(app, store, config, admin)
    register_task_control(app, store, config, admin)
    register_alerts(app, store, admin)
    register_project_limits(app, store, admin)
    register_event_search(app, store, admin)
    register_publications(app, store, admin)
    register_review_issues(app, store, admin)
    register_effectiveness(app, store, admin)
    register_premerge(app, store, admin)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        """检查 API、SQLite、鉴权模式与独立 Worker；API 存活不代表队列正在消费。"""

        with store.connection() as db:
            db.execute("SELECT 1")
        return {
            "status": "ok",
            "auth_mode": "users" if users_mode(store) else
                "dev" if config.dev_mode else "admin",
            "worker": "running" if worker_is_running(config.data_dir) else "stopped",
        }

    @app.get("/api/repositories", dependencies=[admin])
    def list_repositories() -> list[dict[str, Any]]:
        """列出已接入仓库；密钥仅由单项查看接口按需返回。"""

        return [
            public_repository(row, config.webhook_base_url) for row in store.list_repositories()
        ]

    @app.get("/api/review-rules", dependencies=[admin])
    def list_review_rules() -> list[dict[str, Any]]:
        """规则正文是非凭据配置；项目规则由管理台按项目选择编辑。"""

        return [
            {**row, "content": json.loads(row["content"])} for row in store.list_review_rules()
        ]

    @app.get("/api/review-feedback/summary", dependencies=[admin])
    def review_feedback_summary() -> list[dict[str, Any]]:
        """反馈统计以已标记发现为分母，未标记发现不推断为有用或误报。"""

        return store.feedback_summary()

    @app.put("/api/repositories/{repository_id}/notification-policy", dependencies=[admin])
    def put_notification_policy(
        repository_id: int, payload: ProjectNotificationPolicy
    ) -> dict[str, str]:
        """保存项目通知阈值；未完成事件或任务阻止快照变更。"""

        try:
            store.set_project_policy(repository_id, payload.minimum_severity)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {"minimum_severity": payload.minimum_severity}

    @app.get("/api/repositories/{repository_id}/rule-previews", dependencies=[admin])
    def list_rule_previews(repository_id: int) -> list[dict[str, Any]]:
        """显示指定仓库最近的规则预览及执行时固定的提交 SHA。"""

        if store.get_repository(repository_id) is None:
            raise HTTPException(status_code=404, detail="仓库不存在")
        return store.list_rule_previews(repository_id)

    @app.post(
        "/api/repositories/{repository_id}/rule-previews",
        dependencies=[admin], status_code=202,
    )
    def enqueue_rule_preview(repository_id: int, payload: RulePreviewInput) -> dict[str, int | str]:
        """HTTP 只验证路径并入队；Git 与 OCR 在 Worker 中执行。"""

        if store.get_repository(repository_id) is None:
            raise HTTPException(status_code=404, detail="仓库不存在")
        path = payload.file_path
        parts = PurePosixPath(path).parts
        if (
            path != path.strip() or path.startswith(("/", "-"))
            or "\\" in path or "\x00" in path or any(ord(char) < 32 for char in path)
            or not parts or any(part in {".", ".."} for part in path.split("/"))
        ):
            raise HTTPException(status_code=422, detail="请输入仓库内的相对文件路径")
        preview_id = store.enqueue_rule_preview(repository_id, path)
        return {"id": preview_id, "status": "queued"}

    def change_review_rule(
        repository_id: int | None, payload: ReviewRuleDocument | None
    ) -> dict[str, str]:
        """统一处理全局和项目规则，并限制空配置与过大正文。"""

        if payload is not None:
            document = payload.model_dump()
            if not any(document.values()):
                raise HTTPException(status_code=422, detail="请至少配置一条规则或过滤路径")
            if any(not path.strip() for path in document["include"] + document["exclude"]):
                raise HTTPException(status_code=422, detail="路径模式不能为空")
            content = json.dumps(document, ensure_ascii=False, separators=(",", ":"))
            if len(content.encode("utf-8")) > 65536:
                raise HTTPException(status_code=422, detail="审核规则不能超过 64 KiB")
        else:
            content = None
        try:
            changed = store.change_review_rule(repository_id, content)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        if content is None and not changed:
            raise HTTPException(status_code=404, detail="审核规则不存在")
        return {"status": "saved" if content is not None else "deleted"}

    @app.put("/api/review-rules/global", dependencies=[admin])
    def put_global_review_rule(payload: ReviewRuleDocument) -> dict[str, str]:
        """全局配置写入每次 OCR 的隔离 HOME，作为仓库规则的后备层。"""

        return change_review_rule(None, payload)

    @app.delete("/api/review-rules/global", dependencies=[admin])
    def delete_global_review_rule() -> dict[str, str]:
        return change_review_rule(None, None)

    @app.put("/api/review-rules/repositories/{repository_id}", dependencies=[admin])
    def put_repository_review_rule(
        repository_id: int, payload: ReviewRuleDocument
    ) -> dict[str, str]:
        """管理台项目规则通过 OCR --rule 置于版本化仓库规则之上。"""

        return change_review_rule(repository_id, payload)

    @app.delete("/api/review-rules/repositories/{repository_id}", dependencies=[admin])
    def delete_repository_review_rule(repository_id: int) -> dict[str, str]:
        """删除项目规则，保留历史版本以便恢复。"""

        return change_review_rule(repository_id, None)

    def rule_revisions(repository_id: int | None) -> list[dict[str, Any]]:
        """历史正文仅在管理鉴权之后返回，删除后的版本仍可查看。"""

        if repository_id is not None and store.get_repository(repository_id) is None:
            raise HTTPException(status_code=404, detail="仓库不存在")
        return [
            {**row, "content": json.loads(row["content"]) if row["content"] else None}
            for row in store.list_review_rule_revisions(repository_id)
        ]

    def restore_rule(repository_id: int | None, revision_id: int) -> dict[str, str]:
        """历史版本恢复仍受未完成任务保护，并生成新的可追溯版本。"""

        try:
            store.restore_review_rule(repository_id, revision_id)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {"status": "restored"}

    @app.get("/api/review-rules/global/revisions", dependencies=[admin])
    def global_rule_revisions() -> list[dict[str, Any]]:
        """列出全局规则的最近 50 个版本。"""

        return rule_revisions(None)

    @app.post("/api/review-rules/global/revisions/{revision_id}/restore", dependencies=[admin])
    def restore_global_rule(revision_id: int) -> dict[str, str]:
        """恢复全局规则并重新计算后续任务快照。"""

        return restore_rule(None, revision_id)

    @app.get("/api/review-rules/repositories/{repository_id}/revisions", dependencies=[admin])
    def repository_rule_revisions(repository_id: int) -> list[dict[str, Any]]:
        """列出项目规则的最近 50 个版本。"""

        return rule_revisions(repository_id)

    @app.post(
        "/api/review-rules/repositories/{repository_id}/revisions/{revision_id}/restore",
        dependencies=[admin],
    )
    def restore_repository_rule(repository_id: int, revision_id: int) -> dict[str, str]:
        """恢复指定项目的一个规则版本。"""

        return restore_rule(repository_id, revision_id)

    @app.get("/api/repositories/{repository_id}/webhook-token", dependencies=[admin])
    def get_webhook_token(repository_id: int, response: Response,
                          request: Request) -> dict[str, str]:
        """管理员按需查看已有令牌，响应禁止缓存且审计不记录明文。"""

        response.headers["Cache-Control"] = "no-store"
        row = store.get_repository(repository_id)
        if row is None:
            raise HTTPException(status_code=404, detail="仓库不存在")
        try:
            token = secrets.decrypt(row["webhook_secret"])
        except InvalidToken as error:
            raise HTTPException(status_code=503, detail="Webhook 密钥不可用") from error
        try:
            store.record_audit(
                "GET /api/repositories/{repository_id}/webhook-token",
                "repository",
                repository_id,
                "success",
                request.state.identity["id"],
                request.state.identity["username"],
            )
        except sqlite3.Error:
            LOGGER.exception("Webhook 令牌查看审计记录失败")
        return {"webhook_token": token}

    @app.post("/api/repositories/{repository_id}/webhook-token/rotate", dependencies=[admin])
    def rotate_webhook_token(repository_id: int) -> dict[str, str]:
        """服务端生成新 Secret；GitLab 中的令牌必须同步更新才能继续投递。"""

        row = store.get_repository(repository_id)
        if row is None:
            raise HTTPException(status_code=404, detail="仓库不存在")
        if row["auth_kind"] != "secret":
            raise HTTPException(status_code=409, detail="Signing token 须在 GitLab 生成后录入")
        store.update_repository(
            repository_id, {"webhook_secret": secrets.encrypt(token_urlsafe(32))}
        )
        return {"status": "rotated"}

    @app.get("/api/audit-logs", dependencies=[admin])
    def list_audit_logs(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
    ) -> dict[str, Any]:
        """分页展示管理写操作及 HTTP 结果，不返回请求内容。"""

        return store.list_audit(page, page_size)

    @app.get("/api/notification-targets", dependencies=[admin])
    def list_notification_targets() -> list[dict[str, Any]]:
        return [public_notification_target(row) for row in store.list_notification_targets()]

    @app.post("/api/notification-targets", dependencies=[admin], status_code=201)
    def create_notification_target(payload: NotificationTargetCreate) -> dict[str, Any]:
        """加密保存可共享的飞书机器人及可选签名密钥。"""

        if not payload.name.strip() or not validate_feishu_webhook(payload.webhook_url):
            raise HTTPException(status_code=422, detail="飞书 webhook 地址无效")
        target_id = store.add_notification_target(
            payload.name.strip(),
            secrets.encrypt(payload.webhook_url),
            secrets.encrypt(payload.signing_secret) if payload.signing_secret else "",
        )
        row = store.get_notification_target(target_id)
        assert row is not None
        return public_notification_target(row) | {"repository_count": 0}

    @app.patch("/api/notification-targets/{target_id}", dependencies=[admin])
    def update_notification_target(
        target_id: int, payload: NotificationTargetUpdate
    ) -> dict[str, Any]:
        """修改共享通道后，Worker 下一次投递会直接读取新凭据。"""

        if store.get_notification_target(target_id) is None:
            raise HTTPException(status_code=404, detail="飞书配置不存在")
        values: dict[str, str] = {}
        if payload.name is not None:
            values["name"] = payload.name.strip()
        if payload.webhook_url is not None:
            if not validate_feishu_webhook(payload.webhook_url):
                raise HTTPException(status_code=422, detail="飞书 webhook 地址无效")
            values["webhook_ciphertext"] = secrets.encrypt(payload.webhook_url)
        if payload.signing_secret is not None:
            values["signing_secret_ciphertext"] = (
                secrets.encrypt(payload.signing_secret) if payload.signing_secret else ""
            )
        if not values or not values.get("name", "valid").strip():
            raise HTTPException(status_code=422, detail="飞书配置内容无效")
        store.update_notification_target(target_id, values)
        row = next(row for row in store.list_notification_targets() if row["id"] == target_id)
        return public_notification_target(row)

    @app.delete("/api/notification-targets/{target_id}", dependencies=[admin])
    def delete_notification_target(target_id: int) -> dict[str, str]:
        """删除通道并解除所有仓库关联，已有评审任务仍保留。"""

        if not store.delete_notification_target(target_id):
            raise HTTPException(status_code=404, detail="飞书配置不存在")
        return {"status": "deleted"}

    @app.post("/api/repositories", dependencies=[admin], status_code=201)
    def create_repository(payload: RepositoryCreate) -> dict[str, Any]:
        """接入单个 GitLab 项目并加密 webhook 与飞书凭据。"""

        gitlab_url, remote_path = validate_repository_source(
            payload.gitlab_url,
            payload.remote_url,
            payload.path_with_namespace,
            payload.target_branch,
            bool(payload.gitlab_token),
        )
        if payload.feishu_webhook and not validate_feishu_webhook(payload.feishu_webhook):
            raise HTTPException(status_code=422, detail="飞书 webhook 地址无效")
        if (
            payload.feishu_target_id is not None
            and store.get_notification_target(payload.feishu_target_id) is None
        ):
            raise HTTPException(status_code=422, detail="飞书配置不存在")
        if payload.feishu_target_id is not None and payload.feishu_webhook:
            raise HTTPException(status_code=422, detail="飞书配置和独立 Hook 不能同时指定")
        if payload.auth_kind == "signing" and (
            not payload.webhook_token or not payload.webhook_token.startswith("whsec_")
        ):
            raise HTTPException(status_code=422, detail="请填写 GitLab 生成的 Signing token")
        # Secret token 由服务端生成，避免浏览器随机数兼容差异和弱口令。
        webhook_token = payload.webhook_token or token_urlsafe(32)
        values = payload.model_dump(exclude={"webhook_token", "gitlab_token"})
        values["gitlab_url"] = gitlab_url
        values["path_with_namespace"] = remote_path
        values["gitlab_token_ciphertext"] = (
            secrets.encrypt(payload.gitlab_token) if payload.gitlab_token else ""
        )
        values["webhook_secret"] = secrets.encrypt(webhook_token)
        values["feishu_webhook"] = (
            secrets.encrypt(payload.feishu_webhook) if payload.feishu_webhook else ""
        )
        try:
            repository_id = store.add_repository(values)
        except sqlite3.IntegrityError as error:
            raise HTTPException(status_code=409, detail="仓库和目标分支已存在") from error
        row = store.get_repository(repository_id)
        assert row is not None
        return public_repository(row, config.webhook_base_url)

    @app.post("/api/repositories/preflight", dependencies=[admin])
    def preflight_repository(
        payload: RepositoryCreate, repository_id: int | None = None,
    ) -> dict[str, Any]:
        """保存前复用来源约束；不访问外部系统，也不持久化表单中的密钥。"""

        current = store.get_repository(repository_id) if repository_id else None
        if repository_id and current is None:
            raise HTTPException(status_code=404, detail="项目不存在")
        gitlab_url, path = validate_repository_source(
            payload.gitlab_url, payload.remote_url, payload.path_with_namespace,
            payload.target_branch,
            bool(payload.gitlab_token or current and current["gitlab_token_ciphertext"]),
        )
        if payload.feishu_target_id and not store.get_notification_target(payload.feishu_target_id):
            raise HTTPException(status_code=422, detail="飞书配置不存在")
        if payload.auth_kind == "signing" and (
            not payload.webhook_token and not current
            or payload.webhook_token and not payload.webhook_token.startswith("whsec_")
        ):
            raise HTTPException(status_code=422, detail="Signing token 格式无效")
        with store.connection() as db:
            duplicate = db.execute(
                """SELECT id FROM repositories WHERE gitlab_url=? AND project_id=?
                AND target_branch=? AND id!=?""",
                (gitlab_url, payload.project_id, payload.target_branch, repository_id or -1),
            ).fetchone()
        if duplicate:
            raise HTTPException(status_code=409, detail="仓库和目标分支已存在")
        return {"status": "passed", "repository_path": path,
                "next": "保存后执行 Git 与 GitLab API 连接测试"}

    @app.patch("/api/repositories/{repository_id}", dependencies=[admin])
    def update_repository(repository_id: int, payload: RepositoryUpdate) -> dict[str, Any]:
        """校验修改后的仓库来源，并在保留业务历史的前提下更新接入设置。"""

        current = store.get_repository(repository_id)
        if current is None:
            raise HTTPException(status_code=404, detail="仓库不存在")
        values = payload.model_dump(exclude_unset=True, exclude_none=True)
        gitlab_token = values.pop("gitlab_token", None)
        if gitlab_token:
            values["gitlab_token_ciphertext"] = secrets.encrypt(gitlab_token)
        source_fields = {"gitlab_url", "remote_url", "path_with_namespace", "target_branch"}
        if source_fields & payload.model_fields_set:
            gitlab_url, remote_path = validate_repository_source(
                values.get("gitlab_url", current["gitlab_url"]),
                values.get("remote_url", current["remote_url"]),
                values.get("path_with_namespace", current["path_with_namespace"]),
                values.get("target_branch", current["target_branch"]),
                bool(gitlab_token or current["gitlab_token_ciphertext"]),
            )
            if "gitlab_url" in values:
                values["gitlab_url"] = gitlab_url
            values["path_with_namespace"] = remote_path
        if "feishu_target_id" in payload.model_fields_set:
            values["feishu_target_id"] = payload.feishu_target_id
            values["feishu_webhook"] = ""
            if (
                payload.feishu_target_id is not None
                and store.get_notification_target(payload.feishu_target_id) is None
            ):
                raise HTTPException(status_code=422, detail="飞书配置不存在")
        if "webhook_id" in payload.model_fields_set:
            values["webhook_id"] = payload.webhook_id
        if not values:
            raise HTTPException(status_code=422, detail="没有可更新的仓库设置")
        auth_kind = values.get("auth_kind", current["auth_kind"])
        token = values.pop("webhook_token", None)
        if auth_kind != current["auth_kind"] and not token:
            if auth_kind == "signing":
                raise HTTPException(status_code=422, detail="切换 Signing token 时必须填写新令牌")
            # 从 Signing 切回 Secret 时由服务端生成，避免要求管理员自造密钥。
            token = token_urlsafe(32)
        if token:
            if auth_kind == "signing" and not token.startswith("whsec_"):
                raise HTTPException(status_code=422, detail="Signing token 格式无效")
            values["webhook_secret"] = secrets.encrypt(token)
        feishu_webhook = values.pop("feishu_webhook", None)
        if feishu_webhook:
            if not validate_feishu_webhook(feishu_webhook):
                raise HTTPException(status_code=422, detail="飞书 webhook 地址无效")
            values["feishu_webhook"] = secrets.encrypt(feishu_webhook)
            values["feishu_target_id"] = None
        elif "feishu_target_id" in payload.model_fields_set:
            values["feishu_webhook"] = ""
        try:
            store.update_repository(repository_id, values)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except sqlite3.IntegrityError as error:
            raise HTTPException(status_code=409, detail="仓库和目标分支已存在") from error
        updated = store.get_repository(repository_id)
        assert updated is not None
        return public_repository(updated, config.webhook_base_url)

    @app.delete("/api/repositories/{repository_id}/feishu-hook", dependencies=[admin])
    def delete_feishu_hook(repository_id: int) -> dict[str, Any]:
        """删除单个项目的飞书 Hook，项目配置和评审历史保持不变。"""

        if store.get_repository(repository_id) is None:
            raise HTTPException(status_code=404, detail="仓库不存在")
        store.clear_feishu_webhook(repository_id)
        row = store.get_repository(repository_id)
        assert row is not None
        return public_repository(row, config.webhook_base_url)

    @app.delete("/api/repositories/{repository_id}", dependencies=[admin])
    def delete_repository(repository_id: int) -> dict[str, str]:
        """删除项目配置及其业务记录；操作由前端确认后发起。"""

        if store.get_repository(repository_id) is None:
            raise HTTPException(status_code=404, detail="仓库不存在")
        deleted = store.delete_repository(repository_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="仓库不存在")
        return {"status": "deleted"}

    @app.post("/api/repositories/{repository_id}/mrs/{mr_iid}/enqueue", dependencies=[admin])
    def enqueue_mr(repository_id: int, mr_iid: int) -> dict[str, str]:
        """管理员补触发一个 MR，合并事实仍由 Worker 向 GitLab 确认。"""

        repository = store.get_repository(repository_id)
        if repository is None or mr_iid < 1:
            raise HTTPException(status_code=404, detail="仓库或 MR 不存在")
        if not repository["enabled"]:
            raise HTTPException(status_code=409, detail="仓库已暂停接收")
        if not store.enqueue_mr(repository_id, mr_iid):
            raise HTTPException(status_code=409, detail="该 MR 已入队或已完成展开")
        return {"status": "queued"}

    @app.get("/api/model-profiles", dependencies=[admin])
    def list_model_profiles() -> list[dict[str, Any]]:
        return [public_model_profile(row) for row in store.list_model_profiles()]

    @app.post("/api/model-profiles", dependencies=[admin], status_code=201)
    def create_model_profile(payload: ModelProfileCreate) -> dict[str, Any]:
        """新增配置先保持未启用，避免保存草稿立即改变评审任务。"""

        if not payload.name.strip():
            raise HTTPException(status_code=422, detail="配置名称不能为空")
        validate_model_prices(payload.input_price_per_million, payload.output_price_per_million)
        profile_id = store.add_model_profile(
            payload.name.strip(),
            payload.provider,
            payload.model,
            validate_model_endpoint(payload.base_url),
            secrets.encrypt(payload.api_key),
            payload.price_currency,
            str(payload.input_price_per_million) if payload.input_price_per_million is not None
            else None,
            str(payload.output_price_per_million) if payload.output_price_per_million is not None
            else None,
        )
        row = next(row for row in store.list_model_profiles() if row["id"] == profile_id)
        return public_model_profile(row)

    @app.patch("/api/model-profiles/{profile_id}", dependencies=[admin])
    def update_model_profile(profile_id: int, payload: ModelProfileUpdate) -> dict[str, Any]:
        """更新已保存模型；启用配置在队列运行期间保持不可变。"""

        values = payload.model_dump(exclude_unset=True, exclude_none=True)
        # 单价显式传 null 表示清空；其他可选字段仍沿用省略即保留的现有语义。
        for field in ("input_price_per_million", "output_price_per_million"):
            if field in payload.model_fields_set and getattr(payload, field) is None:
                values[field] = None
        if not values:
            raise HTTPException(status_code=422, detail="没有可更新的模型设置")
        current = next((row for row in store.list_model_profiles() if row["id"] == profile_id),
                       None)
        if current is None:
            raise HTTPException(status_code=404, detail="模型配置不存在")
        validate_model_prices(
            values.get("input_price_per_million", current["input_price_per_million"]),
            values.get("output_price_per_million", current["output_price_per_million"]),
        )
        for field in ("input_price_per_million", "output_price_per_million"):
            if values.get(field) is not None:
                values[field] = str(values[field])
        if "name" in values:
            values["name"] = values["name"].strip()
            if not values["name"]:
                raise HTTPException(status_code=422, detail="配置名称不能为空")
        if "base_url" in values:
            values["base_url"] = validate_model_endpoint(values["base_url"])
        key = values.pop("api_key", None)
        if key:
            values["api_key_ciphertext"] = secrets.encrypt(key)
        try:
            updated = store.update_model_profile(profile_id, values)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        if not updated:
            raise HTTPException(status_code=404, detail="模型配置不存在")
        row = next(row for row in store.list_model_profiles() if row["id"] == profile_id)
        return public_model_profile(row)

    @app.post("/api/model-profiles/{profile_id}/activate", dependencies=[admin])
    def activate_model_profile(profile_id: int) -> dict[str, Any]:
        try:
            activated = store.activate_model_profile(profile_id)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        if not activated:
            raise HTTPException(status_code=404, detail="模型配置不存在")
        row = next(row for row in store.list_model_profiles() if row["id"] == profile_id)
        return public_model_profile(row)

    @app.delete("/api/model-profiles/{profile_id}", dependencies=[admin])
    def delete_model_profile(profile_id: int) -> dict[str, str]:
        try:
            deleted = store.delete_model_profile(profile_id)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        if not deleted:
            raise HTTPException(status_code=404, detail="模型配置不存在")
        return {"status": "deleted"}

    @app.get("/api/connection-checks", dependencies=[admin])
    def list_connection_checks() -> list[dict[str, Any]]:
        """显示最近的连接测试结果，外部响应和密钥不进入管理 API。"""

        return store.list_connection_checks()

    @app.post("/api/connection-checks", dependencies=[admin], status_code=202)
    def enqueue_connection_check(payload: ConnectionCheckInput) -> dict[str, int | str]:
        """快速持久化连接测试，耗时的 Git、网络和 OCR 调用由 Worker 完成。"""

        if payload.kind == "model":
            if payload.repository_id is not None:
                raise HTTPException(status_code=422, detail="模型测试不需要仓库 ID")
            profile = store.get_model_profile()
            if profile is None:
                raise HTTPException(status_code=409, detail="请先配置模型与 API key")
        elif payload.repository_id is None or store.get_repository(payload.repository_id) is None:
            raise HTTPException(status_code=404, detail="仓库不存在")
        check_id = store.enqueue_connection_check(payload.kind, payload.repository_id)
        if check_id is None:
            raise HTTPException(status_code=409, detail="同一目标的连接测试正在执行")
        return {"id": check_id, "status": "queued"}

    @app.get("/api/webhook-diagnostics", dependencies=[admin])
    def list_webhook_diagnostics() -> list[dict[str, Any]]:
        """展示最近投递的脱敏状态；未鉴权载荷字段仅作为自称值。"""

        return store.list_webhook_diagnostics()

    @app.get("/api/events", dependencies=[admin])
    def list_events() -> list[dict[str, Any]]:
        """展示最近合并事件与队列处理状态。"""

        return store.list_events()

    @app.post("/api/events/{event_id}/retry", dependencies=[admin])
    def retry_event(event_id: int) -> dict[str, str]:
        """把需要人工处理的事件重新放入 GitLab 确认队列。"""

        if not store.retry_event(event_id):
            raise HTTPException(status_code=409, detail="事件当前无法重试")
        return {"status": "queued"}

    @app.get("/api/jobs", dependencies=[admin])
    def list_jobs() -> list[dict[str, Any]]:
        """展示近期评审任务。"""

        return store.list_jobs()

    @app.get("/api/jobs/{job_id}", dependencies=[admin])
    def get_job(job_id: int) -> dict[str, Any]:
        """获取评审详情及原始机器可读结果。"""

        job = store.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="任务不存在")
        repository = store.get_repository(job["repository_id"])
        if repository:
            project_url = project_web_url(repository["gitlab_url"], repository["remote_url"])
            if job["mr_iid"] > 0:
                job["mr_url"] = f"{project_url}/-/merge_requests/{job['mr_iid']}"
            job["commit_url"] = f"{project_url}/-/commit/{job['commit_sha']}"
        snapshot = json.loads(job["config_snapshot"]) if job.get("config_snapshot") else None
        if job.get("result"):
            job["result"]["estimated_cost"] = estimate_cost(
                job["result"].get("usage"), snapshot,
            )
        # 逐次结果通过受保护的报告接口读取，详情列表不重复传输安全 JSON 或内部路径。
        for attempt in job["attempt_history"]:
            attempt.pop("result_json", None)
            attempt.pop("result_path", None)
            attempt.pop("config_snapshot", None)
        job.pop("config_snapshot", None)
        return job

    @app.put("/api/jobs/{job_id}/feedback/{comment_index}", dependencies=[admin])
    def put_review_feedback(
        job_id: int, comment_index: int, payload: ReviewFeedbackInput
    ) -> dict[str, str]:
        """仅接受已完成任务中实际存在的 OCR 评论序号。"""

        try:
            store.set_review_feedback(job_id, comment_index, payload.verdict)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {"verdict": payload.verdict}

    @app.delete("/api/jobs/{job_id}/feedback/{comment_index}", dependencies=[admin])
    def delete_review_feedback(job_id: int, comment_index: int) -> dict[str, str]:
        """撤销已有反馈；缺失记录明确返回 404。"""

        if not store.clear_review_feedback(job_id, comment_index):
            raise HTTPException(status_code=404, detail="反馈不存在")
        return {"status": "deleted"}

    @app.post("/api/jobs/{job_id}/retry", dependencies=[admin])
    def retry_job(job_id: int) -> dict[str, str | int]:
        """将已完成或失败的任务重新排队，保留历史工件。"""

        job = store.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="任务不存在")
        try:
            snapshot = config_hash(store, config, job["rule_digest"], job["repository_id"])
        except (ValueError, InvalidToken) as error:
            raise HTTPException(409, "评审配置不可用，请先启用并检查 Agent 模型") from error
        queued_id = store.retry_job(job_id, snapshot)
        if queued_id is None:
            raise HTTPException(status_code=409, detail="任务当前无法重跑")
        return {"status": "queued", "job_id": queued_id}

    @app.post("/api/jobs/{job_id}/notification/retry", dependencies=[admin])
    def retry_notification(job_id: int) -> dict[str, str]:
        """只重发终态评审结果，不再次调用模型。"""

        if not store.retry_delivery(job_id):
            raise HTTPException(status_code=409, detail="通知当前无法重发")
        return {"status": "pending"}

    async def read_webhook_body(request: Request) -> bytes:
        """统一限制入站大小，公开入口仅用请求体定位候选仓库。"""

        # 在聚合原始签名字节时限定内存占用，不能等完整请求体读入后才判定上限。
        chunks: list[bytes] = []
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > 1024 * 1024:
                store.record_webhook_diagnostic(
                    None, None, None, "other", "rejected", "body_too_large", 413
                )
                raise HTTPException(status_code=413, detail="GitLab 事件过大")
            chunks.append(chunk)
        return b"".join(chunks)

    def process_gitlab_webhook(
        row: dict[str, Any], headers: dict[str, str], body: bytes
    ) -> dict[str, str]:
        """候选项目必须通过自身的密钥验证，未鉴权载荷不能产生事件。"""

        try:
            token = secrets.decrypt(row["webhook_secret"])
        except InvalidToken as error:
            raise HTTPException(status_code=503, detail="Webhook 密钥不可用") from error
        verify_webhook(headers, body, row["auth_kind"], token)
        store.record_webhook(row["id"])
        if headers.get("x-gitlab-event") == "Push Hook":
            if not row["enable_default_branch_pushes"]:
                return {"status": "ignored"}
            try:
                push = json.loads(body)
            except (ValueError, UnicodeDecodeError):
                return {"status": "ignored"}
            if not isinstance(push, dict) or push.get("object_kind") != "push":
                return {"status": "ignored"}
            project = push.get("project")
            before, after = push.get("before"), push.get("after")
            if (
                not isinstance(project, dict)
                or project.get("id") != row["project_id"]
                or push.get("ref") != f"refs/heads/{row['target_branch']}"
                or not isinstance(before, str)
                or not isinstance(after, str)
                or not re.fullmatch(r"[0-9a-fA-F]{40}", before)
                or not re.fullmatch(r"[0-9a-fA-F]{40}", after)
                or before == "0" * 40
                or after == "0" * 40
            ):
                return {"status": "ignored"}
            delivery_id = headers.get("webhook-id") or headers.get("idempotency-key")
            created = store.add_push_event(row["id"], before, after, delivery_id)
            return {"status": "queued" if created else "duplicate"}
        if headers.get("x-gitlab-event") != "Merge Request Hook":
            return {"status": "ignored"}
        with store.connection() as db:
            premerge_setting = db.execute(
                "SELECT enabled FROM premerge_settings WHERE repository_id=?", (row["id"],)
            ).fetchone()
        if premerge_setting and premerge_setting["enabled"]:
            version = parse_premerge_event(body, row["project_id"], row["target_branch"])
            if version:
                iid, head, context_hint = version
                if head is None:
                    invalidate_premerge(store, row["id"], iid)
                else:
                    with store.connection() as db:
                        setting = db.execute("""SELECT include_description
                            FROM premerge_settings WHERE repository_id=?""",
                            (row["id"],)).fetchone()
                    if setting is None or not setting["include_description"]:
                        context_hint = None
                    created = enqueue_premerge(store, row["id"], iid, head, context_hint)
                    return {"status": "queued" if created else "duplicate"}
        if not row["enable_merge_requests"]:
            return {"status": "ignored"}
        event = parse_merge_event(body, row["project_id"], row["target_branch"])
        if event is None:
            return {"status": "ignored"}
        delivery_id = headers.get("webhook-id") or headers.get("idempotency-key")
        created = store.add_event(
            row["id"], event["mr_iid"], delivery_id, event["merge_sha"], event["squash_sha"]
        )
        with store.connection() as db:
            # 合并后的旧预审结论不能继续作为当前未合并 MR 结果展示。
            db.execute("""UPDATE premerge_reviews SET status='superseded',
                finished_at=CURRENT_TIMESTAMP WHERE repository_id=? AND mr_iid=?
                AND status!='superseded'""", (row["id"], event["mr_iid"]))
        return {"status": "queued" if created else "duplicate"}

    def record_webhook_result(
        repository_id: int | None, payload: dict[str, Any] | None,
        headers: dict[str, str], outcome: str, reason: str, http_status: int,
    ) -> None:
        """只提取受限的自称项目与分支；未鉴权字段绝不能成为可信业务事实。"""

        project = payload.get("project") if payload else None
        project_id = project.get("id") if isinstance(project, dict) else None
        if (
            not isinstance(project_id, int) or isinstance(project_id, bool)
            or not 0 < project_id <= 9223372036854775807
        ):
            project_id = None
        attributes = payload.get("object_attributes") if payload else None
        if payload and payload.get("object_kind") == "push":
            branch = payload.get("ref")
            if isinstance(branch, str):
                branch = branch.removeprefix("refs/heads/")
        else:
            branch = attributes.get("target_branch") if isinstance(attributes, dict) else None
        if not isinstance(branch, str) or not re.fullmatch(r"[a-zA-Z0-9._/-]{1,200}", branch):
            branch = None
        event_header = headers.get("x-gitlab-event")
        event_kind = {
            "Merge Request Hook": "merge_request",
            "Push Hook": "push",
        }.get(event_header or "", "other")
        store.record_webhook_diagnostic(
            repository_id, project_id, branch, event_kind, outcome, reason, http_status
        )

    def handle_webhook_candidate(
        row: dict[str, Any], headers: dict[str, str], body: bytes,
        payload: dict[str, Any] | None, ignored_http_status: int = 200,
    ) -> dict[str, str]:
        """鉴权与业务入队后记录结论，失败也只记录固定错误类别。"""

        try:
            result = process_gitlab_webhook(row, headers, body)
        except HTTPException as error:
            reason = {
                401: "authentication_failed",
                403: "project_mismatch",
                422: "invalid_payload",
                503: "secret_unavailable",
            }.get(error.status_code, "rejected")
            record_webhook_result(
                row["id"], payload, headers, "rejected", reason, error.status_code
            )
            raise
        outcome = result["status"]
        if outcome == "ignored":
            kind = headers.get("x-gitlab-event")
            attributes = payload.get("object_attributes") if payload else None
            reason = (
                "push_disabled" if kind == "Push Hook" and not row["enable_default_branch_pushes"]
                else "merge_disabled" if kind == "Merge Request Hook" and
                not row["enable_merge_requests"] else
                "merge_not_completed" if kind == "Merge Request Hook" and
                isinstance(attributes, dict) and attributes.get("action") != "merge" else
                "target_branch_mismatch" if kind == "Merge Request Hook" and
                isinstance(attributes, dict) and
                attributes.get("target_branch") != row["target_branch"] else
                "invalid_push_range" if kind == "Push Hook" else "event_ignored"
            )
        else:
            reason = outcome
        record_webhook_result(
            row["id"], payload, headers, outcome, reason,
            ignored_http_status if outcome == "ignored" else 200,
        )
        return result

    @app.post("/api/webhooks/gitlab/{repository_id}")
    async def receive_gitlab(repository_id: int, request: Request) -> dict[str, str]:
        """保留旧项目的专属回调地址，新配置统一使用无 ID 地址。"""

        row = store.get_repository(repository_id)
        if row is None or not row["enabled"]:
            store.record_webhook_diagnostic(
                None, None, None, "other", "rejected", "repository_unavailable", 404
            )
            raise HTTPException(status_code=404, detail="仓库未接入")
        body = await read_webhook_body(request)
        try:
            parsed = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            parsed = None
        return handle_webhook_candidate(
            row, {key.lower(): value for key, value in request.headers.items()},
            body, parsed if isinstance(parsed, dict) else None,
        )

    @app.post("/api/webhooks/gitlab", response_model=None)
    async def receive_gitlab_shared(request: Request) -> dict[str, str] | Response:
        """按 GitLab 项目和目标分支定位配置；匹配后仍必须验证该项目令牌。"""

        body = await read_webhook_body(request)
        headers = {key.lower(): value for key, value in request.headers.items()}
        try:
            payload = json.loads(body)
        except (ValueError, UnicodeDecodeError) as error:
            record_webhook_result(None, None, headers, "rejected", "invalid_json", 400)
            raise HTTPException(status_code=400, detail="GitLab 事件格式无效") from error
        if not isinstance(payload, dict):
            record_webhook_result(None, None, headers, "rejected", "invalid_json", 400)
            raise HTTPException(status_code=400, detail="GitLab 事件格式无效")
        project = payload.get("project")
        attributes = payload.get("object_attributes")
        project_id = project.get("id") if isinstance(project, dict) else None
        if not isinstance(project_id, int) or isinstance(project_id, bool):
            project_id = None
        if payload.get("object_kind") == "push" and isinstance(payload.get("ref"), str):
            branch = payload["ref"].removeprefix("refs/heads/")
        else:
            branch = attributes.get("target_branch") if isinstance(attributes, dict) else None
        matches = [
            row
            for row in store.list_repositories()
            if row["enabled"] and row["project_id"] == project_id and row["target_branch"] == branch
        ]
        if len(matches) != 1:
            record_webhook_result(
                None, payload, headers, "ignored", "unmatched_project_or_branch", 204
            )
            return Response(status_code=204)
        result = handle_webhook_candidate(matches[0], headers, body, payload, 204)
        return Response(status_code=204) if result["status"] == "ignored" else result

    frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if frontend_dist.is_dir():
        # API 路由先注册，根挂载只处理管理页与静态资源。
        app.mount("/", FrontendFiles(directory=frontend_dist, html=True), name="frontend")
    return app
