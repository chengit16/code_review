"""执行管理台发起的外部连接诊断；只把脱敏结论写回 SQLite。"""

from __future__ import annotations

import subprocess
from dataclasses import replace
from typing import Any

import httpx

from ocr_manager.config import Settings
from ocr_manager.feishu import FeishuDeliveryError, send_connection_test
from ocr_manager.git_repo import GitRepository
from ocr_manager.gitlab import GitLabClient
from ocr_manager.ocr import check_model_connection
from ocr_manager.secrets import SecretBox
from ocr_manager.storage import Store


def connection_error(kind: str, error: Exception) -> str:
    """外部异常可能包含含令牌的 URL，管理页只接收稳定的安全摘要。"""

    if isinstance(error, FeishuDeliveryError):
        return str(error)
    if isinstance(error, httpx.HTTPStatusError):
        return f"{kind} 返回 HTTP {error.response.status_code}"
    if isinstance(error, (httpx.TimeoutException, subprocess.TimeoutExpired, TimeoutError)):
        return f"{kind} 连接超时"
    if isinstance(error, FileNotFoundError):
        return f"{kind} 命令不存在"
    if isinstance(error, httpx.RequestError):
        return f"{kind} 网络连接失败"
    if isinstance(error, ValueError):
        if str(error) == "飞书 Hook 尚未配置":
            return str(error)
        return f"{kind} 配置与目标不匹配"
    if kind == "model" and isinstance(error, RuntimeError) and str(error).startswith("OCR 模型"):
        return str(error)
    return f"{kind} 测试失败（{type(error).__name__}）"


def run_connection_check(store: Store, settings: Settings, check: dict[str, Any]) -> None:
    """诊断只读访问或测试消息；不创建业务事件、评审任务和正式通知。"""

    kind = str(check["kind"])
    repository = store.get_repository(check["repository_id"]) if check["repository_id"] else None
    try:
        if kind == "model":
            profile = store.get_model_profile()
            model_settings = settings
            if profile is not None:
                model_settings = replace(
                    settings,
                    ocr_provider=profile["provider"],
                    ocr_model=profile["model"],
                    ocr_api_key=SecretBox(settings.master_key).decrypt(
                        profile["api_key_ciphertext"]
                    ),
                )
            check_model_connection(model_settings, settings.data_dir / "checks" / str(check["id"]))
        elif repository is None:
            raise ValueError("仓库不存在")
        elif kind == "git":
            GitRepository(settings.data_dir, repository).check_access()
        elif kind == "gitlab":
            GitLabClient(repository["gitlab_url"], settings.gitlab_api_token).check_access(
                repository["project_id"],
                repository["target_branch"],
                repository["remote_url"],
            )
        elif kind == "feishu":
            target = (
                store.get_notification_target(repository["feishu_target_id"])
                if repository["feishu_target_id"]
                else None
            )
            webhook_ciphertext = (
                target["webhook_ciphertext"] if target else repository["feishu_webhook"]
            )
            if not webhook_ciphertext:
                raise ValueError("飞书 Hook 尚未配置")
            box = SecretBox(settings.master_key)
            webhook = box.decrypt(webhook_ciphertext)
            signing_secret = (
                box.decrypt(target["signing_secret_ciphertext"])
                if target and target["signing_secret_ciphertext"]
                else ""
            )
            if signing_secret:
                send_connection_test(webhook, signing_secret)
            else:
                send_connection_test(webhook)
        else:
            raise ValueError("未知连接测试类型")
    except Exception as error:
        store.finish_connection_check(check["id"], connection_error(kind, error))
    else:
        store.finish_connection_check(check["id"], None)
