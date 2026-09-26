"""配置版本与字段摘要；版本写入和配置修改通过 SQLite 触发器原子完成。"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from ocr_manager.model_pricing import PRICE_FIELDS
from ocr_manager.secrets import SecretBox

if TYPE_CHECKING:
    from ocr_manager.storage import Store

CONFIG_FIELDS = {
    "repository": ("repositories", (
        "name", "gitlab_url", "project_id", "remote_url", "path_with_namespace",
        "target_branch", "auth_kind", "webhook_secret", "gitlab_token_ciphertext",
        "feishu_webhook", "feishu_target_id", "enabled", "webhook_id",
        "enable_merge_requests", "enable_default_branch_pushes",
    )),
    "notification_target": ("notification_targets", (
        "name", "webhook_ciphertext", "signing_secret_ciphertext",
    )),
    "model_profile": ("model_profiles", (
        "name", "provider", "model", "base_url", "api_key_ciphertext", "enabled",
    )),
}
SECRET_FIELDS = frozenset({"webhook_secret", "gitlab_token_ciphertext", "feishu_webhook",
                           "webhook_ciphertext", "signing_secret_ciphertext",
                           "api_key_ciphertext"})


def history_migration() -> str:
    """只为配置字段建立触发器，合法 Webhook 时间等运行元数据不产生版本。"""

    sql = """
    CREATE TABLE config_revisions (
      id INTEGER PRIMARY KEY, object_type TEXT NOT NULL, object_id INTEGER NOT NULL,
      action TEXT NOT NULL, before_json TEXT, after_json TEXT,
      actor TEXT NOT NULL DEFAULT '共享管理会话', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX idx_config_revisions ON config_revisions(object_type, object_id, id DESC);
    """
    for kind, (table, fields) in CONFIG_FIELDS.items():
        def snapshot(prefix: str, fields: tuple[str, ...] = fields) -> str:
            return "json_object(" + ",".join(f"'{f}',{prefix}.{f}" for f in fields) + ")"
        before, after = snapshot("OLD"), snapshot("NEW")
        sql += f"""
        INSERT INTO config_revisions(object_type,object_id,action,after_json,actor)
          SELECT '{kind}',id,'baseline',{snapshot(table)},'迁移基线' FROM {table};
        CREATE TRIGGER history_{table}_insert AFTER INSERT ON {table} BEGIN
          INSERT INTO config_revisions(object_type,object_id,action,after_json)
          VALUES ('{kind}',NEW.id,'created',{after}); END;
        CREATE TRIGGER history_{table}_update AFTER UPDATE ON {table}
          WHEN {before}!={after} BEGIN
          INSERT INTO config_revisions(object_type,object_id,action,before_json,after_json)
          VALUES ('{kind}',NEW.id,'updated',{before},{after}); END;
        CREATE TRIGGER history_{table}_delete AFTER DELETE ON {table} BEGIN
          INSERT INTO config_revisions(object_type,object_id,action,before_json)
          VALUES ('{kind}',OLD.id,'deleted',{before}); END;
        """
    return sql


def list_config_history(store: Store, kind: str, object_id: int | None) -> list[dict[str, Any]]:
    """只暴露字段差异；密文和凭据长度均不进入响应。"""

    with store.connection() as db:
        rows = db.execute(
            """SELECT * FROM config_revisions WHERE object_type=?
            AND (? IS NULL OR object_id=?) ORDER BY id DESC LIMIT 100""",
            (kind, object_id, object_id),
        ).fetchall()
    result = []
    for row in rows:
        before = json.loads(row["before_json"] or "{}")
        after = json.loads(row["after_json"] or "{}")
        changes = []
        fields = CONFIG_FIELDS[kind][1] + (PRICE_FIELDS if kind == "model_profile" else ())
        for field in fields:
            if before.get(field) == after.get(field):
                continue
            changes.append({"field": field, "secret": field in SECRET_FIELDS,
                            "before": "已配置" if before.get(field) else "未配置",
                            "after": "已配置" if after.get(field) else "未配置"}
                           if field in SECRET_FIELDS else
                           {"field": field, "secret": False,
                            "before": before.get(field), "after": after.get(field)})
        result.append({key: row[key] for key in (
            "id", "object_type", "object_id", "action", "actor", "created_at",
        )} | {"changes": changes, "restorable": row["after_json"] is not None})
    return result


def restore_config(
    store: Store, box: SecretBox, kind: str, object_id: int, revision_id: int,
) -> bool:
    """恢复仍存在对象的内容；调用既有保护规则，删除与模型启用状态不回滚。"""

    with store.connection() as db:
        revision = db.execute(
            """SELECT after_json FROM config_revisions
            WHERE id=? AND object_type=? AND object_id=?""",
            (revision_id, kind, object_id),
        ).fetchone()
    if revision is None or revision[0] is None:
        raise ValueError("版本不存在或没有可恢复内容")
    values = json.loads(revision[0])
    for field in SECRET_FIELDS & values.keys():
        if values[field]:
            box.decrypt(values[field])
    if kind == "repository":
        if values.get("feishu_target_id") and not store.get_notification_target(
            values["feishu_target_id"]
        ):
            raise ValueError("历史飞书配置已删除")
        return store.update_repository(object_id, values)
    if kind == "notification_target":
        return store.update_notification_target(object_id, values)
    values.pop("enabled", None)
    # 旧版本创建于单价字段引入之前，恢复它应清除后续填入的单价。
    for field in PRICE_FIELDS:
        values.setdefault(field, "CNY" if field == "price_currency" else None)
    return store.update_model_profile(object_id, values)
