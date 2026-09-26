"""暴露管理 API 与轻量 GitLab webhook 接收端。"""

from __future__ import annotations

import hmac
import logging
import re
import sqlite3
from pathlib import Path
from secrets import token_urlsafe
from typing import Annotated, Any, Literal
from urllib.parse import urlparse

from cryptography.fernet import InvalidToken
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.routing import APIRoute
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles

from ocr_manager.config import Settings, load_settings
from ocr_manager.gitlab import project_web_url
from ocr_manager.secrets import SecretBox
from ocr_manager.storage import Store
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
    auth_kind: Literal["signing", "secret"]
    webhook_token: str | None = Field(default=None, min_length=16)
    feishu_webhook: str | None = None
    feishu_target_id: int | None = Field(default=None, gt=0)

    model_config = {"extra": "forbid"}


class RepositoryUpdate(BaseModel):
    """仓库接入后的可变设置；项目身份和 remote 不允许事后改写。"""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    auth_kind: Literal["signing", "secret"] | None = None
    webhook_token: str | None = Field(default=None, min_length=16)
    feishu_webhook: str | None = None
    feishu_target_id: int | None = Field(default=None, gt=0)
    webhook_id: str | None = Field(default=None, max_length=100)

    model_config = {"extra": "forbid"}


class ModelProfileInput(BaseModel):
    """全局 OCR 模型设置；空 API key 表示沿用已保存密钥。"""

    provider: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    model: str = Field(min_length=1, max_length=160)
    api_key: str | None = Field(default=None, min_length=1)

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
    """只接受与 GitLab 主机一致、无内嵌口令的 SSH Git 地址。"""

    host = urlparse(gitlab_url).hostname
    scp = re.fullmatch(r"git@([a-zA-Z0-9.-]+):([^\s]+)", remote_url)
    if scp:
        return scp.group(1).lower() == host and not scp.group(2).startswith("-")
    remote = urlparse(remote_url)
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
        key: value for key, value in row.items() if key not in {"webhook_secret", "feishu_webhook"}
    } | {
        "webhook_url": f"{public_url}/api/webhooks/gitlab/{row['id']}",
        "has_feishu_webhook": bool(row.get("feishu_target_id") or row.get("feishu_webhook")),
    }


