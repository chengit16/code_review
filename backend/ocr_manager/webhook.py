"""验证 GitLab Merge Request webhook 的来源和合并事件范围。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from fastapi import HTTPException


def verify_webhook(
    headers: dict[str, str],
    body: bytes,
    auth_kind: str,
    token: str,
) -> None:
    """按 GitLab 版本校验签名或旧版密钥，失败时不解析业务数据。"""

    if auth_kind == "secret":
        received = headers.get("x-gitlab-token", "")
        if not received or not hmac.compare_digest(received, token):
            raise HTTPException(status_code=401, detail="GitLab webhook 鉴权失败")
        return

    message_id = headers.get("webhook-id", "")
    timestamp = headers.get("webhook-timestamp", "")
    signature = headers.get("webhook-signature", "")
    try:
        sent_at = int(timestamp)
        key = base64.b64decode(token.removeprefix("whsec_"), validate=True)
    except (ValueError, TypeError) as error:
        raise HTTPException(status_code=401, detail="GitLab webhook 签名无效") from error
    if not message_id or not signature or abs(time.time() - sent_at) > 300:
        raise HTTPException(status_code=401, detail="GitLab webhook 签名无效")
    signed = message_id.encode() + b"." + timestamp.encode() + b"." + body
    expected = "v1," + base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
    if not any(hmac.compare_digest(expected, item) for item in signature.split()):
        raise HTTPException(status_code=401, detail="GitLab webhook 签名无效")


def parse_merge_event(body: bytes, project_id: int, target_branch: str) -> dict[str, Any] | None:
    """只接受配置项目目标分支上的合并动作；其他合法事件不入队。"""

    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError) as error:
        raise HTTPException(status_code=422, detail="无效的 GitLab JSON") from error
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="无效的 GitLab 事件")
    if payload.get("object_kind") != "merge_request":
        return None
    attributes = payload.get("object_attributes")
    project = payload.get("project")
    if not isinstance(attributes, dict) or not isinstance(project, dict):
        raise HTTPException(status_code=422, detail="GitLab MR 字段缺失")
    if attributes.get("action") != "merge" or attributes.get("target_branch") != target_branch:
        return None
    if project.get("id") != project_id or attributes.get("target_project_id") != project_id:
        raise HTTPException(status_code=403, detail="GitLab 项目不匹配")
    mr_iid = attributes.get("iid")
    if not isinstance(mr_iid, int) or isinstance(mr_iid, bool) or mr_iid <= 0:
        raise HTTPException(status_code=422, detail="GitLab MR IID 无效")
    return {
        "mr_iid": mr_iid,
        "merge_sha": attributes.get("merge_commit_sha") or None,
        "squash_sha": attributes.get("squash_commit_sha") or None,
    }
