"""影子评审 SQLite 操作；短事务负责去重、状态和调用记账，不执行 Git 或模型。"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import asdict
from typing import Literal, cast
from uuid import uuid4

from ocr_manager.agent_pilot import managed_pilot_enabled
from ocr_manager.agent_review_config import AgentReviewConfig
from ocr_manager.review_prototype.graph import AgentProgress
from ocr_manager.review_prototype.input import ReviewInput
from ocr_manager.review_prototype.result import ReviewResult
from ocr_manager.scheduler_config import BUSY_MODEL_REPOSITORIES
from ocr_manager.storage import Store

TERMINAL_OCR = {"complete", "partial", "failed", "skipped"}
RUN_SQL = """SELECT a.*,j.repository_id,j.source,j.mr_iid,j.target_branch,j.context_hint,
    j.commit_sha,j.superseded,j.attempts,j.status AS job_status,j.config_hash,j.context_json,
    MAX(0,(julianday('now')-julianday(a.started_at))*86400) AS elapsed_seconds,
    r.enabled,r.project_id,r.gitlab_url,r.gitlab_token_ciphertext,
    o.attempt_number AS ocr_attempt,o.status AS ocr_status
    FROM agent_reviews a JOIN review_jobs j ON j.id=a.job_id
    JOIN repositories r ON r.id=j.repository_id
    JOIN review_attempts o ON o.id=a.source_attempt_id WHERE a.id=?"""


def enqueue(
    store: Store, config: AgentReviewConfig, job_id: int, request_key: str,
    previous_id: int | None = None, *, source_attempt: int | None = None,
) -> int:
    """本机运维触发；写锁下固定 OCR 初审版本和已验证的 Git 范围，禁止并行重跑。"""

    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", request_key):
        raise ValueError("请求键须为 1 到 100 个 ASCII 字母、数字或 ._:-")
    if config.model_source == "project" and config.profile_reference is None:
        raise ValueError("入队前须解析项目的模型配置版本")
    snapshot = config.snapshot()
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        # 1. 幂等查询先于当前任务校验，终态后重复同一请求也只返回原版本。
        existing = db.execute(
            """SELECT a.id,a.previous_id,a.model_snapshot,o.attempt_number
            FROM agent_reviews a JOIN review_attempts o ON o.id=a.source_attempt_id
            WHERE a.job_id=? AND a.request_key=?""",
            (job_id, request_key),
        ).fetchone()
        if existing:
            same_source = source_attempt is None or existing["attempt_number"] == source_attempt
            if (existing["previous_id"] != previous_id or existing["model_snapshot"] != snapshot
                    or not same_source):
                raise ValueError("同一请求键已绑定其他参数")
            return int(existing["id"])
        # 2. 旧任务缺少实际预检范围时默认拒绝，避免把当前分支当成历史 OCR 输入。
        source = current_source(db, job_id)
        if not source or source["status"] not in TERMINAL_OCR or source["superseded"]:
            raise ValueError("需要当前且已结束的 OCR 尝试")
        if source_attempt is not None and source["attempts"] != source_attempt:
            raise ValueError("OCR 尝试已更新，请核对新的初审版本")
        if not source["enabled"] or source["repository_id"] not in config.repositories:
            raise ValueError("仓库未获准运行 Agent")
        if config.managed_pilot and not managed_pilot_enabled(db, source["repository_id"]):
            raise ValueError("仓库的 Agent 试点已关闭")
        base, head = source_range(source)
        latest = db.execute("""SELECT id,status FROM agent_reviews
            WHERE source_attempt_id=? ORDER BY id DESC LIMIT 1""", (source["attempt_id"],)
        ).fetchone()
        if latest and latest["status"] in {"queued", "running"}:
            raise ValueError("已有运行中或排队的 Agent 尝试")
        if previous_id != (latest["id"] if latest else None):
            raise ValueError("重跑须引用该 OCR 版本的最近一次 Agent 尝试")
        if db.execute("""SELECT 1 FROM agent_reviews WHERE job_id=?
            AND status IN ('queued','running')""", (job_id,)).fetchone():
            raise ValueError("此任务已有运行中或排队的 Agent 尝试")
        # 3. 新尝试只关联原 OCR 尝试，不调用初审、投递或发布用例。
        cursor = db.execute("""INSERT INTO agent_reviews
            (job_id,source_attempt_id,previous_id,request_key,base_sha,head_sha,
             ocr_config_hash,context_digest,model_snapshot) VALUES(?,?,?,?,?,?,?,?,?)""",
            (job_id, source["attempt_id"], previous_id, request_key, base, head,
             source["config_hash"], _context_digest(source), snapshot))
        assert cursor.lastrowid is not None
        return cursor.lastrowid


def current_source(db: sqlite3.Connection, job_id: int) -> sqlite3.Row | None:
    """从调用方事务读取当前 OCR 尝试，要求任务与尝试状态一致。"""

    return cast(sqlite3.Row | None, db.execute("""SELECT j.*,o.id AS attempt_id,r.enabled
        FROM review_jobs j JOIN repositories r ON r.id=j.repository_id
        JOIN review_attempts o ON o.job_id=j.id AND o.attempt_number=j.attempts
          AND o.status=j.status WHERE j.id=?""", (job_id,)).fetchone())


def source_range(source: sqlite3.Row) -> tuple[str, str]:
    """校验已落库的 OCR 固定范围；没有预检快照时不使用当前分支。"""

    scope = json.loads(source["scope_json"] or "{}")
    if not isinstance(scope, dict):
        raise ValueError("缺少固定的 OCR 评审范围")
    base, head = scope.get("base_sha"), scope.get("head_sha")
    if (
        not isinstance(base, str) or not re.fullmatch(r"[0-9a-f]{40}", base)
        or not isinstance(head, str) or not re.fullmatch(r"[0-9a-f]{40}", head)
        or head != source["commit_sha"] or base == head
        or (source["base_sha"] is not None and base != source["base_sha"])
        or (source["source"] == "premerge" and base != source["base_sha"])
        or type(scope.get("original_count")) is not int or scope["original_count"] < 0
    ):
        raise ValueError("缺少可核对的 OCR 评审范围")
    return base, head


def _context_digest(source: sqlite3.Row) -> str:
    context = json.dumps([source["context_hint"], source["context_json"]], ensure_ascii=False)
    return hashlib.sha256(context.encode()).hexdigest()


def claim(store: Store) -> dict[str, int] | None:
    """正式模型任务领取之后尝试；原子领取并参与同仓库互斥。"""

    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(f"""SELECT a.id,j.repository_id FROM agent_reviews a
            JOIN review_jobs j ON j.id=a.job_id
            WHERE a.status='queued' AND j.repository_id NOT IN ({BUSY_MODEL_REPOSITORIES})
            ORDER BY a.id LIMIT 1""").fetchone()
        if row is None:
            return None
        db.execute("""UPDATE agent_reviews SET status='running',
            started_at=COALESCE(started_at,strftime('%Y-%m-%dT%H:%M:%fZ','now')) WHERE id=?""",
            (row["id"],))
        return {"id": int(row["id"]), "repository_id": int(row["repository_id"])}


def load_run(store: Store, run_id: int) -> sqlite3.Row | None:
    """执行端按 ID 重读，活动状态和固定尝试由数据库提供。"""

    with store.connection() as db:
        return cast(sqlite3.Row | None, db.execute(RUN_SQL, (run_id,)).fetchone())


def source_is_current(row: sqlite3.Row) -> bool:
    """OCR 重评、MR 被替代或仓库关闭后，历史仍可查，旧影子任务不得继续付费。"""

    return (
        bool(row["enabled"]) and not row["superseded"]
        and row["job_status"] in TERMINAL_OCR and row["job_status"] == row["ocr_status"]
        and row["attempts"] == row["ocr_attempt"] and row["commit_sha"] == row["head_sha"]
        and row["config_hash"] == row["ocr_config_hash"]
        and _context_digest(row) == row["context_digest"]
    )


def pin_input(store: Store, run_id: int, snapshot: ReviewInput) -> bool:
    """以实际差异固定内容身份和清单，不把差异全文写入业务库。"""

    key = snapshot.key
    manifest = json.dumps({
        "hunks": [{"id": hunk.hunk_id, "path": hunk.path, "records": len(hunk.lines)}
                  for hunk in snapshot.hunks],
        "excluded_paths": snapshot.excluded_paths,
    }, ensure_ascii=False)
    with store.connection() as db:
        cursor = db.execute("""UPDATE agent_reviews SET input_key=?,input_manifest_json=?
            WHERE id=? AND status='running' AND NOT EXISTS (
              SELECT 1 FROM agent_reviews p
              WHERE p.source_attempt_id=agent_reviews.source_attempt_id
                AND p.input_key IS NOT NULL AND p.input_key!=?)""", (key, manifest, run_id, key))
        return cursor.rowcount == 1


def cancel(store: Store, run_id: int) -> bool:
    """已排队直接结束；在途结果提交前以取消为准，不影响 OCR 和调用账目。"""

    with store.connection() as db:
        cursor = db.execute("""UPDATE agent_reviews SET cancel_requested=1,
            reason=CASE WHEN status='queued' THEN 'cancelled' ELSE reason END,
            finished_at=CASE WHEN status='queued' THEN CURRENT_TIMESTAMP ELSE finished_at END,
            status=CASE WHEN status='queued' THEN 'cancelled' ELSE status END
            WHERE id=? AND status IN ('queued','running') AND cancel_requested=0""", (run_id,))
        return cursor.rowcount == 1


def finish(
    store: Store, run_id: int, *, reason: str, result: ReviewResult | None = None,
) -> None:
    """在写锁内裁决取消与迟到结果；保留已验证覆盖，状态与结束时间同事务。"""

    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(RUN_SQL, (run_id,)).fetchone()
        if row is None or row["status"] != "running":
            return
        status: Literal["complete", "partial", "failed", "skipped", "cancelled"]
        status = result.status if result else "failed"
        if row["cancel_requested"]:
            status, reason, result = "cancelled", "cancelled", None
        elif not source_is_current(row):
            status, reason, result = "failed", "source_changed", None
        db.execute("""UPDATE agent_reviews SET status=?,reason=?,result_json=?,
            finished_at=CURRENT_TIMESTAMP WHERE id=?""", (
            status, reason, json.dumps(asdict(result), ensure_ascii=False) if result else None,
            run_id,
        ))


def reserve_call(
    store: Store, run_id: int, hunk_id: int, offset: int, tokens: int,
    max_reads: int | None, max_tokens: int | None, max_source_tokens: int | None,
) -> str | None:
    """先登记可能产生费用的调用；同一页只准发送一次，未知账目阻止下一次调用。"""

    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        source = db.execute(RUN_SQL, (run_id,)).fetchone()
        if not source or source["status"] != "running" or source["cancel_requested"]:
            return None
        if not source_is_current(source):
            return None
        # 启用 Token 门槛时，同一 OCR 版本的未知请求按原预留占用后续额度。
        usage = db.execute("""WITH charges AS (
              SELECT a.id,c.status,CASE WHEN c.status='recorded'
                THEN c.prompt_tokens+c.completion_tokens ELSE c.reserved_tokens END AS tokens
              FROM agent_reviews a JOIN agent_review_calls c ON c.agent_review_id=a.id
              WHERE a.source_attempt_id=?
            ) SELECT COUNT(*) FILTER(WHERE id=?) AS calls,
              COALESCE(SUM(tokens) FILTER(WHERE id=?),0) AS run_tokens,
              COALESCE(SUM(tokens),0) AS source_tokens,
              MAX(status='unknown') FILTER(WHERE id=?) AS unknown
              FROM charges""", (source["source_attempt_id"], run_id, run_id, run_id)).fetchone()
        if (
            usage["unknown"]
            or (max_reads is not None and usage["calls"] >= max_reads)
            or (max_tokens is not None and usage["run_tokens"] + tokens > max_tokens)
            or (max_source_tokens is not None
                and usage["source_tokens"] + tokens > max_source_tokens)
        ):
            return None
        identifier = uuid4().hex
        db.execute("""INSERT INTO agent_review_calls
            (id,agent_review_id,hunk_id,page_offset,reserved_tokens) VALUES(?,?,?,?,?)
            ON CONFLICT(agent_review_id,hunk_id,page_offset) DO NOTHING""",
            (identifier, run_id, hunk_id, offset, tokens))
        return identifier if db.execute("SELECT changes()").fetchone()[0] == 1 else None


def record_usage(
    store: Store, call_id: str, prompt: int, completion: int, provider_model: str | None = None,
) -> None:
    """结束调用记账；只保存供应商返回的 Token 数，费用金额仍未知。"""

    with store.connection() as db:
        db.execute("""UPDATE agent_review_calls SET status='recorded',prompt_tokens=?,
            completion_tokens=?,provider_model=?,finished_at=CURRENT_TIMESTAMP
            WHERE id=? AND status='unknown'""", (prompt, completion, provider_model, call_id))


def checkpoint(store: Store, run_id: int, progress: AgentProgress) -> bool:
    """在完整校验本页后保存恢复点；已记账的连续页才算完成。"""

    with store.connection() as db:
        cursor = db.execute("""UPDATE agent_reviews SET completed_pages=?,progress_json=?
            WHERE id=? AND status='running' AND cancel_requested=0 AND completed_pages=?
            AND ?=(SELECT COUNT(*) FROM agent_review_calls c
                 WHERE c.agent_review_id=agent_reviews.id AND c.status='recorded')
            """, (progress.reads, json.dumps(asdict(progress), ensure_ascii=False),
                  run_id, progress.reads - 1, progress.reads))
        return cursor.rowcount == 1


def report(store: Store, run_id: int) -> dict[str, object]:
    """只读取得固定 OCR 结果、Agent 结果及调用账目；凭据和代码输入不在返回中。"""

    with store.connection() as db:
        db.execute("BEGIN")
        row = db.execute(RUN_SQL, (run_id,)).fetchone()
        if row is None:
            raise ValueError("Agent 尝试不存在")
        ocr = db.execute(
            "SELECT result_json FROM review_attempts WHERE id=?", (row["source_attempt_id"],),
        ).fetchone()
        calls = db.execute("""SELECT id,hunk_id,page_offset,status,reserved_tokens,prompt_tokens,
            completion_tokens,provider_model,started_at,finished_at FROM agent_review_calls
            WHERE agent_review_id=? ORDER BY rowid""", (run_id,)).fetchall()
    return {
        "comparison": {key: row[key] for key in (
            "id", "job_id", "previous_id", "base_sha", "head_sha", "input_key",
        )},
        "input_manifest": json.loads(row["input_manifest_json"] or "null"),
        "ocr": {"attempt_number": row["ocr_attempt"], "revision": 0, "status": row["ocr_status"],
                "config_hash": row["ocr_config_hash"], "result": json.loads(ocr[0] or "null")},
        "agent": {"status": row["status"], "reason": row["reason"],
                  "started_at": row["started_at"], "finished_at": row["finished_at"],
                  "config": json.loads(row["model_snapshot"]),
                  "result": json.loads(row["result_json"] or "null"),
                  "progress": json.loads(row["progress_json"] or "null")
                  if row["result_json"] is None else None,
                  "calls": [dict(call) for call in calls],
                  "cost_minor_units": None if calls else 0},
    }
