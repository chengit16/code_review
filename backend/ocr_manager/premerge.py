"""合并前 MR 版本队列；旧提交结果只保留历史，不进入当前结论。"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from ocr_manager.storage import Store


PREMERGE_MIGRATION = """
CREATE TABLE premerge_settings (
  repository_id INTEGER PRIMARY KEY REFERENCES repositories(id) ON DELETE CASCADE,
  enabled INTEGER NOT NULL DEFAULT 0 CHECK (enabled IN (0, 1))
);
CREATE TABLE premerge_reviews (
  id INTEGER PRIMARY KEY,
  repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
  mr_iid INTEGER NOT NULL,
  head_sha TEXT NOT NULL,
  base_sha TEXT,
  status TEXT NOT NULL DEFAULT 'queued',
  attempts INTEGER NOT NULL DEFAULT 0,
  next_run_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  result_json TEXT,
  result_path TEXT,
  changed_files TEXT,
  error TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TEXT,
  CHECK (length(head_sha)=40)
);
CREATE INDEX idx_premerge_ready ON premerge_reviews(status, next_run_at, id);
CREATE INDEX idx_premerge_mr ON premerge_reviews(repository_id, mr_iid, id DESC);
"""

SHA = re.compile(r"[0-9a-fA-F]{40}\Z")


def parse_premerge_event(body: bytes, project_id: int, branch: str) -> tuple[int, str] | None:
    """仅从通过项目密钥鉴权的 MR 更新提取版本；Worker 仍须向 GitLab 复核。"""

    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError) as error:
        raise HTTPException(422, "无效的 GitLab JSON") from error
    if not isinstance(payload, dict) or payload.get("object_kind") != "merge_request":
        return None
    attributes, project = payload.get("object_attributes"), payload.get("project")
    if not isinstance(attributes, dict) or not isinstance(project, dict):
        raise HTTPException(422, "GitLab MR 字段缺失")
    if attributes.get("action") not in {"open", "reopen", "update"}:
        return None
    if (type(project.get("id")) is not int or project["id"] != project_id or
        type(attributes.get("target_project_id")) is not int or
        attributes["target_project_id"] != project_id):
        raise HTTPException(403, "GitLab 项目不匹配")
    if attributes.get("target_branch") != branch:
        return None
    iid = attributes.get("iid")
    last_commit = attributes.get("last_commit")
    head = last_commit.get("id") if isinstance(last_commit, dict) else None
    if type(iid) is not int or iid <= 0 or not isinstance(head, str) or not SHA.fullmatch(head):
        raise HTTPException(422, "MR 提交版本无效")
    return iid, head.lower()


def enqueue_premerge(store: Store, repository_id: int, mr_iid: int, head_sha: str) -> bool:
    """新版本入库时立即使旧结果失效；重复投递不会重复调用 OCR。"""

    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        enabled = db.execute("""SELECT s.enabled FROM premerge_settings s
            JOIN repositories r ON r.id=s.repository_id
            WHERE r.id=? AND r.enabled=1""", (repository_id,)).fetchone()
        if enabled is None or not enabled["enabled"]:
            return False
        latest = db.execute("""SELECT head_sha,status FROM premerge_reviews
            WHERE repository_id=? AND mr_iid=? ORDER BY id DESC LIMIT 1""",
            (repository_id, mr_iid)).fetchone()
        if latest and latest["head_sha"] == head_sha and latest["status"] != "superseded":
            return False
        db.execute("""UPDATE premerge_reviews SET status='superseded',
            finished_at=CURRENT_TIMESTAMP WHERE repository_id=? AND mr_iid=?
            AND status!='superseded'""", (repository_id, mr_iid))
        db.execute("""INSERT INTO premerge_reviews(repository_id,mr_iid,head_sha)
            VALUES(?,?,?)""", (repository_id, mr_iid, head_sha))
        return True


def next_premerge(store: Store) -> dict[str, Any] | None:
    """单 Worker 领取开启合并前审查的最新待处理版本。"""

    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("""SELECT p.* FROM premerge_reviews p
            JOIN repositories r ON r.id=p.repository_id
            JOIN premerge_settings s ON s.repository_id=r.id
            WHERE p.status='queued' AND p.next_run_at<=CURRENT_TIMESTAMP
            AND r.enabled=1 AND s.enabled=1 ORDER BY p.id LIMIT 1""").fetchone()
        if row:
            db.execute("""UPDATE premerge_reviews SET status='running',
                attempts=attempts+1 WHERE id=?""", (row["id"],))
        return {**dict(row), "attempts": row["attempts"] + 1} if row else None


def premerge_is_current(store: Store, review_id: int) -> bool:
    """OCR 执行期间也检查版本；Webhook 到达后尽快终止过期运行。"""

    with store.connection() as db:
        row = db.execute("SELECT status FROM premerge_reviews WHERE id=?",
                         (review_id,)).fetchone()
        return row is not None and row["status"] == "running"


def finish_premerge(store: Store, review_id: int, status: str, base_sha: str | None,
                    result: dict[str, Any] | None, result_path: str | None,
                    changed_files: list[dict[str, Any]] | None, error: str | None) -> None:
    """只允许当前运行版本写回；过期 OCR 结果不能复活旧结论。"""

    projection = None
    if result is not None:
        projection = {
            "comments": [{key: item[key] for key in
                          ("path", "content", "start_line", "end_line", "severity", "category")
                          if key in item} for item in result.get("comments", [])
                         if isinstance(item, dict)],
            "manifest": {"terminal_state": result.get("manifest", {}).get("terminal_state"),
                         "coverage": result.get("manifest", {}).get("coverage")},
            "preview": result.get("preview"),
        }
    with store.connection() as db:
        db.execute("""UPDATE premerge_reviews SET status=?,base_sha=?,result_json=?,
            result_path=?,changed_files=?,error=?,finished_at=CURRENT_TIMESTAMP
            WHERE id=? AND status='running'""",
            (status, base_sha, json.dumps(projection, ensure_ascii=False) if projection else None,
             result_path, json.dumps(changed_files) if changed_files is not None else None,
             error, review_id))


class PremergeSetting(BaseModel):
    """项目级合并前审查开关，默认关闭。"""

    model_config = ConfigDict(extra="forbid")
    enabled: bool


def register_premerge(app: FastAPI, store: Store, admin: Any) -> None:
    """管理页查询版本和启停；Webhook 与 OCR 不在管理请求中执行。"""

    @app.get("/api/repositories/{repository_id}/premerge", dependencies=[admin])
    def setting(repository_id: int) -> dict[str, bool]:
        """读取该项目是否审查未合并 MR。"""

        if store.get_repository(repository_id) is None:
            raise HTTPException(404, "项目不存在")
        with store.connection() as db:
            row = db.execute("SELECT enabled FROM premerge_settings WHERE repository_id=?",
                             (repository_id,)).fetchone()
        return {"enabled": bool(row[0]) if row else False}

    @app.put("/api/repositories/{repository_id}/premerge", dependencies=[admin])
    def save_setting(repository_id: int, payload: PremergeSetting) -> dict[str, bool]:
        """关闭只暂停新任务领取；历史版本仍可供管理员核查。"""

        with store.connection() as db:
            if not db.execute("SELECT 1 FROM repositories WHERE id=?",
                              (repository_id,)).fetchone():
                raise HTTPException(404, "项目不存在")
            db.execute("""INSERT INTO premerge_settings(repository_id,enabled) VALUES(?,?)
                ON CONFLICT(repository_id) DO UPDATE SET enabled=excluded.enabled""",
                (repository_id, payload.enabled))
        return {"enabled": payload.enabled}

    @app.get("/api/premerge-reviews", dependencies=[admin])
    def list_reviews(repository_id: int | None = None) -> list[dict[str, Any]]:
        """最多展示最近 100 个版本，旧版本明确标为失效。"""

        with store.connection() as db:
            rows = db.execute("""SELECT p.*,r.name AS repository_name FROM premerge_reviews p
                JOIN repositories r ON r.id=p.repository_id
                WHERE (? IS NULL OR p.repository_id=?) ORDER BY p.id DESC LIMIT 100""",
                (repository_id, repository_id)).fetchall()
        return [dict(row) for row in rows]

    @app.get("/api/premerge-reviews/{review_id}", dependencies=[admin])
    def review_detail(review_id: int) -> dict[str, Any]:
        """详情只暴露安全投影与差异文件，原始模型工件保留在本机。"""

        with store.connection() as db:
            row = db.execute("""SELECT p.*,r.name AS repository_name FROM premerge_reviews p
                JOIN repositories r ON r.id=p.repository_id WHERE p.id=?""",
                (review_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "合并前审查不存在")
        return dict(row)
