"""管理 SQLite 迁移、事件收件箱、逐提交队列与通知状态。"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 13
SCHEMA = """
CREATE TABLE IF NOT EXISTS repositories (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  gitlab_url TEXT NOT NULL,
  project_id INTEGER NOT NULL,
  remote_url TEXT NOT NULL,
  target_branch TEXT NOT NULL,
  auth_kind TEXT NOT NULL CHECK (auth_kind IN ('signing', 'secret')),
  webhook_secret TEXT NOT NULL,
  feishu_webhook TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(gitlab_url, project_id, target_branch)
);
CREATE TABLE IF NOT EXISTS merge_events (
  id INTEGER PRIMARY KEY,
  repository_id INTEGER NOT NULL REFERENCES repositories(id),
  mr_iid INTEGER NOT NULL,
  delivery_id TEXT,
  merge_sha TEXT,
  squash_sha TEXT,
  status TEXT NOT NULL DEFAULT 'queued',
  error TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(repository_id, mr_iid),
  UNIQUE(repository_id, delivery_id)
);
CREATE TABLE IF NOT EXISTS review_jobs (
  id INTEGER PRIMARY KEY,
  repository_id INTEGER NOT NULL REFERENCES repositories(id),
  event_id INTEGER NOT NULL REFERENCES merge_events(id),
  mr_iid INTEGER NOT NULL,
  commit_sha TEXT NOT NULL,
  ordinal INTEGER NOT NULL,
  config_hash TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued',
  result_path TEXT,
  result_json TEXT,
  error TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  next_run_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TEXT,
  UNIQUE(repository_id, mr_iid, commit_sha, config_hash)
);
CREATE TABLE IF NOT EXISTS notification_deliveries (
  id INTEGER PRIMARY KEY,
  job_id INTEGER NOT NULL UNIQUE REFERENCES review_jobs(id),
  status TEXT NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0,
  next_run_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  error TEXT,
  sent_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_queue ON merge_events(status, id);
CREATE INDEX IF NOT EXISTS idx_jobs_queue ON review_jobs(status, next_run_at, id);
CREATE INDEX IF NOT EXISTS idx_deliveries_queue ON notification_deliveries(status, next_run_at, id);
"""
SCHEMA_V2 = """
ALTER TABLE merge_events ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE merge_events ADD COLUMN next_run_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP;
CREATE TABLE model_profile (
  id INTEGER PRIMARY KEY CHECK (id=1),
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  api_key_ciphertext TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE review_attempts (
  id INTEGER PRIMARY KEY,
  job_id INTEGER NOT NULL REFERENCES review_jobs(id),
  attempt_number INTEGER NOT NULL,
  status TEXT NOT NULL,
  result_path TEXT,
  error TEXT,
  finished_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(job_id, attempt_number)
);
CREATE INDEX idx_events_ready ON merge_events(status, next_run_at, id);
"""
SCHEMA_V3 = """
ALTER TABLE review_jobs ADD COLUMN retry_start_attempts INTEGER NOT NULL DEFAULT 0;
"""
SCHEMA_V4 = """
ALTER TABLE repositories ADD COLUMN webhook_id TEXT;
ALTER TABLE repositories ADD COLUMN last_webhook_at TEXT;
"""
SCHEMA_V5 = """
CREATE TABLE audit_log (
  id INTEGER PRIMARY KEY,
  action TEXT NOT NULL,
  object_type TEXT NOT NULL,
  object_id INTEGER,
  outcome TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_audit_recent ON audit_log(id DESC);
"""
SCHEMA_V6 = """
CREATE TABLE connection_checks (
  id INTEGER PRIMARY KEY,
  kind TEXT NOT NULL CHECK (kind IN ('git', 'gitlab', 'model', 'feishu')),
  repository_id INTEGER REFERENCES repositories(id),
  status TEXT NOT NULL DEFAULT 'queued'
    CHECK (status IN ('queued', 'running', 'passed', 'failed')),
  error TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TEXT,
  CHECK ((kind='model' AND repository_id IS NULL)
    OR (kind!='model' AND repository_id IS NOT NULL))
);
CREATE UNIQUE INDEX idx_connection_checks_active
ON connection_checks(kind, COALESCE(repository_id, 0))
WHERE status IN ('queued', 'running');
CREATE INDEX idx_connection_checks_queue ON connection_checks(status, id);
"""
SCHEMA_V7 = """
ALTER TABLE review_jobs ADD COLUMN rule_digest TEXT NOT NULL DEFAULT '';
"""
SCHEMA_V8 = """
CREATE TABLE notification_targets (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  webhook_ciphertext TEXT NOT NULL,
  signing_secret_ciphertext TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE repositories ADD COLUMN feishu_target_id INTEGER
  REFERENCES notification_targets(id) ON DELETE SET NULL;
CREATE INDEX idx_repositories_feishu_target ON repositories(feishu_target_id);
INSERT INTO notification_targets(id, name, webhook_ciphertext)
SELECT id, name || ' 通知', feishu_webhook FROM repositories WHERE feishu_webhook != '';
UPDATE repositories SET feishu_target_id=id, feishu_webhook=''
WHERE feishu_webhook != '';
"""
SCHEMA_V9 = """
ALTER TABLE repositories ADD COLUMN path_with_namespace TEXT NOT NULL DEFAULT '';
ALTER TABLE repositories ADD COLUMN gitlab_token_ciphertext TEXT NOT NULL DEFAULT '';
ALTER TABLE repositories ADD COLUMN enable_merge_requests INTEGER NOT NULL DEFAULT 1;
ALTER TABLE repositories ADD COLUMN enable_default_branch_pushes INTEGER NOT NULL DEFAULT 0;
"""
SCHEMA_V10 = """
CREATE TABLE model_profiles (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  base_url TEXT NOT NULL DEFAULT '',
  api_key_ciphertext TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 0,
  version INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX idx_model_profiles_enabled ON model_profiles(enabled) WHERE enabled=1;
INSERT INTO model_profiles(id, name, provider, model, api_key_ciphertext, enabled, version)
SELECT id, '原有模型', provider, model, api_key_ciphertext, 1, version FROM model_profile;
"""
SCHEMA_V11 = """
CREATE TABLE review_rule_configs (
  id INTEGER PRIMARY KEY,
  repository_id INTEGER UNIQUE REFERENCES repositories(id) ON DELETE CASCADE,
  content TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX idx_review_rule_global ON review_rule_configs((1))
WHERE repository_id IS NULL;
"""
SCHEMA_V12 = """
CREATE TABLE review_rule_revisions (
  id INTEGER PRIMARY KEY,
  repository_id INTEGER REFERENCES repositories(id) ON DELETE CASCADE,
  content TEXT,
  action TEXT NOT NULL CHECK (action IN ('saved', 'deleted', 'restored')),
  restored_from INTEGER,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_review_rule_revisions_scope
ON review_rule_revisions(repository_id, id DESC);
INSERT INTO review_rule_revisions(repository_id, content, action)
SELECT repository_id, content, 'saved' FROM review_rule_configs;
"""
SCHEMA_V13 = """
CREATE TABLE rule_previews (
  id INTEGER PRIMARY KEY,
  repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
  file_path TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued'
    CHECK (status IN ('queued', 'running', 'passed', 'failed')),
  commit_sha TEXT,
  output TEXT,
  error TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TEXT
);
CREATE INDEX idx_rule_previews_queue ON rule_previews(status, id);
"""


class Store:
    """提供短事务数据操作；外部调用必须在事务结束后执行。"""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """为每次操作建立独立连接，并保证异常时回滚与关闭。"""

        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def migrate(self) -> None:
        """仅执行已知版本迁移，拒绝打开更新版本的数据库。"""

        with self.connection() as db:
            version = int(db.execute("PRAGMA user_version").fetchone()[0])
            if version > SCHEMA_VERSION:
                raise RuntimeError("数据库版本高于当前程序")
            migrations = (
                (1, SCHEMA),
                (2, SCHEMA_V2),
                (3, SCHEMA_V3),
                (4, SCHEMA_V4),
                (5, SCHEMA_V5),
                (6, SCHEMA_V6),
                (7, SCHEMA_V7),
                (8, SCHEMA_V8),
                (9, SCHEMA_V9),
                (10, SCHEMA_V10),
                (11, SCHEMA_V11),
                (12, SCHEMA_V12),
                (13, SCHEMA_V13),
            )
            for target_version, script in migrations:
                if version >= target_version:
                    continue
                # executescript 会先提交现有事务，因此每版显式包住 DDL 与版本号。
                # 任一步失败都由外层 connection 上下文回滚该版本，避免半成品 schema。
                db.executescript(
                    f"BEGIN IMMEDIATE;\n{script}\nPRAGMA user_version={target_version};\nCOMMIT;"
                )

    def enqueue_connection_check(self, kind: str, repository_id: int | None) -> int | None:
        """诊断请求先持久化；同一目标只允许一个未完成检查。"""

        with self.connection() as db:
            cursor = db.execute(
                """INSERT OR IGNORE INTO connection_checks(kind, repository_id)
                VALUES (?, ?)""",
                (kind, repository_id),
            )
            return cursor.lastrowid if cursor.rowcount else None

    def list_connection_checks(self) -> list[dict[str, Any]]:
        """仅返回诊断状态和脱敏错误，不向管理页传输凭据。"""

        with self.connection() as db:
            return [
                dict(row)
                for row in db.execute("SELECT * FROM connection_checks ORDER BY id DESC LIMIT 100")
            ]

    def next_connection_check(self) -> dict[str, Any] | None:
        """领取一个诊断任务；外部调用在事务结束后执行。"""

        with self.connection() as db:
            row = db.execute(
                "SELECT * FROM connection_checks WHERE status='queued' ORDER BY id LIMIT 1"
            ).fetchone()
            if row:
                db.execute("UPDATE connection_checks SET status='running' WHERE id=?", (row["id"],))
            return dict(row) if row else None

    def finish_connection_check(self, check_id: int, error: str | None) -> None:
        """只保存可展示的错误摘要；诊断不自动重试以免重复发测试消息。"""

        with self.connection() as db:
            db.execute(
                """UPDATE connection_checks SET status=?, error=?,
                finished_at=CURRENT_TIMESTAMP WHERE id=? AND status='running'""",
                ("failed" if error else "passed", error, check_id),
            )

    def record_audit(
        self, action: str, object_type: str, object_id: int | None, outcome: str
    ) -> None:
        """仅记录操作元数据，绝不保存请求体、令牌或外部服务响应。"""

        with self.connection() as db:
            db.execute(
                """INSERT INTO audit_log(action, object_type, object_id, outcome)
                VALUES (?, ?, ?, ?)""",
                (action, object_type, object_id, outcome),
            )

    def list_audit(self) -> list[dict[str, Any]]:
        """返回最近的管理动作供操作追溯。"""

        with self.connection() as db:
            return [
                dict(row)
                for row in db.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 100")
            ]

    def add_repository(self, values: dict[str, Any]) -> int:
        """持久化项目配置；调用方负责在写入前加密凭据。"""

        with self.connection() as db:
            cursor = db.execute(
                """INSERT INTO repositories
                (name, gitlab_url, project_id, remote_url, target_branch,
                 auth_kind, webhook_secret, feishu_webhook, feishu_target_id,
                 path_with_namespace, gitlab_token_ciphertext,
                 enable_merge_requests, enable_default_branch_pushes)
                VALUES (:name, :gitlab_url, :project_id, :remote_url,
                        :target_branch, :auth_kind, :webhook_secret,
                        :feishu_webhook, :feishu_target_id,
                        :path_with_namespace, :gitlab_token_ciphertext,
                        :enable_merge_requests, :enable_default_branch_pushes)""",
                values
                | {
                    "feishu_target_id": values.get("feishu_target_id"),
                    "path_with_namespace": values.get("path_with_namespace", ""),
                    "gitlab_token_ciphertext": values.get("gitlab_token_ciphertext", ""),
                    "enable_merge_requests": values.get("enable_merge_requests", True),
                    "enable_default_branch_pushes": values.get(
                        "enable_default_branch_pushes", False
                    ),
                },
            )
            if cursor.lastrowid is None:
                raise RuntimeError("仓库写入后未返回 ID")
            return cursor.lastrowid

    def get_repository(self, repository_id: int) -> dict[str, Any] | None:
        """读取仓库配置供内部验证与 Worker 使用。"""

        with self.connection() as db:
            row = db.execute("SELECT * FROM repositories WHERE id=?", (repository_id,)).fetchone()
            return dict(row) if row else None

    def list_repositories(self) -> list[dict[str, Any]]:
        """列出仓库配置；对外响应必须额外移除密文字段。"""

        with self.connection() as db:
            return [dict(row) for row in db.execute("SELECT * FROM repositories ORDER BY id")]

    def list_review_rules(self) -> list[dict[str, Any]]:
        """返回全局与项目规则，供管理台展示当前可编辑版本。"""

        with self.connection() as db:
            return [
                dict(row)
                for row in db.execute(
                    """SELECT repository_id, content, updated_at
                    FROM review_rule_configs ORDER BY repository_id"""
                )
            ]

    def get_review_rule(self, repository_id: int | None) -> str | None:
        """管理规则可覆盖某个项目，也可作为所有项目的全局兜底。"""

        with self.connection() as db:
            row = db.execute(
                "SELECT content FROM review_rule_configs WHERE repository_id IS ?",
                (repository_id,),
            ).fetchone()
            return str(row["content"]) if row else None

    def list_review_rule_revisions(self, repository_id: int | None) -> list[dict[str, Any]]:
        """按范围列出最近版本；正文用于管理员核对和回滚。"""

        with self.connection() as db:
            return [
                dict(row)
                for row in db.execute(
                    """SELECT id, repository_id, content, action, restored_from, created_at
                    FROM review_rule_revisions WHERE repository_id IS ?
                    ORDER BY id DESC LIMIT 50""",
                    (repository_id,),
                )
            ]

    def enqueue_rule_preview(self, repository_id: int, file_path: str) -> int:
        """规则预览先入库；Worker 再访问 Git 与 OCR，避免 HTTP 请求被长任务占用。"""

        with self.connection() as db:
            cursor = db.execute(
                "INSERT INTO rule_previews(repository_id, file_path) VALUES (?, ?)",
                (repository_id, file_path),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("规则预览入队失败")
            # 仅清理已结束的旧诊断；排队和运行记录始终保留到 Worker 确认末态。
            db.execute(
                """DELETE FROM rule_previews WHERE repository_id=?
                AND status IN ('passed', 'failed') AND id NOT IN (
                    SELECT id FROM rule_previews WHERE repository_id=?
                    ORDER BY id DESC LIMIT 100
                )""",
                (repository_id, repository_id),
            )
            return cursor.lastrowid

    def list_rule_previews(self, repository_id: int) -> list[dict[str, Any]]:
        """只展示项目最近的预览结果，命中规则文本不写入审计日志。"""

        with self.connection() as db:
            return [
                dict(row) for row in db.execute(
                    """SELECT * FROM rule_previews WHERE repository_id=?
                    ORDER BY id DESC LIMIT 20""",
                    (repository_id,),
                )
            ]

    def next_rule_preview(self) -> dict[str, Any] | None:
        """单 Worker 领取最早的预览，外部操作在事务结束后执行。"""

        with self.connection() as db:
            row = db.execute(
                "SELECT * FROM rule_previews WHERE status='queued' ORDER BY id LIMIT 1"
            ).fetchone()
            if row:
                db.execute("UPDATE rule_previews SET status='running' WHERE id=?", (row["id"],))
            return dict(row) if row else None

    def finish_rule_preview(
        self, preview_id: int, commit_sha: str | None,
        output: str | None, error: str | None,
    ) -> None:
        """结果与提交 SHA 一起落库；删除项目后迟到结果不得重建记录。"""

        with self.connection() as db:
            db.execute(
                """UPDATE rule_previews SET status=?, commit_sha=?, output=?, error=?,
                finished_at=CURRENT_TIMESTAMP WHERE id=? AND status='running'""",
                ("failed" if error else "passed", commit_sha, output, error, preview_id),
            )

    def _write_review_rule(
        self, db: sqlite3.Connection, repository_id: int | None,
        content: str | None, restored_from: int | None = None,
    ) -> bool:
        """在调用方事务内核对活动任务并保存当前配置与历史版本。"""

        if repository_id is not None and db.execute(
            "SELECT 1 FROM repositories WHERE id=?", (repository_id,)
        ).fetchone() is None:
            raise LookupError("仓库不存在")
        active = db.execute(
            """SELECT 1 FROM review_jobs WHERE status IN ('queued','running')
            AND (? IS NULL OR repository_id=?) LIMIT 1""",
            (repository_id, repository_id),
        ).fetchone()
        if active:
            raise ValueError("有待处理评审任务，请完成后再修改审核规则")
        current = db.execute(
            "SELECT id, content FROM review_rule_configs WHERE repository_id IS ?",
            (repository_id,),
        ).fetchone()
        if content is None and current is None:
            return False
        if current is not None and content == current["content"] and restored_from is None:
            return True
        if content is None:
            db.execute("DELETE FROM review_rule_configs WHERE id=?", (current["id"],))
        elif current:
            db.execute(
                """UPDATE review_rule_configs SET content=?,
                updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                (content, current["id"]),
            )
        else:
            db.execute(
                "INSERT INTO review_rule_configs(repository_id, content) VALUES (?, ?)",
                (repository_id, content),
            )
        db.execute(
            """INSERT INTO review_rule_revisions(repository_id, content, action, restored_from)
            VALUES (?, ?, ?, ?)""",
            (repository_id, content, "restored" if restored_from else
             "saved" if content is not None else "deleted", restored_from),
        )
        return True

    def change_review_rule(self, repository_id: int | None, content: str | None) -> bool:
        """在写锁内阻止修改运行中或排队任务使用的规则。"""

        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            return self._write_review_rule(db, repository_id, content)

    def restore_review_rule(self, repository_id: int | None, revision_id: int) -> bool:
        """同一写事务内读取目标版本并恢复，防止并发配置变更越过队列保护。"""

        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            revision = db.execute(
                """SELECT content FROM review_rule_revisions
                WHERE id=? AND repository_id IS ?""",
                (revision_id, repository_id),
            ).fetchone()
            if revision is None:
                raise LookupError("审核规则版本不存在")
            return self._write_review_rule(db, repository_id, revision["content"], revision_id)

    def update_repository(self, repository_id: int, values: dict[str, Any]) -> bool:
        """项目身份有历史后冻结；来源变化必须等待当前事件和评审结束。"""

        allowed = {
            "name",
            "gitlab_url",
            "project_id",
            "remote_url",
            "path_with_namespace",
            "target_branch",
            "enabled",
            "auth_kind",
            "webhook_secret",
            "feishu_webhook",
            "feishu_target_id",
            "webhook_id",
            "gitlab_token_ciphertext",
            "enable_merge_requests",
            "enable_default_branch_pushes",
        }
        if not values or not values.keys() <= allowed:
            raise ValueError("仓库更新字段无效")
        assignments = ", ".join(f"{field}=?" for field in values)
        with self.connection() as db:
            source_fields = {
                "gitlab_url",
                "project_id",
                "remote_url",
                "path_with_namespace",
                "target_branch",
            }
            if source_fields & values.keys():
                # 先取得写锁，防止检查队列状态与更新来源之间插入 Webhook 事件。
                db.execute("BEGIN IMMEDIATE")
                current = db.execute(
                    """SELECT gitlab_url, project_id, remote_url, path_with_namespace,
                    target_branch, last_webhook_at FROM repositories WHERE id=?""",
                    (repository_id,),
                ).fetchone()
                if current:
                    changed = {
                        key for key in source_fields & values.keys() if values[key] != current[key]
                    }
                    if changed & {"gitlab_url", "project_id"}:
                        has_event = db.execute(
                            "SELECT 1 FROM merge_events WHERE repository_id=? LIMIT 1",
                            (repository_id,),
                        ).fetchone()
                        if current["last_webhook_at"] or has_event:
                            raise ValueError(
                                "已有 Webhook 投递或评审事件，不能修改 GitLab 项目身份"
                            )
                    if changed:
                        active_event = db.execute(
                            """SELECT 1 FROM merge_events WHERE repository_id=?
                            AND status IN ('queued','running') LIMIT 1""",
                            (repository_id,),
                        ).fetchone()
                        active_job = db.execute(
                            """SELECT 1 FROM review_jobs WHERE repository_id=?
                            AND status IN ('queued','running') LIMIT 1""",
                            (repository_id,),
                        ).fetchone()
                        if active_event or active_job:
                            raise ValueError("有待处理事件或评审任务，请完成后再修改仓库来源或分支")
            cursor = db.execute(
                f"UPDATE repositories SET {assignments} WHERE id=?",
                (*values.values(), repository_id),
            )
            return cursor.rowcount == 1

    def clear_feishu_webhook(self, repository_id: int) -> bool:
        """解除仓库与通知通道的关联，保留共享通道及评审历史。"""

        with self.connection() as db:
            cursor = db.execute(
                "UPDATE repositories SET feishu_webhook='', feishu_target_id=NULL WHERE id=?",
                (repository_id,),
            )
            return cursor.rowcount == 1

    def add_notification_target(self, name: str, webhook: str, signing_secret: str) -> int:
        """通知凭据只存密文；仓库通过外键共享同一目标。"""

        with self.connection() as db:
            cursor = db.execute(
                """INSERT INTO notification_targets
                (name, webhook_ciphertext, signing_secret_ciphertext) VALUES (?, ?, ?)""",
                (name, webhook, signing_secret),
            )
            assert cursor.lastrowid is not None
            return cursor.lastrowid

    def get_notification_target(self, target_id: int) -> dict[str, Any] | None:
        with self.connection() as db:
            row = db.execute(
                "SELECT * FROM notification_targets WHERE id=?", (target_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_notification_targets(self) -> list[dict[str, Any]]:
        with self.connection() as db:
            return [
                dict(row)
                for row in db.execute(
                    """SELECT t.*, COUNT(r.id) AS repository_count
                    FROM notification_targets t LEFT JOIN repositories r
                    ON r.feishu_target_id=t.id GROUP BY t.id ORDER BY t.id"""
                )
            ]

    def update_notification_target(self, target_id: int, values: dict[str, str]) -> bool:
        allowed = {"name", "webhook_ciphertext", "signing_secret_ciphertext"}
        if not values or not values.keys() <= allowed:
            raise ValueError("飞书配置更新字段无效")
        assignments = ", ".join(f"{field}=?" for field in values)
        with self.connection() as db:
            cursor = db.execute(
                f"UPDATE notification_targets SET {assignments}, "
                "updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (*values.values(), target_id),
            )
            return cursor.rowcount == 1

    def delete_notification_target(self, target_id: int) -> bool:
        """删除共享通道时外键将所有关联仓库置为未配置。"""

        with self.connection() as db:
            cursor = db.execute("DELETE FROM notification_targets WHERE id=?", (target_id,))
            return cursor.rowcount == 1

    def delete_repository(self, repository_id: int) -> bool:
        """删除项目及其关联事件、评审、通知和连接测试记录。"""

        with self.connection() as db:
            db.execute(
                """DELETE FROM notification_deliveries
                WHERE job_id IN (SELECT id FROM review_jobs WHERE repository_id=?)""",
                (repository_id,),
            )
            db.execute(
                """DELETE FROM review_attempts
                WHERE job_id IN (SELECT id FROM review_jobs WHERE repository_id=?)""",
                (repository_id,),
            )
            db.execute("DELETE FROM review_jobs WHERE repository_id=?", (repository_id,))
            db.execute("DELETE FROM merge_events WHERE repository_id=?", (repository_id,))
            db.execute("DELETE FROM connection_checks WHERE repository_id=?", (repository_id,))
            cursor = db.execute("DELETE FROM repositories WHERE id=?", (repository_id,))
            return cursor.rowcount == 1

    def record_webhook(self, repository_id: int) -> None:
        """合法鉴权投递可用于判断 GitLab 回调连接是否仍在工作。"""

        with self.connection() as db:
            db.execute(
                "UPDATE repositories SET last_webhook_at=CURRENT_TIMESTAMP WHERE id=?",
                (repository_id,),
            )

    def add_event(
        self,
        repository_id: int,
        mr_iid: int,
        delivery_id: str | None,
        merge_sha: str | None,
        squash_sha: str | None,
    ) -> bool:
        """以 MR 和投递 ID 双重去重，成功保存才允许向 GitLab 确认。"""

        with self.connection() as db:
            cursor = db.execute(
                """INSERT OR IGNORE INTO merge_events
                (repository_id, mr_iid, delivery_id, merge_sha, squash_sha)
                VALUES (?, ?, ?, ?, ?)""",
                (repository_id, mr_iid, delivery_id, merge_sha, squash_sha),
            )
            return cursor.rowcount == 1

    def add_push_event(
        self, repository_id: int, before_sha: str, after_sha: str, delivery_id: str | None
    ) -> bool:
        """复用事件队列保存 Push；负 IID 仅作内部区分，提交范围以后端 Git 为准。"""

        synthetic_iid = -(int(hashlib.sha256(after_sha.encode()).hexdigest()[:15], 16) + 1)
        with self.connection() as db:
            cursor = db.execute(
                """INSERT OR IGNORE INTO merge_events
                (repository_id, mr_iid, delivery_id, merge_sha, squash_sha)
                VALUES (?, ?, ?, ?, ?)""",
                (repository_id, synthetic_iid, delivery_id, after_sha, before_sha),
            )
            return cursor.rowcount == 1

    def enqueue_mr(self, repository_id: int, mr_iid: int) -> bool:
        """手动补触发已合并 MR；已有异常事件可重新展开，已完成事件不重复建任务。"""

        with self.connection() as db:
            cursor = db.execute(
                """INSERT OR IGNORE INTO merge_events(repository_id, mr_iid)
                VALUES (?, ?)""",
                (repository_id, mr_iid),
            )
            if cursor.rowcount:
                return True
            cursor = db.execute(
                """UPDATE merge_events SET status='queued', error=NULL, attempts=0,
                next_run_at=CURRENT_TIMESTAMP WHERE repository_id=? AND mr_iid=?
                AND status='needs_attention'""",
                (repository_id, mr_iid),
            )
            return cursor.rowcount == 1

    def list_events(self) -> list[dict[str, Any]]:
        """返回近期合并事件及处理状态。"""

        with self.connection() as db:
            return [
                dict(row)
                for row in db.execute("SELECT * FROM merge_events ORDER BY id DESC LIMIT 100")
            ]

    def next_event(self) -> dict[str, Any] | None:
        """领取最早的未展开事件；单 Worker 下状态更新仍需持久化。"""

        with self.connection() as db:
            row = db.execute(
                """SELECT e.* FROM merge_events e
                JOIN repositories r ON r.id=e.repository_id
                WHERE e.status='queued' AND r.enabled=1
                AND e.next_run_at<=CURRENT_TIMESTAMP ORDER BY e.id LIMIT 1"""
            ).fetchone()
            if row:
                db.execute(
                    "UPDATE merge_events SET status='running', attempts=attempts+1 WHERE id=?",
                    (row["id"],),
                )
            return dict(row) if row else None

    def finish_event(
        self,
        event_id: int,
        commits: list[str] | None,
        snapshots: dict[str, tuple[str, str]],
        error: str | None,
    ) -> None:
        """在同一事务写入所有提交任务及事件末态；项目已删除时直接结束。"""

        with self.connection() as db:
            if commits is not None:
                event = db.execute("SELECT * FROM merge_events WHERE id=?", (event_id,)).fetchone()
                if event is None:
                    # 管理员允许随时删除项目，Worker 的在途结果因此可能失去写回目标。
                    return
                for ordinal, commit_sha in enumerate(commits):
                    # 每个提交可能携带不同版本的规则文件，事务内固化各自的评审配置。
                    snapshot_hash, rule_digest = snapshots[commit_sha]
                    db.execute(
                        """INSERT OR IGNORE INTO review_jobs
                        (repository_id, event_id, mr_iid, commit_sha, ordinal,
                         config_hash, rule_digest)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (
                            event["repository_id"],
                            event_id,
                            event["mr_iid"],
                            commit_sha,
                            ordinal,
                            snapshot_hash,
                            rule_digest,
                        ),
                    )
            db.execute(
                "UPDATE merge_events SET status=?, error=? WHERE id=?",
                ("done" if commits is not None else "needs_attention", error, event_id),
            )

    def defer_event(self, event_id: int, error: str) -> None:
        """临时故障有限重试，超过上限后转人工处理。"""

        with self.connection() as db:
            db.execute(
                """UPDATE merge_events
                SET status=CASE WHEN attempts>=3 THEN 'needs_attention' ELSE 'queued' END,
                error=?, next_run_at=datetime('now', '+' || attempts * 20 || ' seconds')
                WHERE id=?""",
                (error[:500], event_id),
            )

    def retry_event(self, event_id: int) -> bool:
        """管理员确认后重置异常事件的自动重试次数。"""

        with self.connection() as db:
            cursor = db.execute(
                """UPDATE merge_events SET status='queued', attempts=0, error=NULL,
                next_run_at=CURRENT_TIMESTAMP WHERE id=? AND status='needs_attention'""",
                (event_id,),
            )
            return cursor.rowcount == 1

    def get_model_profile(self) -> dict[str, Any] | None:
        """内部读取当前启用模型；旧单模型记录在迁移时复制到新配置表。"""

        with self.connection() as db:
            row = db.execute("SELECT * FROM model_profiles WHERE enabled=1").fetchone()
            return dict(row) if row else None

    def list_model_profiles(self) -> list[dict[str, Any]]:
        with self.connection() as db:
            return [dict(row) for row in db.execute("SELECT * FROM model_profiles ORDER BY id")]

    def add_model_profile(
        self, name: str, provider: str, model: str, base_url: str, ciphertext: str
    ) -> int:
        """新增模型不影响运行任务；明确启用后才参与新任务快照。"""

        with self.connection() as db:
            cursor = db.execute(
                """INSERT INTO model_profiles(name, provider, model, base_url, api_key_ciphertext)
                VALUES (?, ?, ?, ?, ?)""",
                (name, provider, model, base_url, ciphertext),
            )
            assert cursor.lastrowid is not None
            return cursor.lastrowid

    def activate_model_profile(self, profile_id: int) -> bool:
        """模型切换在单个事务中完成，排队任务仍受配置快照保护。"""

        with self.connection() as db:
            existing = db.execute(
                "SELECT id FROM model_profiles WHERE id=?", (profile_id,)
            ).fetchone()
            if existing is None:
                return False
            active = db.execute("SELECT id FROM model_profiles WHERE enabled=1").fetchone()
            if active and active["id"] == profile_id:
                return True
            busy = db.execute(
                """SELECT EXISTS(SELECT 1 FROM merge_events WHERE status IN ('queued','running'))
                OR EXISTS(SELECT 1 FROM review_jobs WHERE status IN ('queued','running'))"""
            ).fetchone()[0]
            # 尚无启用模型时，积压事件需要允许首次启用才能继续处理。
            if busy and active:
                raise ValueError("队列运行期间不能更换全局模型配置")
            db.execute("UPDATE model_profiles SET enabled=0 WHERE enabled=1")
            db.execute(
                "UPDATE model_profiles SET enabled=1, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (profile_id,),
            )
            return True

    def update_model_profile(self, profile_id: int, values: dict[str, str]) -> bool:
        """修改启用模型前确认队列空闲；版本递增使旧评审快照失效。"""

        allowed = {"name", "provider", "model", "base_url", "api_key_ciphertext"}
        if not values or not values.keys() <= allowed:
            raise ValueError("模型更新字段无效")
        assignments = ", ".join(f"{field}=?" for field in values)
        with self.connection() as db:
            profile = db.execute(
                "SELECT enabled FROM model_profiles WHERE id=?", (profile_id,)
            ).fetchone()
            if profile is None:
                return False
            if profile["enabled"]:
                busy = db.execute(
                    """SELECT EXISTS(SELECT 1 FROM merge_events
                    WHERE status IN ('queued','running'))
                    OR EXISTS(SELECT 1 FROM review_jobs
                    WHERE status IN ('queued','running'))"""
                ).fetchone()[0]
                if busy:
                    raise ValueError("队列运行期间不能修改启用的模型配置")
            db.execute(
                f"UPDATE model_profiles SET {assignments}, version=version+1, "
                "updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (*values.values(), profile_id),
            )
            return True

    def delete_model_profile(self, profile_id: int) -> bool:
        """不允许删除正在使用的模型，防止后续任务落回环境默认值。"""

        with self.connection() as db:
            row = db.execute(
                "SELECT enabled FROM model_profiles WHERE id=?", (profile_id,)
            ).fetchone()
            if row is None:
                return False
            if row["enabled"]:
                raise ValueError("请先启用其他模型")
            db.execute("DELETE FROM model_profiles WHERE id=?", (profile_id,))
            return True

    def next_job(self, last_repository_id: int | None = None) -> dict[str, Any] | None:
        """同一 MR 保持顺序，不同仓库优先轮转领取。"""

        with self.connection() as db:
            row = db.execute(
                """SELECT j.* FROM review_jobs j
                JOIN repositories r ON r.id=j.repository_id
                WHERE j.status='queued' AND r.enabled=1
                AND j.next_run_at<=CURRENT_TIMESTAMP
                AND NOT EXISTS (
                  SELECT 1 FROM merge_events earlier
                  WHERE earlier.repository_id=j.repository_id AND earlier.id<j.event_id
                  AND earlier.status IN ('queued','running')
                )
                AND NOT EXISTS (
                  SELECT 1 FROM review_jobs earlier_job
                  WHERE earlier_job.repository_id=j.repository_id
                  AND earlier_job.event_id<j.event_id
                  AND earlier_job.status IN ('queued','running')
                )
                AND NOT EXISTS (
                  SELECT 1 FROM review_jobs previous
                  WHERE previous.event_id=j.event_id AND previous.ordinal<j.ordinal
                  AND previous.status IN ('queued','running')
                ) ORDER BY CASE WHEN j.repository_id=? THEN 1 ELSE 0 END, j.id LIMIT 1""",
                (last_repository_id,),
            ).fetchone()
            if row:
                db.execute(
                    "UPDATE review_jobs SET status='running', attempts=attempts+1 WHERE id=?",
                    (row["id"],),
                )
            return dict(row) if row else None

    def finish_job(
        self,
        job_id: int,
        status: str,
        result_path: str | None,
        result: dict[str, Any] | None,
        error: str | None,
    ) -> None:
        """保存评审结论并原子创建独立飞书投递任务；已删除任务不再写回。"""

        # 原始 OCR JSON 留在受控工件；索引库和其备份只保存页面与通知必需的字段。
        projection = (
            {
                "comments": [
                    {
                        key: comment[key]
                        for key in (
                            "path",
                            "content",
                            "start_line",
                            "end_line",
                            "severity",
                            "category",
                        )
                        if key in comment
                    }
                    for comment in result.get("comments", [])
                    if isinstance(comment, dict)
                ],
                "manifest": {
                    "terminal_state": result["manifest"].get("terminal_state"),
                    "coverage": result["manifest"].get("coverage"),
                }
                if isinstance(result.get("manifest"), dict)
                else None,
                "summary": {"budget_exceeded": result["summary"].get("budget_exceeded") is True}
                if isinstance(result.get("summary"), dict)
                else None,
                "preview": result.get("preview"),
                "message": result.get("message"),
                "source": result.get("source"),
            }
            if result is not None
            else None
        )
        with self.connection() as db:
            job = db.execute(
                "SELECT attempts, retry_start_attempts FROM review_jobs WHERE id=?", (job_id,)
            ).fetchone()
            if job is None:
                # 项目删除会级联移除任务，在途 OCR 完成后无需恢复已删除的业务记录。
                return
            db.execute(
                """UPDATE review_jobs SET status=?, result_path=?, result_json=?, error=?,
                finished_at=CURRENT_TIMESTAMP WHERE id=?""",
                (
                    status,
                    result_path,
                    json.dumps(projection, ensure_ascii=False) if projection is not None else None,
                    error,
                    job_id,
                ),
            )
            db.execute(
                "INSERT OR IGNORE INTO notification_deliveries(job_id) VALUES (?)", (job_id,)
            )
            db.execute(
                """INSERT INTO review_attempts
                (job_id, attempt_number, status, result_path, error) VALUES (?, ?, ?, ?, ?)""",
                (job_id, job["attempts"], status, result_path, error),
            )

    def defer_job(self, job_id: int, error: str) -> None:
        """临时失败有限退避；项目已删除时不再重新建立任务。"""

        with self.connection() as db:
            job = db.execute(
                "SELECT attempts, retry_start_attempts FROM review_jobs WHERE id=?", (job_id,)
            ).fetchone()
            if job is None:
                return
            attempts = int(job["attempts"])
            final = attempts - int(job["retry_start_attempts"]) >= 3
            db.execute(
                """UPDATE review_jobs SET status=?, error=?,
                next_run_at=datetime('now', '+' || min(300,
                  (attempts - retry_start_attempts) *
                  (attempts - retry_start_attempts) * 20) || ' seconds'),
                finished_at=CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE NULL END WHERE id=?""",
                ("failed" if final else "queued", error[:500], final, job_id),
            )
            db.execute(
                """INSERT INTO review_attempts
                (job_id, attempt_number, status, error) VALUES (?, ?, 'failed', ?)""",
                (job_id, attempts, error[:500]),
            )
            if final:
                db.execute(
                    "INSERT OR IGNORE INTO notification_deliveries(job_id) VALUES (?)", (job_id,)
                )

    def list_jobs(self) -> list[dict[str, Any]]:
        """返回任务列表，避免在列表接口传输完整 OCR 结果。"""

        with self.connection() as db:
            return [
                dict(row)
                for row in db.execute(
                    """SELECT id, repository_id, event_id, mr_iid, commit_sha, ordinal,
                status, error, attempts, created_at, finished_at FROM review_jobs
                ORDER BY id DESC LIMIT 200"""
                )
            ]

    def get_job_rule_digest(self, job_id: int) -> str | None:
        """重审只需要原提交的规则摘要，不读取可能很大的 OCR 原始结果。"""

        with self.connection() as db:
            row = db.execute("SELECT rule_digest FROM review_jobs WHERE id=?", (job_id,)).fetchone()
            return str(row["rule_digest"]) if row else None

    def get_job(self, job_id: int) -> dict[str, Any] | None:
        """读取单任务和机器可读结果供管理页展示。"""

        with self.connection() as db:
            row = db.execute("SELECT * FROM review_jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                return None
            result = dict(row)
            raw_result = result.pop("result_json")
            if raw_result:
                # 原始工件可能包含模型推理内容，管理 API 只提供页面必需的投影。
                parsed = json.loads(raw_result)
                manifest = parsed.get("manifest")
                comments = parsed.get("comments")
                result["result"] = {
                    "comments": [
                        {
                            key: comment[key]
                            for key in (
                                "path",
                                "content",
                                "start_line",
                                "end_line",
                                "severity",
                                "category",
                            )
                            if key in comment
                        }
                        for comment in comments
                        if isinstance(comment, dict)
                    ]
                    if isinstance(comments, list)
                    else [],
                    "manifest": {
                        "terminal_state": manifest.get("terminal_state"),
                        "coverage": manifest.get("coverage"),
                    }
                    if isinstance(manifest, dict)
                    else None,
                    "preview": parsed.get("preview"),
                }
            else:
                result["result"] = None
            result["attempt_history"] = [
                dict(attempt)
                for attempt in db.execute(
                    "SELECT * FROM review_attempts WHERE job_id=? ORDER BY id DESC", (job_id,)
                )
            ]
            delivery = db.execute(
                """SELECT id, status, attempts, error, sent_at
                FROM notification_deliveries WHERE job_id=?""",
                (job_id,),
            ).fetchone()
            result["delivery"] = dict(delivery) if delivery else None
            return result

    def retry_job(self, job_id: int, config_hash: str | None = None) -> int | None:
        """同配置保留尝试历史；配置变化则建立新的不可变任务快照。"""

        with self.connection() as db:
            old = db.execute("SELECT * FROM review_jobs WHERE id=?", (job_id,)).fetchone()
            if old is None or old["status"] not in ("complete", "partial", "failed", "skipped"):
                return None
            if config_hash and config_hash != old["config_hash"]:
                cursor = db.execute(
                    """INSERT OR IGNORE INTO review_jobs
                    (repository_id, event_id, mr_iid, commit_sha, ordinal,
                     config_hash, rule_digest)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        old["repository_id"],
                        old["event_id"],
                        old["mr_iid"],
                        old["commit_sha"],
                        old["ordinal"],
                        config_hash,
                        old["rule_digest"],
                    ),
                )
                return cursor.lastrowid if cursor.rowcount else None
            cursor = db.execute(
                """UPDATE review_jobs SET status='queued', error=NULL,
                retry_start_attempts=attempts,
                next_run_at=CURRENT_TIMESTAMP WHERE id=?
                AND status IN ('complete','partial','failed','skipped')""",
                (job_id,),
            )
            if cursor.rowcount:
                # 旧投递不得在重审期间发送，新的评审结论完成后再生成通知。
                db.execute("DELETE FROM notification_deliveries WHERE job_id=?", (job_id,))
            return job_id if cursor.rowcount else None

    def next_delivery(self) -> dict[str, Any] | None:
        """领取待发送通知；评审结果与通知重试相互独立。"""

        with self.connection() as db:
            row = db.execute(
                """SELECT d.*, j.repository_id, j.commit_sha, j.mr_iid, j.status AS review_status,
                j.result_json, j.error AS review_error,
                r.name AS repository_name, r.path_with_namespace, r.target_branch,
                r.gitlab_url, r.remote_url
                FROM notification_deliveries d
                JOIN review_jobs j ON j.id=d.job_id
                JOIN repositories r ON r.id=j.repository_id
                WHERE d.status='pending' AND r.enabled=1
                AND d.next_run_at<=CURRENT_TIMESTAMP
                ORDER BY d.id LIMIT 1"""
            ).fetchone()
            if row:
                db.execute(
                    """UPDATE notification_deliveries
                    SET status='sending', attempts=attempts+1 WHERE id=?""",
                    (row["id"],),
                )
            return dict(row) if row else None

    def finish_delivery(self, delivery_id: int, error: str | None, retryable: bool = True) -> None:
        """暂时失败有限退避，明确拒绝则立即停止自动投递。"""

        with self.connection() as db:
            if error is None:
                db.execute(
                    """UPDATE notification_deliveries SET status='sent', error=NULL,
                    sent_at=CURRENT_TIMESTAMP WHERE id=?""",
                    (delivery_id,),
                )
            else:
                db.execute(
                    """UPDATE notification_deliveries
                    SET status=CASE WHEN ? OR attempts>=5 THEN 'failed' ELSE 'pending' END,
                    error=?,
                    next_run_at=datetime(
                      'now', '+' || min(300, attempts * attempts * 10) || ' seconds'
                    )
                    WHERE id=?""",
                    (not retryable, error[:500], delivery_id),
                )

    def retry_delivery(self, job_id: int) -> bool:
        """仅对已结束评审的投递重新发送，避免读到重审中的旧结果。"""

        with self.connection() as db:
            cursor = db.execute(
                """UPDATE notification_deliveries SET status='pending', attempts=0,
                error=NULL, next_run_at=CURRENT_TIMESTAMP, sent_at=NULL
                WHERE job_id=? AND status IN ('failed', 'sent')
                AND EXISTS (SELECT 1 FROM review_jobs WHERE id=?
                  AND status IN ('complete', 'partial', 'failed', 'skipped'))""",
                (job_id, job_id),
            )
            return cursor.rowcount == 1

    def recover(self) -> None:
        """独占 Worker 重启后记录中断尝试，并按原有限重试上限恢复。"""

        with self.connection() as db:
            db.execute(
                """UPDATE rule_previews SET status='failed',
                error='Worker 中断，预览结果未确认', finished_at=CURRENT_TIMESTAMP
                WHERE status='running'"""
            )
            # 飞书测试消息可能已被接收，重启后只标失败，不自动补发。
            db.execute(
                """UPDATE connection_checks SET status='failed',
                error='Worker 中断，测试结果未确认', finished_at=CURRENT_TIMESTAMP
                WHERE status='running'"""
            )
            db.execute(
                """UPDATE merge_events SET
                status=CASE WHEN attempts>=3 THEN 'needs_attention' ELSE 'queued' END,
                error='Worker 中断，事件处理未确认', next_run_at=CURRENT_TIMESTAMP
                WHERE status='running'"""
            )
            running = db.execute(
                """SELECT id, attempts, retry_start_attempts
                FROM review_jobs WHERE status='running'"""
            ).fetchall()
            for job in running:
                final = job["attempts"] - job["retry_start_attempts"] >= 3
                db.execute(
                    """INSERT OR IGNORE INTO review_attempts
                    (job_id, attempt_number, status, error)
                    VALUES (?, ?, 'failed', 'Worker 中断，评审结果未确认')""",
                    (job["id"], job["attempts"]),
                )
                db.execute(
                    """UPDATE review_jobs SET status=?, error='Worker 中断，评审结果未确认',
                    next_run_at=CURRENT_TIMESTAMP,
                    finished_at=CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE NULL END
                    WHERE id=?""",
                    ("failed" if final else "queued", final, job["id"]),
                )
                if final:
                    db.execute(
                        "INSERT OR IGNORE INTO notification_deliveries(job_id) VALUES (?)",
                        (job["id"],),
                    )
            # 响应丢失时飞书可能已收消息；有限重试并在卡片中保留任务 ID 供识别。
            db.execute(
                """UPDATE notification_deliveries SET
                status=CASE WHEN attempts>=5 THEN 'failed' ELSE 'pending' END,
                error='Worker 中断，飞书响应未确认', next_run_at=CURRENT_TIMESTAMP
                WHERE status='sending'"""
            )
