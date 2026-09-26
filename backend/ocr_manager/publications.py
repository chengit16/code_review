"""验证 GitLab MR 版本和新增行后投递行内评论；失败只重试发布。"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

import httpx
from cryptography.fernet import InvalidToken
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict
from unidiff import PatchSet
from unidiff.errors import UnidiffParseError

from ocr_manager.config import Settings
from ocr_manager.gitlab import GitLabClient
from ocr_manager.secrets import SecretBox

if TYPE_CHECKING:
    from ocr_manager.storage import Store


def inline_position(mr: dict[str, Any], diffs: list[dict[str, Any]],
                    comment: dict[str, Any]) -> dict[str, str] | None:
    """仅接受 MR 当前 diff 中真实新增行；文件级与旧版本行不伪造位置。"""

    refs = mr.get("diff_refs")
    if not isinstance(refs, dict) or any(not isinstance(refs.get(key), str) or
                                        not re.fullmatch(r"[0-9a-f]{40}", refs[key])
                                        for key in ("base_sha", "start_sha", "head_sha")):
        return None
    path, line = comment.get("path"), comment.get("start_line")
    if not isinstance(path, str) or not isinstance(line, int) or line < 1:
        return None
    for item in diffs:
        if item["new_path"] != path or item.get("too_large") or item.get("collapsed"):
            continue
        old_path = item.get("old_path") or path
        try:
            patch = PatchSet(f"--- a/{old_path}\n+++ b/{path}\n{item['diff']}")
        except (ValueError, UnidiffParseError):
            return None
        if any(part.is_added and part.target_line_no == line
               for file in patch for hunk in file for part in hunk):
            return {"position_type": "text", "base_sha": refs["base_sha"],
                    "start_sha": refs["start_sha"], "head_sha": refs["head_sha"],
                    "old_path": old_path, "new_path": path, "new_line": str(line)}
    return None


def next_publication(store: Store) -> dict[str, Any] | None:
    """只领取项目仍启用发布且任务已完成的待发项。"""

    with store.connection() as db:
        row = db.execute("""SELECT p.*, j.repository_id, j.mr_iid, j.commit_sha,
            j.result_json FROM gitlab_publications p
            JOIN review_jobs j ON j.id=p.job_id
            JOIN gitlab_publication_settings s ON s.repository_id=j.repository_id
            JOIN repositories r ON r.id=j.repository_id
            WHERE p.status='pending' AND p.next_run_at<=CURRENT_TIMESTAMP
            AND s.enabled=1 AND r.enabled=1 AND j.status IN ('complete','partial')
            AND p.attempt_number=j.attempts
            ORDER BY p.id LIMIT 1""").fetchone()
        if row:
            db.execute("UPDATE gitlab_publications SET status='sending', attempts=attempts+1 "
                       "WHERE id=?", (row["id"],))
        return dict(row) if row else None


def finish_publication(store: Store, publication_id: int, status: str,
                       error: str | None = None, discussion_id: str | None = None,
                       retryable: bool = False) -> None:
    """独立记录写回结果，OCR 和飞书状态不受 GitLab 故障影响。"""

    with store.connection() as db:
        db.execute("""UPDATE gitlab_publications SET
            status=CASE WHEN ?='failed' AND ?=1 AND attempts<5 THEN 'pending' ELSE ? END,
            error=?, discussion_id=?,
            sent_at=CASE WHEN ?='sent' THEN CURRENT_TIMESTAMP ELSE NULL END,
            next_run_at=datetime('now',printf('+%d seconds',min(300,attempts*attempts*10)))
            WHERE id=?""", (status, retryable, status, error, discussion_id, status,
                             publication_id))


def publish_one(store: Store, settings: Settings, item: dict[str, Any]) -> None:
    """只向配置身份匹配的已合并 MR 当前 diff 发送定位有效的发现。"""

    try:
        repository = store.get_repository(item["repository_id"])
        if not repository:
            finish_publication(store, item["id"], "failed", "项目已删除")
            return
        token = SecretBox(settings.master_key).decrypt(repository["gitlab_token_ciphertext"])
        gitlab = GitLabClient(repository["gitlab_url"], token)
        mr = gitlab.get_merge_request(repository["project_id"], item["mr_iid"])
        if (mr.get("state") != "merged" or
            mr.get("target_project_id") != repository["project_id"] or
            mr.get("target_branch") != repository["target_branch"]):
            finish_publication(store, item["id"], "failed", "MR 身份或合并状态已变化")
            return
        payload = item["result_json"]
        comments = json.loads(payload).get("comments", []) if payload else []
        if item["comment_index"] >= len(comments):
            finish_publication(store, item["id"], "failed", "发现索引已失效")
            return
        comment = comments[item["comment_index"]]
        position = inline_position(mr, gitlab.list_merge_request_diffs(
            repository["project_id"], item["mr_iid"]), comment)
        if position is None:
            finish_publication(store, item["id"], "skipped", "发现不在 MR 当前新增行")
            return
        marker = (f"<!-- open-code-review:{item['job_id']}:"
                  f"{item['attempt_number']}:{item['comment_index']} -->")
        discussion = gitlab.post_inline_discussion(repository["project_id"], item["mr_iid"],
                                                   str(comment.get("content", ""))[:5000],
                                                   position, marker)
        finish_publication(store, item["id"], "sent", discussion_id=discussion)
    except httpx.HTTPStatusError as error:
        status = error.response.status_code
        finish_publication(store, item["id"], "failed", f"GitLab HTTP {status}",
                           retryable=status == 429 or status >= 500)
    except httpx.RequestError:
        finish_publication(store, item["id"], "failed", "GitLab 网络连接失败", retryable=True)
    except (InvalidToken, ValueError, TypeError, KeyError, UnidiffParseError):
        finish_publication(store, item["id"], "failed", "GitLab 发布配置或 diff 无效")


class PublicationSetting(BaseModel):
    """默认不向 GitLab 写回；启用须显式保存项目级设置。"""

    model_config = ConfigDict(extra="forbid")
    enabled: bool


def register_publications(app: FastAPI, store: Store, admin: Any) -> None:
    """管理设置、准备历史结果和独立重试，绝不在 HTTP 中写 GitLab。"""

    @app.get("/api/repositories/{repository_id}/gitlab-publication", dependencies=[admin])
    def setting(repository_id: int) -> dict[str, bool]:
        """读取是否允许该项目向 MR 发布行内评论。"""

        if store.get_repository(repository_id) is None:
            raise HTTPException(404, "项目不存在")
        with store.connection() as db:
            row = db.execute(
                "SELECT enabled FROM gitlab_publication_settings WHERE repository_id=?",
                (repository_id,),
            ).fetchone()
            return {"enabled": bool(row[0]) if row else False}

    @app.put("/api/repositories/{repository_id}/gitlab-publication", dependencies=[admin])
    def save_setting(repository_id: int, payload: PublicationSetting) -> dict[str, bool]:
        """关闭后待发布项暂停，已发布的 GitLab 评论不自动撤回。"""

        with store.connection() as db:
            if not db.execute("SELECT 1 FROM repositories WHERE id=?",
                              (repository_id,)).fetchone():
                raise HTTPException(404, "项目不存在")
            db.execute("""INSERT INTO gitlab_publication_settings(repository_id,enabled)
                VALUES(?,?) ON CONFLICT(repository_id) DO UPDATE SET enabled=excluded.enabled""",
                (repository_id, payload.enabled))
        return {"enabled": payload.enabled}

    @app.post("/api/jobs/{job_id}/gitlab-publications/prepare", dependencies=[admin])
    def prepare(job_id: int) -> dict[str, int]:
        """为启用后的历史终态结果建立发布项，唯一约束防重复。"""

        with store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            job = db.execute("SELECT * FROM review_jobs WHERE id=?", (job_id,)).fetchone()
            if job is None:
                raise HTTPException(404, "任务不存在")
            enabled = db.execute(
                "SELECT enabled FROM gitlab_publication_settings WHERE repository_id=?",
                (job["repository_id"],),
            ).fetchone()
            if (not enabled or not enabled[0] or job["mr_iid"] < 1 or
                job["status"] not in {"complete", "partial"}):
                raise HTTPException(409, "项目未启用发布或任务尚无可发布结果")
            comments = json.loads(job["result_json"] or "{}").get("comments", [])
            count = 0
            for index in range(len(comments)):
                changed = db.execute("""INSERT OR IGNORE INTO gitlab_publications
                    (job_id,attempt_number,comment_index) VALUES(?,?,?)""",
                    (job_id, job["attempts"], index)).rowcount
                count += changed
        return {"created": count}

    @app.post("/api/gitlab-publications/{publication_id}/retry", dependencies=[admin])
    def retry(publication_id: int) -> dict[str, str]:
        """失败或未定位的评论可在 MR diff 更新后独立重试。"""

        with store.connection() as db:
            changed = db.execute("""UPDATE gitlab_publications SET status='pending',
                attempts=0,error=NULL,next_run_at=CURRENT_TIMESTAMP WHERE id=?
                AND status IN ('failed','skipped')""", (publication_id,)).rowcount
            if not changed:
                raise HTTPException(409, "评论当前无法重试")
        return {"status": "pending"}
