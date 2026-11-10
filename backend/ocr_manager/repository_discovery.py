"""管理员显式获取仓库资料；HTTP 只保存加密请求，Worker 执行有界 GitLab 读取。"""

from __future__ import annotations

import ipaddress
import json
import re
from typing import Any
from urllib.parse import quote, unquote, urlparse

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from ocr_manager.config import Settings
from ocr_manager.secrets import SecretBox
from ocr_manager.storage import Store


class DiscoveryInput(BaseModel):
    """令牌只供本次主机读取，服务端加密暂存并在完成、中断或过期后清除。"""

    remote_url: str = Field(min_length=1, max_length=1000)
    gitlab_token: str = Field(min_length=1, max_length=4000)
    model_config = {"extra": "forbid"}


def discovery_source(value: str) -> tuple[str, str, str]:
    """仅接受无凭据 HTTPS 项目地址，固定读取 API 路径且禁止重定向转发令牌。"""

    try:
        parsed = urlparse(value.strip())
        host = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port
    except ValueError:
        raise ValueError("仓库地址主机或端口无效") from None
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    path = unquote(parsed.path).strip("/").removesuffix(".git")
    if (parsed.scheme != "https" or not host or host == "localhost" or port == 0
            or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment or len(path.split("/")) < 2
            or not re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+", path)
            or any(part in {".", "..", "-"} for part in path.split("/"))
            or address and (address.is_loopback or address.is_link_local
                            or address.is_multicast or address.is_unspecified)):
        raise ValueError("请填写无凭据的 HTTPS GitLab 项目或 Clone 地址")
    authority = f"[{host}]" if ":" in host else host
    origin = f"https://{authority}" + (f":{port}" if port and port != 443 else "")
    return origin, path, f"{origin}/{path}.git"


def claim_discovery(store: Store) -> dict[str, Any] | None:
    """过期请求清除凭据；领取使用短事务，不占用模型槽。"""

    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("""UPDATE repository_discoveries SET status='failed',token_ciphertext='',
                   error='请求已过期，请重新获取',finished_at=CURRENT_TIMESTAMP
                   WHERE status='queued' AND created_at<datetime('now','-15 minutes')""")
        row = db.execute("SELECT * FROM repository_discoveries WHERE status='queued' "
                         "ORDER BY id LIMIT 1").fetchone()
        if row is not None:
            db.execute("UPDATE repository_discoveries SET status='running' WHERE id=?",
                       (row["id"],))
        return dict(row) if row is not None else None


def execute_discovery(store: Store, settings: Settings, task: dict[str, Any]) -> None:
    """仅保存白名单项目字段，不保存完整外部响应；失败不回显 URL、令牌或响应正文。"""

    result: dict[str, Any] | None = None
    error: str | None = None
    try:
        # 1. 再校验目标，并只向已明确指定的同一 HTTPS 主机发送本次令牌。
        origin, path, remote = discovery_source(task["remote_url"])
        key = SecretBox(settings.master_key).decrypt(task["token_ciphertext"])
        with httpx.Client(timeout=15, follow_redirects=False,
                          headers={"PRIVATE-TOKEN": key}) as client:
            endpoint = f"{origin}/api/v4/projects/{quote(path, safe='')}"
            with client.stream("GET", endpoint) as response:
                response.raise_for_status()
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > 1024 * 1024:
                        raise ValueError("项目响应过大")
        # 2. 只接受相同项目身份；不使用上游返回的任意 Clone URL 继续发起网络请求。
        data = json.loads(body)
        if (not isinstance(data, dict) or not isinstance(data.get("id"), int)
                or isinstance(data["id"], bool) or data["id"] <= 0
                or data.get("path_with_namespace") != path
                or not isinstance(data.get("name"), str) or not data["name"]
                or len(data["name"]) > 120
                or not isinstance(data.get("default_branch"), str)
                or not re.fullmatch(r"[A-Za-z0-9._/-]{1,200}", data["default_branch"])
                or data["default_branch"].startswith(("-", "/", "."))
                or data["default_branch"].endswith(("/", "."))
                or ".." in data["default_branch"] or "//" in data["default_branch"]):
            raise ValueError("项目身份或默认分支无法确认")
        result = {"name": data["name"], "project_id": data["id"], "gitlab_url": origin,
                  "remote_url": remote, "path_with_namespace": path,
                  "target_branch": data["default_branch"]}
    except httpx.HTTPStatusError as failure:
        error = f"GitLab 返回 HTTP {failure.response.status_code}，请核对项目地址与令牌权限"
    except httpx.TimeoutException:
        error = "GitLab 读取超时，请检查网络后重新获取"
    except Exception:
        error = "无法确认项目资料，请核对地址、令牌及默认分支，或使用手动填写"
    # 3. 无论成功失败均清除临时凭据；不自动重试外部读取。
    with store.connection() as db:
        db.execute("""UPDATE repository_discoveries SET status=?,token_ciphertext='',
                   result_json=?,error=?,finished_at=CURRENT_TIMESTAMP
                   WHERE id=? AND status='running'""",
                   ("failed" if error else "passed", json.dumps(result) if result else None,
                    error, task["id"]))


def register_discovery(app: FastAPI, store: Store, settings: Settings, admin: Any) -> None:
    """管理员可创建和读取资料请求；HTTP 不执行 Git、GitLab 或其他外部调用。"""

    @app.post("/api/repository-discoveries", dependencies=[admin], status_code=202)
    def create(payload: DiscoveryInput) -> dict[str, int | str]:
        """持久化显式查询；队列上限防止堆积临时凭据。"""

        try:
            _, _, remote = discovery_source(payload.remote_url)
        except ValueError as error:
            raise HTTPException(422, str(error)) from None
        with store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT COUNT(*) FROM repository_discoveries "
                          "WHERE status IN ('queued','running')").fetchone()[0] >= 10:
                raise HTTPException(409, "已有资料获取请求等待处理，请稍后重试")
            cursor = db.execute("INSERT INTO repository_discoveries(remote_url,token_ciphertext) "
                                "VALUES(?,?)", (remote, SecretBox(settings.master_key).encrypt(
                                    payload.gitlab_token)))
            return {"id": int(cursor.lastrowid or 0), "status": "queued"}

    @app.get("/api/repository-discoveries/{discovery_id}", dependencies=[admin])
    def read(discovery_id: int) -> dict[str, Any]:
        """仅返回安全投影，不能读取令牌密文或其他请求体。"""

        with store.connection() as db:
            row = db.execute("SELECT id,status,result_json,error FROM repository_discoveries "
                             "WHERE id=?", (discovery_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "资料获取请求不存在")
        return {"id": row["id"], "status": row["status"], "error": row["error"],
                "result": json.loads(row["result_json"]) if row["result_json"] else None}

    @app.delete("/api/repository-discoveries/{discovery_id}", dependencies=[admin])
    def cancel(discovery_id: int) -> dict[str, str]:
        """放弃尚未完成的请求并清除凭据；已发出的只读网络请求可能仍会完成。"""

        with store.connection() as db:
            db.execute("""UPDATE repository_discoveries SET status='failed',token_ciphertext='',
                error='已停止等待，请手动填写或重新获取',finished_at=CURRENT_TIMESTAMP
                WHERE id=? AND status IN ('queued','running')""", (discovery_id,))
        return {"status": "stopped"}