def public_notification_target(row: dict[str, Any]) -> dict[str, Any]:
    """管理列表只返回通道元数据，密文和明文均不进入浏览器缓存。"""

    return {
        key: value
        for key, value in row.items()
        if key not in {"webhook_ciphertext", "signing_secret_ciphertext"}
    } | {"has_signing_secret": bool(row["signing_secret_ciphertext"])}


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
                    "notification-targets": "notification_target",
                    "model-profile": "model_profile",
                    "connection-checks": "connection_check",
                    "events": "merge_event",
                    "jobs": "review_job",
                }.get(resource, "management")
                params = request.path_params
                object_id = next(
                    (
                        params[name]
                        for name in ("repository_id", "target_id", "event_id", "job_id")
                        if name in params
                    ),
                    None,
                )
                outcome = (
                    "success" if response.status_code < 400 else f"http_{response.status_code}"
                )
                try:
                    store.record_audit(
                        f"{request.method} {route.path}", object_type, object_id, outcome
                    )
                except sqlite3.Error:
                    # 审计写入异常不能让已提交的配置操作向客户端伪装成失败。
                    LOGGER.exception("管理操作审计记录失败")
        return response

    def require_admin(x_admin_token: Annotated[str | None, Header()] = None) -> None:
        """开发模式跳过管理台口令；其他模式仍使用服务端口令，Webhook 不共享权限。"""

        if config.dev_mode:
            return
        if not x_admin_token or not hmac.compare_digest(x_admin_token, config.admin_token):
            raise HTTPException(status_code=401, detail="管理口令无效")

    admin = Depends(require_admin)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        """检查 API、SQLite、鉴权模式与独立 Worker；API 存活不代表队列正在消费。"""

        with store.connection() as db:
            db.execute("SELECT 1")
        return {
            "status": "ok",
            "auth_mode": "dev" if config.dev_mode else "admin",
            "worker": "running" if worker_is_running(config.data_dir) else "stopped",
        }

    @app.get("/api/repositories", dependencies=[admin])
    def list_repositories() -> list[dict[str, Any]]:
        """列出已接入仓库；密钥仅由单项查看接口按需返回。"""

        return [public_repository(row, config.public_url) for row in store.list_repositories()]

    @app.get("/api/repositories/{repository_id}/webhook-token", dependencies=[admin])
    def get_webhook_token(repository_id: int, response: Response) -> dict[str, str]:
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
            )
        except sqlite3.Error:
            LOGGER.exception("Webhook 令牌查看审计记录失败")
        return {"webhook_token": token}

    @app.get("/api/audit-logs", dependencies=[admin])
    def list_audit_logs() -> list[dict[str, Any]]:
        """展示近期管理写操作及 HTTP 结果，不返回请求内容。"""

        return store.list_audit()

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

        gitlab = urlparse(payload.gitlab_url)
        if (
            gitlab.scheme != "https"
            or not gitlab.hostname
            or gitlab.username
            or gitlab.password
            or gitlab.query
            or gitlab.fragment
        ):
            raise HTTPException(status_code=422, detail="GitLab 地址必须是 HTTPS 主机")
        if not validate_remote(payload.gitlab_url, payload.remote_url):
            raise HTTPException(
                status_code=422, detail="Git 地址必须是同一 GitLab 主机的只读 SSH 地址"
            )
        branch = payload.target_branch
        if (
            not re.fullmatch(r"[a-zA-Z0-9._/-]+", branch)
            or branch.startswith(("-", "/", "."))
            or branch.endswith(("/", "."))
            or ".." in branch
            or "//" in branch
        ):
            raise HTTPException(status_code=422, detail="目标分支名称无效")
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
        values = payload.model_dump(exclude={"webhook_token"})
        values["gitlab_url"] = payload.gitlab_url.rstrip("/")
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
        return public_repository(row, config.public_url)

    @app.patch("/api/repositories/{repository_id}", dependencies=[admin])
    def update_repository(repository_id: int, payload: RepositoryUpdate) -> dict[str, Any]:
        """暂停接收、维护 webhook 元数据或单向轮换项目凭据。"""

        current = store.get_repository(repository_id)
        if current is None:
            raise HTTPException(status_code=404, detail="仓库不存在")
        values = payload.model_dump(exclude_unset=True, exclude_none=True)
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
            raise HTTPException(status_code=422, detail="切换鉴权方式时必须同时更新令牌")
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
        store.update_repository(repository_id, values)
        updated = store.get_repository(repository_id)
        assert updated is not None
        return public_repository(updated, config.public_url)

    @app.delete("/api/repositories/{repository_id}/feishu-hook", dependencies=[admin])
    def delete_feishu_hook(repository_id: int) -> dict[str, Any]:
        """删除单个项目的飞书 Hook，项目配置和评审历史保持不变。"""

        if store.get_repository(repository_id) is None:
            raise HTTPException(status_code=404, detail="仓库不存在")
        store.clear_feishu_webhook(repository_id)
        row = store.get_repository(repository_id)
        assert row is not None
        return public_repository(row, config.public_url)

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

    @app.get("/api/model-profile", dependencies=[admin])
    def get_model_profile() -> dict[str, Any]:
        """仅返回模型标识和是否已设置密钥，绝不回显密文。"""

        profile = store.get_model_profile()
        if profile is None:
            return {
                "provider": config.ocr_provider,
                "model": config.ocr_model,
                "has_api_key": bool(config.ocr_api_key),
                "version": 0,
            }
        return {
            "provider": profile["provider"],
            "model": profile["model"],
            "has_api_key": True,
            "version": profile["version"],
        }

    @app.put("/api/model-profile", dependencies=[admin])
    def save_model_profile(payload: ModelProfileInput) -> dict[str, Any]:
        """加密保存模型密钥；任务排队或运行时锁定全局配置版本。"""

        ciphertext = secrets.encrypt(payload.api_key) if payload.api_key else None
        try:
            store.save_model_profile(payload.provider, payload.model, ciphertext)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return get_model_profile()

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
            profile = get_model_profile()
            if not profile["has_api_key"] or not profile["model"]:
                raise HTTPException(status_code=409, detail="请先配置模型与 API key")
        elif payload.repository_id is None or store.get_repository(payload.repository_id) is None:
            raise HTTPException(status_code=404, detail="仓库不存在")
        check_id = store.enqueue_connection_check(payload.kind, payload.repository_id)
        if check_id is None:
            raise HTTPException(status_code=409, detail="同一目标的连接测试正在执行")
        return {"id": check_id, "status": "queued"}

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
        """展示近期逐提交评审任务。"""

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
            job["mr_url"] = f"{project_url}/-/merge_requests/{job['mr_iid']}"
            job["commit_url"] = f"{project_url}/-/commit/{job['commit_sha']}"
        return job

    @app.post("/api/jobs/{job_id}/retry", dependencies=[admin])
    def retry_job(job_id: int) -> dict[str, str | int]:
        """将已完成或失败的任务重新排队，保留历史工件。"""

        rule_digest = store.get_job_rule_digest(job_id)
        if rule_digest is None:
            raise HTTPException(status_code=404, detail="任务不存在")
        queued_id = store.retry_job(job_id, config_hash(store, config, rule_digest))
        if queued_id is None:
            raise HTTPException(status_code=409, detail="任务当前无法重跑")
        return {"status": "queued", "job_id": queued_id}

    @app.post("/api/jobs/{job_id}/notification/retry", dependencies=[admin])
    def retry_notification(job_id: int) -> dict[str, str]:
        """只重发终态评审结果，不再次调用模型。"""

        if not store.retry_delivery(job_id):
            raise HTTPException(status_code=409, detail="通知当前无法重发")
        return {"status": "pending"}

    @app.post("/api/webhooks/gitlab/{repository_id}")
    async def receive_gitlab(repository_id: int, request: Request) -> dict[str, str]:
        """先鉴权再持久化合并事件，避免 GitLab 等待耗时评审。"""

        row = store.get_repository(repository_id)
        if row is None or not row["enabled"]:
            raise HTTPException(status_code=404, detail="仓库未接入")
        # 在聚合原始签名字节时限定内存占用，不能等完整请求体读入后才判定上限。
        chunks: list[bytes] = []
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > 1024 * 1024:
                raise HTTPException(status_code=413, detail="GitLab 事件过大")
            chunks.append(chunk)
        body = b"".join(chunks)
        try:
            token = secrets.decrypt(row["webhook_secret"])
        except InvalidToken as error:
            raise HTTPException(status_code=503, detail="Webhook 密钥不可用") from error
        headers = {key.lower(): value for key, value in request.headers.items()}
        verify_webhook(headers, body, row["auth_kind"], token)
        store.record_webhook(repository_id)
        if headers.get("x-gitlab-event") != "Merge Request Hook":
            return {"status": "ignored"}
        event = parse_merge_event(body, row["project_id"], row["target_branch"])
        if event is None:
            return {"status": "ignored"}
        delivery_id = headers.get("webhook-id") or headers.get("idempotency-key")
        created = store.add_event(
            repository_id, event["mr_iid"], delivery_id, event["merge_sha"], event["squash_sha"]
        )
        return {"status": "queued" if created else "duplicate"}

    frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if frontend_dist.is_dir():
        # API 路由先注册，根挂载只处理管理页与静态资源。
        app.mount("/", FrontendFiles(directory=frontend_dist, html=True), name="frontend")
    return app
