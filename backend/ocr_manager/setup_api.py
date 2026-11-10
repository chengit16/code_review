"""投影管理员接入所需的生效事实；不读取远端规则、执行测试或回显凭据。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException

from ocr_manager.config import Settings
from ocr_manager.project_limits import get_limits
from ocr_manager.scheduler_config import read_scheduler_config
from ocr_manager.storage import Store


def effective_configuration(store: Store, settings: Settings, repository_id: int) -> dict[str, Any]:
    """说明后续任务配置来源，不把历史执行或仓库规则文件推断为当前生效。"""

    repo = store.get_repository(repository_id)
    if repo is None:
        raise HTTPException(404, "项目不存在")
    limits = get_limits(store, repository_id)
    profile = (next((item for item in store.list_model_profiles()
                     if item["id"] == limits["model_profile_id"]), None)
               if limits["model_profile_id"] else store.get_model_profile())
    with store.connection() as db:
        changed = db.execute("""SELECT id,created_at FROM config_revisions
            WHERE object_type='repository' AND object_id=? ORDER BY id DESC LIMIT 1""",
                             (repository_id,)).fetchone()
        latest_job = db.execute("""SELECT id,status,finished_at FROM review_jobs
            WHERE repository_id=? ORDER BY id DESC LIMIT 1""", (repository_id,)).fetchone()
    return {
        "repository_id": repository_id,
        "model": {"id": profile["id"] if profile else None,
                  "name": profile["name"] if profile else None,
                  "model": profile["model"] if profile else None,
                  "complete": bool(profile and profile["model"] and profile["api_key_ciphertext"]),
                  "source": "project" if limits["model_profile_id"] else "global"},
        "timeout_seconds": {"value": limits["timeout_seconds"] or settings.ocr_timeout_seconds,
                            "source": "project" if limits["timeout_seconds"] else "process"},
        "max_files": limits["max_files"], "max_tokens_budget": limits["max_tokens_budget"],
        "newline_filter_enabled": bool(limits["newline_filter_enabled"]),
        "rules": {"global_configured": store.get_review_rule(None) is not None,
                  "project_configured": store.get_review_rule(repository_id) is not None,
                  "repository_file": "执行时按对应提交读取；此处尚未核实"},
        "repository_change": dict(changed) if changed else None,
        "latest_job": dict(latest_job) if latest_job else None,
    }


def register_setup(app: FastAPI, store: Store, settings: Settings, admin: Any) -> None:
    """只向管理员提供保存配置及当前进程摘要，不以 HTTP 执行外部动作。"""

    @app.get("/api/repositories/{repository_id}/effective-configuration", dependencies=[admin])
    def effective(repository_id: int) -> dict[str, Any]:
        """读取当前配置；在途及历史任务仍以自己的执行快照为准。"""

        return effective_configuration(store, settings, repository_id)

    @app.get("/api/model-profile-usage", dependencies=[admin])
    def model_usage() -> dict[str, int]:
        """只计显式项目引用，不把非默认模型误称未使用。"""

        with store.connection() as db:
            return {str(row["model_profile_id"]): row["count"] for row in db.execute(
                "SELECT model_profile_id,COUNT(*) AS count FROM project_review_limits "
                "WHERE model_profile_id IS NOT NULL GROUP BY model_profile_id")}

    @app.get("/api/deployment-summary", dependencies=[admin])
    def deployment() -> dict[str, Any]:
        """白名单投影进程值；不回显私有文件路径、命令参数或密钥。"""

        return {"auth_mode": "dev" if settings.dev_mode else "protected",
                "ocr_command": Path(settings.ocr_command).name,
                "timeout_seconds": settings.ocr_timeout_seconds,
                "ocr_internal_concurrency": settings.ocr_concurrency,
                "model_task_concurrency": read_scheduler_config(store)["model_task_concurrency"],
                "review_language": settings.review_language, "effort": settings.ocr_effort,
                "source": "当前 API 进程读取的部署配置；不证明 Worker 进程完全一致",
                "restart": "部署配置变更需协调重启 API 与 Worker；页面任务并发另行热应用"}
