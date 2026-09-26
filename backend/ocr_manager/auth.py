"""管理账号、有限期会话与角色授权；数据库只保存密码和令牌摘要。"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from ocr_manager.storage import Store


AUTH_MIGRATION = """
CREATE TABLE management_users (
  id INTEGER PRIMARY KEY,
  username TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('admin','reader')),
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0,1)),
  failed_attempts INTEGER NOT NULL DEFAULT 0,
  locked_until TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE management_sessions (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES management_users(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL UNIQUE,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_management_sessions_user ON management_sessions(user_id);
CREATE TABLE management_auth_mode (
  id INTEGER PRIMARY KEY CHECK (id=1),
  users_enabled INTEGER NOT NULL DEFAULT 0 CHECK (users_enabled IN (0,1))
);
INSERT INTO management_auth_mode(id,users_enabled) VALUES(1,0);
ALTER TABLE audit_log ADD COLUMN actor_id INTEGER;
ALTER TABLE audit_log ADD COLUMN actor_name TEXT;
"""


def hash_password(password: str) -> str:
    """采用随机盐和 scrypt；密码本身及派生密钥都不进入响应或日志。"""

    if not 12 <= len(password) <= 128:
        raise ValueError("密码长度须为 12 至 128 个字符")
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return f"scrypt$16384$8$1${salt.hex()}${derived.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    """对登录输入执行恒定时间摘要比较；损坏的历史哈希一律拒绝。"""

    try:
        algorithm, n, r, p, salt, expected = encoded.split("$")
        if algorithm != "scrypt":
            return False
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt),
                                n=int(n), r=int(r), p=int(p))
        return hmac.compare_digest(actual, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False


def users_mode(store: Store) -> bool:
    """运行时读取模式，切换后所有进程立即使用同一持久化事实。"""

    with store.connection() as db:
        return bool(db.execute("SELECT users_enabled FROM management_auth_mode WHERE id=1"
                               ).fetchone()[0])


def session_identity(store: Store, token: str) -> dict[str, Any] | None:
    """只接受未过期、未禁用账号的会话；角色变更立即影响旧会话。"""

    digest = hashlib.sha256(token.encode()).hexdigest()
    with store.connection() as db:
        row = db.execute("""SELECT u.id,u.username,u.role FROM management_sessions s
            JOIN management_users u ON u.id=s.user_id WHERE s.token_hash=?
            AND s.expires_at>CURRENT_TIMESTAMP AND u.enabled=1""", (digest,)).fetchone()
    return dict(row) if row else None


def public_user(row: dict[str, Any]) -> dict[str, Any]:
    """管理 API 不返回密码摘要、锁定字段或会话摘要。"""

    return {key: row[key] for key in ("id", "username", "role", "enabled", "created_at")}


class LoginRequest(BaseModel):
    """账号登录输入，不允许夹带额外授权字段。"""

    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class UserCreate(BaseModel):
    """仅管理员可创建账号；只读角色不能提升自己。"""

    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    password: str = Field(min_length=12, max_length=128)
    role: str = Field(pattern=r"^(admin|reader)$")


class UserUpdate(BaseModel):
    """管理员可调整角色、启停或重置密码，字段缺失表示保留。"""

    model_config = ConfigDict(extra="forbid")
    role: str | None = Field(default=None, pattern=r"^(admin|reader)$")
    enabled: bool | None = None
    password: str | None = Field(default=None, min_length=12, max_length=128)


class ModeUpdate(BaseModel):
    """账号模式显式启停；开启前须已有可用管理员。"""

    model_config = ConfigDict(extra="forbid")
    users_enabled: bool


def register_auth(app: FastAPI, store: Store,
                  require_access: Callable[[Request], dict[str, Any]]) -> None:
    """账号路由统一复用服务端身份依赖，用户模式的管理操作只允许管理员。"""

    def require_role(request: Request) -> dict[str, Any]:
        """账号管理始终要求管理员；默认开发模式作为可信本机管理员。"""

        identity: dict[str, Any] = require_access(request)
        if identity["role"] != "admin":
            raise HTTPException(403, "需要管理员权限")
        return identity

    @app.post("/api/auth/login")
    def login(request: Request, payload: LoginRequest) -> dict[str, Any]:
        """每账号连续失败五次锁定五分钟；登录成功签发十二小时随机会话。"""

        if not users_mode(store):
            raise HTTPException(409, "账号模式未启用")
        token: str | None = None
        user: dict[str, Any] | None = None
        with store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM management_sessions WHERE expires_at<=CURRENT_TIMESTAMP")
            row = db.execute("SELECT * FROM management_users WHERE username=? COLLATE NOCASE",
                             (payload.username,)).fetchone()
            now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
            locked = bool(row and row["locked_until"] and row["locked_until"] > now)
            valid = bool(row and row["enabled"] and not locked and
                         verify_password(payload.password, row["password_hash"]))
            if not valid:
                if row and not locked:
                    db.execute("""UPDATE management_users SET failed_attempts=failed_attempts+1,
                        locked_until=CASE WHEN failed_attempts+1>=5 THEN
                        datetime('now','+5 minutes') ELSE NULL END WHERE id=?""", (row["id"],))
            else:
                db.execute("""UPDATE management_users SET failed_attempts=0,
                    locked_until=NULL WHERE id=?""",
                           (row["id"],))
                token = secrets.token_urlsafe(32)
                expires = (datetime.now(UTC) + timedelta(hours=12)).strftime(
                    "%Y-%m-%d %H:%M:%S")
                db.execute("""INSERT INTO management_sessions(user_id,token_hash,expires_at)
                    VALUES(?,?,?)""", (row["id"], hashlib.sha256(token.encode()).hexdigest(),
                                      expires))
                user = public_user(dict(row))
        if token is None or user is None:
            raise HTTPException(401, "用户名或密码无效")
        request.state.identity = user
        return {"token": token, "user": user}

    @app.get("/api/auth/me")
    def me(request: Request) -> dict[str, Any]:
        """前端恢复界面状态时从服务端获取当前角色。"""

        return require_access(request)

    @app.post("/api/auth/logout")
    def logout(request: Request) -> dict[str, str]:
        """删除当前会话；默认开发和共享口令模式不保存会话。"""

        identity = require_access(request)
        if identity["id"] is not None:
            header = request.headers.get("authorization", "")
            token = header.removeprefix("Bearer ")
            with store.connection() as db:
                db.execute("DELETE FROM management_sessions WHERE token_hash=?",
                           (hashlib.sha256(token.encode()).hexdigest(),))
        return {"status": "ok"}

    @app.get("/api/auth/mode")
    def mode(request: Request) -> dict[str, bool]:
        """仅管理员可查看或切换账号模式。"""

        require_role(request)
        return {"users_enabled": users_mode(store)}

    @app.put("/api/auth/mode")
    def change_mode(request: Request, payload: ModeUpdate) -> dict[str, bool]:
        """切换与管理员存在性核对在同一写事务；关闭后用户会话失去访问权。"""

        require_role(request)
        with store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if payload.users_enabled and not db.execute("""SELECT 1 FROM management_users
                WHERE role='admin' AND enabled=1 LIMIT 1""").fetchone():
                raise HTTPException(409, "请先创建至少一名管理员")
            db.execute("UPDATE management_auth_mode SET users_enabled=? WHERE id=1",
                       (payload.users_enabled,))
        return {"users_enabled": payload.users_enabled}

    @app.get("/api/auth/users")
    def list_users(request: Request) -> list[dict[str, Any]]:
        """用户列表不包含认证材料。"""

        require_role(request)
        with store.connection() as db:
            return [public_user(dict(row)) for row in db.execute(
                "SELECT * FROM management_users ORDER BY id")]

    @app.post("/api/auth/users", status_code=201)
    def create_user(request: Request, payload: UserCreate) -> dict[str, Any]:
        """新账号密码在持久化前派生；重复用户名以冲突响应。"""

        require_role(request)
        password_hash = hash_password(payload.password)
        with store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM management_users WHERE username=? COLLATE NOCASE",
                          (payload.username,)).fetchone():
                raise HTTPException(409, "用户名已存在")
            cursor = db.execute("""INSERT INTO management_users(username,password_hash,role)
                VALUES(?,?,?)""", (payload.username, password_hash, payload.role))
            user = db.execute("SELECT * FROM management_users WHERE id=?",
                              (cursor.lastrowid,)).fetchone()
        return public_user(dict(user))

    @app.patch("/api/auth/users/{user_id}")
    def update_user(request: Request, user_id: int, payload: UserUpdate) -> dict[str, Any]:
        """最后一名启用管理员不可降权或停用，且变更会撤销目标会话。"""

        require_role(request)
        with store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM management_users WHERE id=?", (user_id,)).fetchone()
            if row is None:
                raise HTTPException(404, "用户不存在")
            new_role = payload.role or row["role"]
            new_enabled = row["enabled"] if payload.enabled is None else payload.enabled
            if (row["role"] == "admin" and row["enabled"] and
                (new_role != "admin" or not new_enabled)):
                count = db.execute("""SELECT count(*) FROM management_users
                    WHERE role='admin' AND enabled=1""").fetchone()[0]
                if count <= 1:
                    raise HTTPException(409, "不能停用最后一名管理员")
            password_hash = (hash_password(payload.password) if payload.password else
                             row["password_hash"])
            db.execute("""UPDATE management_users SET role=?,enabled=?,password_hash=?,
                failed_attempts=0,locked_until=NULL WHERE id=?""",
                (new_role, new_enabled, password_hash, user_id))
            db.execute("DELETE FROM management_sessions WHERE user_id=?", (user_id,))
            updated = db.execute("SELECT * FROM management_users WHERE id=?", (user_id,)).fetchone()
        return public_user(dict(updated))

    @app.delete("/api/auth/users/{user_id}")
    def delete_user(request: Request, user_id: int) -> dict[str, str]:
        """删除账号会级联撤销会话；最后一名管理员始终保留恢复入口。"""

        require_role(request)
        with store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT role,enabled FROM management_users WHERE id=?",
                             (user_id,)).fetchone()
            if row is None:
                raise HTTPException(404, "用户不存在")
            if row["role"] == "admin" and row["enabled"]:
                count = db.execute("""SELECT count(*) FROM management_users
                    WHERE role='admin' AND enabled=1""").fetchone()[0]
                if count <= 1:
                    raise HTTPException(409, "不能删除最后一名管理员")
            db.execute("DELETE FROM management_users WHERE id=?", (user_id,))
        return {"status": "deleted"}
