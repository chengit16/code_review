"""把逐次 OCR 发现整理为可跟进的问题，同时保留每次出现的证据。"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import TYPE_CHECKING, Any, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from ocr_manager.storage import Store


ISSUES_MIGRATION = """
CREATE TABLE review_issues (
  id INTEGER PRIMARY KEY,
  repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
  fingerprint TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open'
    CHECK(status IN ('open','fixed','ignored','merged')),
  path TEXT NOT NULL,
  content TEXT NOT NULL,
  severity TEXT,
  category TEXT,
  first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  closed_at TEXT,
  merged_into_id INTEGER REFERENCES review_issues(id) ON DELETE SET NULL
);
CREATE INDEX idx_review_issues_filter ON review_issues(repository_id,status,id DESC);
CREATE INDEX idx_review_issues_fingerprint ON review_issues(repository_id,fingerprint,status);
CREATE TABLE review_issue_occurrences (
  id INTEGER PRIMARY KEY,
  issue_id INTEGER NOT NULL REFERENCES review_issues(id) ON DELETE CASCADE,
  job_id INTEGER NOT NULL REFERENCES review_jobs(id) ON DELETE CASCADE,
  attempt_number INTEGER NOT NULL,
  comment_index INTEGER NOT NULL,
  mr_iid INTEGER NOT NULL,
  commit_sha TEXT NOT NULL,
  path TEXT NOT NULL,
  start_line INTEGER,
  content TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(job_id,attempt_number,comment_index)
);
CREATE INDEX idx_issue_occurrences_issue ON review_issue_occurrences(issue_id,id DESC);
CREATE TABLE review_issue_events (
  id INTEGER PRIMARY KEY,
  issue_id INTEGER NOT NULL REFERENCES review_issues(id) ON DELETE CASCADE,
  old_status TEXT,
  new_status TEXT NOT NULL,
  actor TEXT NOT NULL,
  note TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE review_issue_backfill (
  id INTEGER PRIMARY KEY CHECK(id=1),
  completed INTEGER NOT NULL DEFAULT 0 CHECK(completed IN (0,1))
);
INSERT INTO review_issue_backfill(id) VALUES(1);
"""


def _fingerprint(comment: dict[str, Any]) -> str:
    """只自动关联路径、类别和文字完全一致的开放问题；行号变化不改变身份。"""

    fields = (str(comment.get("path", "")).strip().casefold(),
              str(comment.get("category") or "").strip().casefold(),
              " ".join(str(comment.get("content", "")).split()).casefold())
    return hashlib.sha256(json.dumps(fields, ensure_ascii=False).encode()).hexdigest()


def capture_findings(db: sqlite3.Connection, job: dict[str, Any],
                     comments: list[Any]) -> None:
    """在评审写回事务中记录出现；重审和重复调用不会复制同一次发现。"""

    for index, comment in enumerate(comments):
        if (not isinstance(comment, dict) or not isinstance(comment.get("path"), str)
            or not isinstance(comment.get("content"), str)
            or not comment["path"].strip() or not comment["content"].strip()):
            continue
        existing = db.execute("""SELECT 1 FROM review_issue_occurrences
            WHERE job_id=? AND attempt_number=? AND comment_index=?""",
                              (job["id"], job["attempts"], index)).fetchone()
        if existing:
            continue
        fingerprint = _fingerprint(comment)
        # 人工合并后的旧指纹继续指向开放目标，避免下一次评审重新生成重复问题。
        issue = db.execute("""SELECT CASE WHEN i.status='merged' THEN t.id ELSE i.id END
            AS id FROM review_issues i LEFT JOIN review_issues t ON t.id=i.merged_into_id
            WHERE i.repository_id=? AND i.fingerprint=? AND
            (i.status='open' OR (i.status='merged' AND t.status='open'))
            ORDER BY CASE WHEN i.status='open' THEN 0 ELSE 1 END,i.id DESC LIMIT 1""",
            (job["repository_id"], fingerprint)).fetchone()
        if issue:
            issue_id = issue["id"]
            db.execute("UPDATE review_issues SET last_seen_at=CURRENT_TIMESTAMP WHERE id=?",
                       (issue_id,))
        else:
            severity = comment.get("severity")
            category = comment.get("category")
            cursor = db.execute("""INSERT INTO review_issues
                (repository_id,fingerprint,path,content,severity,category)
                VALUES(?,?,?,?,?,?)""",
                (job["repository_id"], fingerprint, comment["path"], comment["content"],
                 severity if isinstance(severity, str) else None,
                 category if isinstance(category, str) else None))
            issue_id = cursor.lastrowid
            db.execute("""INSERT INTO review_issue_events(issue_id,new_status,actor,note)
                VALUES(?,'open','系统','评审发现')""", (issue_id,))
        line = comment.get("start_line")
        db.execute("""INSERT INTO review_issue_occurrences
            (issue_id,job_id,attempt_number,comment_index,mr_iid,commit_sha,path,
             start_line,content,severity,category) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (issue_id, job["id"], job["attempts"], index, job["mr_iid"],
             job["commit_sha"], comment["path"],
             line if isinstance(line, int) and not isinstance(line, bool) else None,
             comment["content"],
             comment.get("severity") if isinstance(comment.get("severity"), str) else None,
             comment.get("category") if isinstance(comment.get("category"), str) else None))


