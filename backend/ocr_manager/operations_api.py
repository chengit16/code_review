"""装配运维管理接口；继承管理鉴权，不执行评审或外部网络操作。"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any, Literal

from cryptography.fernet import InvalidToken
from fastapi import FastAPI, HTTPException, Query
from starlette.responses import Response

from ocr_manager.config import Settings
from ocr_manager.config_history import list_config_history, restore_config
from ocr_manager.secrets import SecretBox
from ocr_manager.storage import Store
from ocr_manager.tasks import report_projection, search_jobs


def register_operations(app: FastAPI, store: Store, settings: Settings, admin: Any) -> None:
    """注册独立运维资源，所有接口由既有服务端管理权限保护。"""

    @app.get("/api/repository-readiness", dependencies=[admin])
    def repository_readiness() -> list[dict[str, Any]]:
        """按保存版本与测试时间计算接入状态，旧测试不会冒充新配置已验证。"""

        checks = store.list_connection_checks()
        with store.connection() as db:
            versions = {row["object_id"]: row["id"] for row in db.execute(
                """SELECT object_id, MAX(id) AS id
                FROM config_revisions WHERE object_type='repository' GROUP BY object_id"""
            )}
        result = []
        for repository in store.list_repositories():
            relevant = [check for check in checks if check["repository_id"] == repository["id"]]
            git = next((check for check in relevant if check["kind"] == "git"), None)
            gitlab = next((check for check in relevant if check["kind"] == "gitlab"), None)
            version_id = versions.get(repository["id"])
            tested = all(check and check["status"] == "passed"
                         and check["config_revision_id"] == version_id for check in (git, gitlab))
            result.append({"repository_id": repository["id"],
                           "config_revision_id": version_id,
                           "git": git["status"] if git else "untested",
                           "gitlab": gitlab["status"] if gitlab else "untested",
                           "status": "paused" if not repository["enabled"] else
                           "ready" if tested else "needs_check",
                           "last_webhook_at": repository["last_webhook_at"]})
        return result

    @app.get("/api/config-history/{kind}", dependencies=[admin])
    def config_history(
        kind: Literal["repository", "notification_target", "model_profile"],
        object_id: int | None = Query(None, gt=0),
    ) -> list[dict[str, Any]]:
        """查看对象配置差异；共享口令只能标识共享管理会话。"""

        return list_config_history(store, kind, object_id)

    @app.post("/api/config-history/{kind}/{object_id}/{revision_id}/restore", dependencies=[admin])
    def restore_configuration(
        kind: Literal["repository", "notification_target", "model_profile"],
        object_id: int, revision_id: int,
    ) -> dict[str, str]:
        """恢复历史内容；密文失效或当前队列不允许恢复时返回冲突。"""

        try:
            if not restore_config(
                store, SecretBox(settings.master_key), kind, object_id, revision_id,
            ):
                raise HTTPException(404, "配置对象已删除")
        except InvalidToken as error:
            raise HTTPException(409, "历史凭据无法解密") from error
        except (ValueError, sqlite3.IntegrityError) as error:
            raise HTTPException(
                409, "版本恢复被拒绝，请核对关联配置、项目身份及待处理队列",
            ) from error
        return {"status": "restored"}

    @app.get("/api/task-search", dependencies=[admin])
    def task_search(
        page: int = Query(1, ge=1, le=1000000),
        page_size: int = Query(25, ge=1, le=100),
        repository_id: int | None = Query(None, gt=0),
        status: Literal["queued", "running", "complete", "partial", "failed", "skipped"]
        | None = None,
        target_branch: str | None = Query(None, max_length=200),
        mr_iid: int | None = Query(None, gt=0),
        sha: str | None = Query(None, pattern=r"^[0-9a-fA-F]{4,40}$"),
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> dict[str, Any]:
        """时间按 UTC 比较；无时区输入默认 UTC，非法范围明确拒绝。"""

        def utc(value: datetime | None) -> str | None:
            if value is None:
                return None
            return value.replace(tzinfo=value.tzinfo or UTC).astimezone(
                UTC
            ).strftime("%Y-%m-%d %H:%M:%S")

        start, end = utc(since), utc(until)
        if start and end and start > end:
            raise HTTPException(422, "起始时间不能晚于结束时间")
        return search_jobs(store, {
            "repository_id": repository_id, "status": status, "target_branch": target_branch,
            "mr_iid": mr_iid, "sha": sha.lower() if sha else None, "since": start, "until": end,
        }, page, page_size)

    @app.get("/api/jobs/{job_id}/report", dependencies=[admin])
    def download_report(job_id: int) -> Response:
        """下载白名单报告；额外移除当前已知凭据，绝不返回原始 thinking。"""

        job = store.get_job(job_id)
        if job is None:
            raise HTTPException(404, "任务不存在")
        content = json.dumps(report_projection(job), ensure_ascii=False, indent=2)
        box = SecretBox(settings.master_key)
        secret_values = [settings.master_key, settings.admin_token]
        repository = store.get_repository(job["repository_id"]) or {}
        target = store.get_notification_target(repository.get("feishu_target_id", 0)) or {}
        for row, keys in (
            (repository, ("gitlab_token_ciphertext", "webhook_secret", "feishu_webhook")),
            (target, ("webhook_ciphertext", "signing_secret_ciphertext")),
            *((profile, ("api_key_ciphertext",)) for profile in store.list_model_profiles()),
        ):
            for key in keys:
                if row.get(key):
                    try:
                        secret_values.append(box.decrypt(row[key]))
                    except InvalidToken:
                        pass  # 已失效密文不会作为明文出现在报告中。
        for secret in sorted(filter(None, secret_values), key=len, reverse=True):
            content = content.replace(json.dumps(secret, ensure_ascii=False)[1:-1], "[REDACTED]")
        return Response(content, media_type="application/json", headers={
            "Content-Disposition": f'attachment; filename="review-{job_id}.json"',
            "Cache-Control": "no-store",
        })
