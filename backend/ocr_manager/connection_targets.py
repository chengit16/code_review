"""计算测试目标的配置指纹；只在数据库内部使用密文摘要，不向页面投影凭据。"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any


def connection_fingerprint(
    db: sqlite3.Connection, kind: str, repository_id: int | None,
    model_profile_id: int | None = None, notification_target_id: int | None = None,
) -> str | None:
    """关联实际连接字段；名称、价格和默认模型切换不改变某个指定模型的可连接性。"""

    row: sqlite3.Row | None
    if kind == "model":
        row = db.execute("SELECT provider,model,base_url,api_key_ciphertext FROM model_profiles "
                         "WHERE id=?", (model_profile_id,)).fetchone()
    elif kind == "feishu":
        if notification_target_id is None:
            repo = db.execute("SELECT feishu_target_id,feishu_webhook FROM repositories WHERE id=?",
                              (repository_id,)).fetchone()
            if repo is None:
                return None
            notification_target_id = repo["feishu_target_id"]
            if notification_target_id is None:
                row = repo
            else:
                row = db.execute("SELECT webhook_ciphertext,signing_secret_ciphertext "
                                 "FROM notification_targets WHERE id=?",
                                 (notification_target_id,)).fetchone()
        else:
            row = db.execute("SELECT webhook_ciphertext,signing_secret_ciphertext "
                             "FROM notification_targets WHERE id=?",
                             (notification_target_id,)).fetchone()
    else:
        row = db.execute("SELECT gitlab_url,project_id,remote_url,target_branch,"
                         "gitlab_token_ciphertext FROM repositories WHERE id=?",
                         (repository_id,)).fetchone()
    if row is None:
        return None
    identity = [kind, repository_id, model_profile_id, notification_target_id, dict(row)]
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()


def check_is_current(db: sqlite3.Connection, check: dict[str, Any]) -> bool:
    """无版本证据的历史测试保持待核实；删除目标或配置改变后不能继续算通过。"""

    expected = check.get("config_fingerprint")
    return bool(expected and expected == connection_fingerprint(
        db, check["kind"], check["repository_id"], check.get("model_profile_id"),
        check.get("notification_target_id"),
    ))