def backfill_existing_issues(db: sqlite3.Connection) -> None:
    """旧库仅补建当前已保存的可信结果；历史尝试不推断仍未修复的问题。"""

    row = db.execute("SELECT completed FROM review_issue_backfill WHERE id=1").fetchone()
    if row is None or row["completed"]:
        return
    db.execute("BEGIN IMMEDIATE")
    for job in db.execute("""SELECT id,repository_id,attempts,mr_iid,commit_sha,result_json
        FROM review_jobs WHERE status IN ('complete','partial') AND result_json IS NOT NULL
        ORDER BY id""").fetchall():
        try:
            result = json.loads(job["result_json"])
        except (TypeError, ValueError):
            continue
        if isinstance(result, dict) and isinstance(result.get("comments"), list):
            capture_findings(db, dict(job), result["comments"])
    db.execute("UPDATE review_issue_backfill SET completed=1 WHERE id=1")


class IssueUpdate(BaseModel):
    """状态须由人确认；发现从后续评审消失不会自动视为已修复。"""

    model_config = ConfigDict(extra="forbid")
    status: Literal["open", "fixed", "ignored"]
    note: str | None = Field(default=None, max_length=500)


class IssueMerge(BaseModel):
    """管理员确认两条描述不同的问题实际上指向同一缺陷。"""

    model_config = ConfigDict(extra="forbid")
    target_id: int = Field(gt=0)


