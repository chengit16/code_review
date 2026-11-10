"""执行管理台发起的外部连接诊断；只把脱敏结论写回 SQLite。"""

from __future__ import annotations

import subprocess
from dataclasses import replace
from typing import Any

import httpx

from ocr_manager.config import Settings
from ocr_manager.connection_targets import check_is_current
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
    try:
        # 同一读取快照内核对目标并冻结外部调用参数，完成事务再次核对变化。
        with store.connection() as db:
            db.execute("BEGIN")
            current = check_is_current(db, check)
            repo_row = db.execute("SELECT * FROM repositories WHERE id=?",
                                  (check["repository_id"],)).fetchone()
            repository = dict(repo_row) if repo_row else None
            model_row = db.execute("SELECT * FROM model_profiles WHERE id=?",
                                   (check.get("model_profile_id"),)).fetchone()
            profile = dict(model_row) if model_row else None
            target_id = check.get("notification_target_id") or (
                repository["feishu_target_id"] if repository else None)
            target_row = db.execute("SELECT * FROM notification_targets WHERE id=?",
                                    (target_id,)).fetchone()
            target = dict(target_row) if target_row else None
        if not current:
            store.finish_connection_check(check["id"], "配置已更改或无版本证据，请重新测试")
            return
        if kind == "model":
            model_settings = settings
            if profile is not None:
                model_settings = replace(
                    settings,
                    ocr_provider=profile["provider"],
                    ocr_model=profile["model"],
                    ocr_base_url=profile["base_url"],
                    ocr_api_key=SecretBox(settings.master_key).decrypt(
                        profile["api_key_ciphertext"]
                    ) if profile["api_key_ciphertext"] else "",
                )
            check_model_connection(model_settings, settings.data_dir / "checks" / str(check["id"]))
        elif kind == "feishu" and check.get("notification_target_id"):
            if target is None:
                raise ValueError("通知通道不存在")
            box = SecretBox(settings.master_key)
            webhook = box.decrypt(target["webhook_ciphertext"])
            signing_secret = (box.decrypt(target["signing_secret_ciphertext"])
                              if target["signing_secret_ciphertext"] else "")
            if signing_secret:
                send_connection_test(webhook, signing_secret)
            else:
                send_connection_test(webhook)
        elif repository is None:
            raise ValueError("仓库不存在")
        elif kind == "git":
            if repository["gitlab_token_ciphertext"]:
                repository["gitlab_token"] = SecretBox(settings.master_key).decrypt(
                    repository["gitlab_token_ciphertext"]
                )
            GitRepository(settings.data_dir, repository).check_access()
        elif kind == "gitlab":
            token = (
                SecretBox(settings.master_key).decrypt(repository["gitlab_token_ciphertext"])
                if repository["gitlab_token_ciphertext"]
                else settings.gitlab_api_token
            )
            GitLabClient(repository["gitlab_url"], token).check_access(
                repository["project_id"],
                repository["target_branch"],
                repository["remote_url"],
            )
        elif kind == "feishu":
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
