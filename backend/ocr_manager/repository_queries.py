"""短期仓库查询会话；凭据绑定管理员会话和主机，HTTP 仅加密入队。"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any
from urllib.parse import quote
from uuid import uuid4

import httpx
from cryptography.fernet import InvalidToken
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from ocr_manager.secrets import SecretBox

if TYPE_CHECKING:
    from ocr_manager.config import Settings
    from ocr_manager.storage import Store


class QueryInput(BaseModel):
    """查询会话绑定输入；编辑留空令牌仅允许访问原主机。"""

    remote_url: str = Field(min_length=1, max_length=1000)
    gitlab_token: str = Field(default="", max_length=4000)
    repository_id: int | None = Field(default=None, gt=0)
    model_config = {"extra": "forbid"}


class BranchInput(BaseModel):
    """远程分页搜索，不把第一页结果作为全部候选。"""

    search: str = Field(default="", max_length=200)
    page: int = Field(default=1, ge=1, le=1000)
    model_config = {"extra": "forbid"}


def owner(request: Request) -> str:
    """只保存当前授权令牌的摘要；不同会话不能互读临时资料。"""

    return hashlib.sha256(
        (
            request.headers.get("authorization", "")
            or request.headers.get("x-admin-token", "")
            or "local-development"
        ).encode()
    ).hexdigest()


def query_row(store: Store, session_id: str, actor: str) -> dict[str, Any]:
    """过期会话立即清密文；主机和凭据变更后旧编辑引用不可再使用。"""

    with store.connection() as db:
        db.execute(
            "UPDATE repository_query_sessions SET token_ciphertext='' "
            "WHERE expires_at<=CURRENT_TIMESTAMP"
        )
        row = db.execute(
            "SELECT * FROM repository_query_sessions WHERE id=? AND owner=? "
            "AND expires_at>CURRENT_TIMESTAMP",
            (session_id, actor),
        ).fetchone()
    if row is None:
        raise HTTPException(409, "查询已过期，请重新识别仓库")
    result = dict(row)
    if result["repository_id"]:
        repository = store.get_repository(result["repository_id"])
        version = hashlib.sha256(
            str((repository or {}).get("gitlab_token_ciphertext", "")).encode()
        ).hexdigest()
        if version != result["credential_version"]:
            raise HTTPException(409, "已保存凭据发生变化，请重新识别")
    return result


def branch_result(
    settings: Settings, session: dict[str, Any], task: dict[str, Any]
) -> dict[str, Any]:
    """Worker 执行固定主机的只读请求，限制正文并拒绝重定向。"""

    from ocr_manager.repository_discovery import discovery_source

    origin, path, _ = discovery_source(session["remote_url"])
    key = SecretBox(settings.master_key).decrypt(session["token_ciphertext"])
    with httpx.Client(timeout=15, follow_redirects=False, headers={"PRIVATE-TOKEN": key}) as client:
        with client.stream(
            "GET",
            f"{origin}/api/v4/projects/{quote(path, safe='')}/repository/branches",
            params={"search": task["search"], "page": task["page"], "per_page": 50},
        ) as response:
            response.raise_for_status()
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > 1024 * 1024:
                    raise ValueError("分支响应过大")
            next_page = response.headers.get("x-next-page", "")
    rows = json.loads(body)
    if not isinstance(rows, list) or any(
        not isinstance(row, dict) or not isinstance(row.get("name"), str) for row in rows
    ):
        raise ValueError("分支响应无效")
    return {
        "items": [{"name": row["name"], "default": bool(row.get("default"))} for row in rows],
        "next_page": int(next_page) if next_page else None,
    }


def validate_reference(
    store: Store,
    actor: str,
    reference: str,
    remote: str,
    token: str,
    branch: str | list[str],
    repository_id: int | None,
) -> dict[str, Any]:
    """保存只消费已核验引用，身份和分支由 Worker 结果证明；不访问网络。"""

    from ocr_manager.repository_discovery import discovery_source

    session = query_row(store, reference, actor)
    if (
        session["repository_id"] != repository_id
        or session["remote_url"] != discovery_source(remote)[2]
    ):
        raise HTTPException(409, "仓库来源已变化，请重新识别")
    if repository_id:
        repository = store.get_repository(repository_id)
        version = hashlib.sha256(
            str((repository or {}).get("gitlab_token_ciphertext", "")).encode()
        ).hexdigest()
        if version != session["credential_version"]:
            raise HTTPException(409, "已保存凭据发生变化，请重新识别")
    if session["input_token_required"] and not token:
        raise HTTPException(409, "请保留本次识别使用的 Token 后再保存")
    if token and hashlib.sha256(token.encode()).hexdigest() != session["credential_digest"]:
        raise HTTPException(409, "Token 已变化，请重新识别")
    metadata = json.loads(session["result_json"]) if session["result_json"] else None
    if not metadata:
        raise HTTPException(409, "仓库资料尚未核验")
    with store.connection() as db:
        rows = db.execute(
            "SELECT result_json FROM repository_discoveries WHERE query_session_id=? "
            "AND operation='branches' AND status='passed'",
            (reference,),
        ).fetchall()
    verified = {item["name"] for row in rows for item in json.loads(row[0])["items"]}
    selected = [branch] if isinstance(branch, str) else branch
    if not selected or not set(selected) <= verified:
        raise HTTPException(409, "所选分支尚未核验，请重新搜索选择")
    return dict(metadata)


def register_queries(app: FastAPI, store: Store, settings: Settings, admin: Any) -> None:
    """管理员查询端点；会话与请求共同限额，临时凭据不进入响应或日志。"""

    @app.post("/api/repository-query-sessions", dependencies=[admin], status_code=202)
    def create(payload: QueryInput, request: Request) -> dict[str, Any]:
        """来源不变时允许编辑使用已存凭据；换主机必须新凭据。"""

        from ocr_manager.repository_discovery import discovery_source

        try:
            origin, _, remote = discovery_source(payload.remote_url)
        except ValueError as error:
            raise HTTPException(422, str(error)) from None
        repository = store.get_repository(payload.repository_id) if payload.repository_id else None
        if payload.repository_id and repository is None:
            raise HTTPException(404, "项目不存在")
        credential_version = hashlib.sha256(
            str((repository or {}).get("gitlab_token_ciphertext", "")).encode()
        ).hexdigest()
        key = payload.gitlab_token
        box = SecretBox(settings.master_key)
        if not key and payload.repository_id:
            repository = store.get_repository(payload.repository_id)
            if not repository:
                raise HTTPException(404, "项目不存在")
            if origin != repository["gitlab_url"].rstrip("/"):
                raise HTTPException(422, "更换 GitLab 主机需要重新输入 Token")
            try:
                key = box.decrypt(repository["gitlab_token_ciphertext"])
            except (InvalidToken, ValueError):
                raise HTTPException(422, "已保存 Token 不可用，请重新填写") from None
        if not key:
            raise HTTPException(422, "请填写 GitLab Token")
        identity = uuid4().hex
        with store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "UPDATE repository_query_sessions SET token_ciphertext='' "
                "WHERE expires_at<=CURRENT_TIMESTAMP"
            )
            if (
                db.execute(
                    "SELECT COUNT(*) FROM repository_discoveries "
                    "WHERE status IN ('queued','running')"
                ).fetchone()[0]
                >= 20
            ):
                raise HTTPException(409, "远程查询繁忙，请稍后重试")
            if (
                db.execute(
                    "SELECT COUNT(*) FROM repository_query_sessions WHERE owner=? "
                    "AND expires_at>CURRENT_TIMESTAMP",
                    (owner(request),),
                ).fetchone()[0]
                >= 10
            ):
                raise HTTPException(409, "查询会话过多，请稍后重试")
            db.execute(
                """INSERT INTO repository_query_sessions
                (id,owner,remote_url,token_ciphertext,repository_id,credential_digest,
                credential_version,input_token_required,expires_at)
                VALUES(?,?,?,?,?,?,?,?,datetime('now','+15 minutes'))""",
                (
                    identity,
                    owner(request),
                    remote,
                    box.encrypt(key),
                    payload.repository_id,
                    hashlib.sha256(key.encode()).hexdigest(),
                    credential_version,
                    int(bool(payload.gitlab_token)),
                ),
            )
            task = db.execute(
                "INSERT INTO repository_discoveries"
                "(remote_url,token_ciphertext,query_session_id) VALUES(?,?,?)",
                (remote, box.encrypt(key), identity),
            ).lastrowid
        return {"session_id": identity, "id": task}

    @app.post(
        "/api/repository-query-sessions/{session_id}/branches",
        dependencies=[admin],
        status_code=202,
    )
    def branches(session_id: str, payload: BranchInput, request: Request) -> dict[str, int]:
        """分页查询先入 SQLite，网络由 ingress Worker 执行。"""

        session = query_row(store, session_id, owner(request))
        with store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if (
                db.execute(
                    "SELECT COUNT(*) FROM repository_discoveries WHERE status IN "
                    "('queued','running')"
                ).fetchone()[0]
                >= 20
            ):
                raise HTTPException(409, "分支查询繁忙，请稍后重试")
            task = db.execute(
                """INSERT INTO repository_discoveries
                (remote_url,token_ciphertext,query_session_id,operation,search,page)
                VALUES(?,'',?,'branches',?,?)""",
                (session["remote_url"], session_id, payload.search, payload.page),
            ).lastrowid
        return {"id": int(task or 0)}

    @app.delete("/api/repository-query-sessions/{session_id}", dependencies=[admin])
    def cancel(session_id: str, request: Request) -> dict[str, str]:
        """放弃草稿即时过期，不删除查询事实。"""

        with store.connection() as db:
            row = db.execute(
                "SELECT 1 FROM repository_query_sessions WHERE id=? AND owner=?",
                (session_id, owner(request)),
            ).fetchone()
            if row is None:
                raise HTTPException(404, "查询不存在")
            db.execute(
                "UPDATE repository_query_sessions SET token_ciphertext='',"
                "expires_at=CURRENT_TIMESTAMP WHERE id=?",
                (session_id,),
            )
            db.execute(
                "UPDATE repository_discoveries SET token_ciphertext='',status='failed',"
                "error='查询已取消',finished_at=CURRENT_TIMESTAMP "
                "WHERE query_session_id=? AND status IN ('queued','running')",
                (session_id,),
            )
        return {"status": "expired"}