def register_review_issues(app: FastAPI, store: Store, admin: Any) -> None:
    """只提供管理查询和人工状态修改；HTTP 请求不调用 OCR 或 GitLab。"""

    @app.get("/api/review-issues", dependencies=[admin])
    def list_issues(repository_id: int | None = Query(None, gt=0),
                    status: Literal["open", "fixed", "ignored", "merged"] | None = None,
                    severity: str | None = Query(None, max_length=40),
                    page: int = Query(1, ge=1),
                    page_size: int = Query(25, ge=1, le=100)) -> dict[str, Any]:
        """按仓库、状态和级别分页；默认隐藏已合并的重复项。"""

        where = """WHERE (? IS NULL OR i.repository_id=?)
            AND (? IS NOT NULL OR i.status!='merged')
            AND (? IS NULL OR i.status=?) AND (? IS NULL OR i.severity=?)"""
        params = (repository_id, repository_id, status, status, status, severity, severity)
        with store.connection() as db:
            total = db.execute(
                f"SELECT COUNT(*) FROM review_issues i {where}", params
            ).fetchone()[0]
            rows = db.execute(f"""SELECT i.*,r.name AS repository_name,
                (SELECT COUNT(*) FROM review_issue_occurrences o WHERE o.issue_id=i.id)
                AS occurrence_count FROM review_issues i JOIN repositories r
                ON r.id=i.repository_id {where} ORDER BY i.id DESC LIMIT ? OFFSET ?""",
                (*params, page_size, (page - 1) * page_size)).fetchall()
        return {"items": [dict(row) for row in rows], "total": total,
                "page": page, "page_size": page_size}

    @app.get("/api/review-issues/{issue_id}", dependencies=[admin])
    def issue_detail(issue_id: int) -> dict[str, Any]:
        """返回原始出现位置和人工决策历史，便于跨 MR 核查。"""

        with store.connection() as db:
            issue = db.execute("""SELECT i.*,r.name AS repository_name FROM review_issues i
                JOIN repositories r ON r.id=i.repository_id WHERE i.id=?""",
                (issue_id,)).fetchone()
            if issue is None:
                raise HTTPException(404, "问题不存在")
            occurrences = [dict(row) for row in db.execute("""SELECT * FROM
                review_issue_occurrences WHERE issue_id=? ORDER BY id DESC""", (issue_id,))]
            events = [dict(row) for row in db.execute("""SELECT * FROM review_issue_events
                WHERE issue_id=? ORDER BY id DESC""", (issue_id,))]
        return {**dict(issue), "occurrences": occurrences, "events": events}

    @app.patch("/api/review-issues/{issue_id}", dependencies=[admin])
    def update_issue(issue_id: int, payload: IssueUpdate, request: Request) -> dict[str, str]:
        """记录状态变化和操作者；重复保存不生成无意义事件。"""

        with store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            issue = db.execute(
                "SELECT status FROM review_issues WHERE id=?", (issue_id,)
            ).fetchone()
            if issue is None:
                raise HTTPException(404, "问题不存在")
            if issue["status"] == "merged":
                raise HTTPException(409, "已合并的问题不能修改状态")
            if issue["status"] != payload.status:
                db.execute("""UPDATE review_issues SET status=?,
                    closed_at=CASE WHEN ?='open' THEN NULL ELSE CURRENT_TIMESTAMP END
                    WHERE id=?""", (payload.status, payload.status, issue_id))
                actor = request.state.identity["username"]
                db.execute("""INSERT INTO review_issue_events
                    (issue_id,old_status,new_status,actor,note) VALUES(?,?,?,?,?)""",
                    (issue_id, issue["status"], payload.status, actor, payload.note))
        return {"status": payload.status}

    @app.post("/api/review-issues/{issue_id}/merge", dependencies=[admin])
    def merge_issue(issue_id: int, payload: IssueMerge, request: Request) -> dict[str, int]:
        """同仓库开放问题可人工合并；保留源问题及合并记录供审计。"""

        if issue_id == payload.target_id:
            raise HTTPException(409, "不能合并到自身")
        with store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            source = db.execute("SELECT * FROM review_issues WHERE id=?", (issue_id,)).fetchone()
            target = db.execute("SELECT * FROM review_issues WHERE id=?",
                                (payload.target_id,)).fetchone()
            if source is None or target is None:
                raise HTTPException(404, "问题不存在")
            if (source["repository_id"] != target["repository_id"] or
                source["status"] != "open" or target["status"] != "open"):
                raise HTTPException(409, "仅能合并同一仓库的开放问题")
            db.execute("UPDATE review_issue_occurrences SET issue_id=? WHERE issue_id=?",
                       (payload.target_id, issue_id))
            db.execute("""UPDATE review_issues SET status='merged',merged_into_id=?,
                closed_at=CURRENT_TIMESTAMP WHERE id=?""", (payload.target_id, issue_id))
            db.execute("""UPDATE review_issues SET last_seen_at=MAX(last_seen_at,?) WHERE id=?""",
                       (source["last_seen_at"], payload.target_id))
            db.execute("""INSERT INTO review_issue_events
                (issue_id,old_status,new_status,actor,note) VALUES(?,'open','merged',?,?)""",
                (issue_id, request.state.identity["username"], f"并入问题 #{payload.target_id}"))
            db.execute("""INSERT INTO review_issue_events
                (issue_id,old_status,new_status,actor,note) VALUES(?,'open','open',?,?)""",
                (payload.target_id, request.state.identity["username"],
                 f"合并问题 #{issue_id}"))
        return {"target_id": payload.target_id}
