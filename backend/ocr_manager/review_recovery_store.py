"""以短事务管理独立补审批次和候选版本；不运行 Git/OCR，原初审不改，有效提升与通知由终态事务提交。"""

from __future__ import annotations

import json
import sqlite3
import uuid
from typing import TYPE_CHECKING, Any

from ocr_manager.artifact_lock import artifact_lock
from ocr_manager.model_pricing import estimate_cost
from ocr_manager.recovery_budget import budget_state, save_gate
from ocr_manager.review_recovery_contracts import (
    RecoveryCreate,
    RecoveryEligibility,
    RecoverySnapshot,
)
from ocr_manager.review_recovery_domain import (
    RecoveryConflict,
    coverage_items,
    digest,
    encoded,
    merge_candidate,
)
from ocr_manager.review_results import project_review_result
from ocr_manager.scheduler_config import BUSY_MODEL_REPOSITORIES

if TYPE_CHECKING:
    from ocr_manager.config import Settings
    from ocr_manager.storage import Store


def source_state(db: sqlite3.Connection, job_id: int) -> tuple[
        dict[str, Any], dict[str, Any], int, list[dict[str, Any]]]:
    """仅返回当前初审尝试对应的最新候选；后续全量重审自动隔离旧候选版本。"""

    row = db.execute("""SELECT j.*,r.enabled FROM review_jobs j JOIN repositories r
        ON r.id=j.repository_id WHERE j.id=?""", (job_id,)).fetchone()
    if row is None:
        raise RecoveryConflict("job_missing")
    job = dict(row)
    if job["status"] != "partial" or job["cancel_requested"] or not job["enabled"]:
        raise RecoveryConflict("source_not_partial")
    if not job["result_path"] or not job["result_json"] or not job["config_snapshot"]:
        raise RecoveryConflict("source_evidence_missing")
    aggregate = db.execute("""SELECT * FROM review_recovery_aggregates
        WHERE job_id=? AND source_attempt=? ORDER BY revision DESC LIMIT 1""",
        (job_id, job["attempts"])).fetchone()
    try:
        snapshot = json.loads(job["config_snapshot"])
        if (not isinstance(snapshot, dict)
                or type(snapshot.get("timeout_seconds")) is not int
                or snapshot["timeout_seconds"] <= 0
                or type(snapshot.get("max_tokens_budget")) is not int
                or snapshot["max_tokens_budget"] < 0):
            raise ValueError
        result = json.loads(aggregate["result_json"] if aggregate else job["result_json"])
        origins = (json.loads(aggregate["origins_json"]) if aggregate else [
            {"source_attempt": job["attempts"], "comment_index": index}
            for index, _ in enumerate(result.get("comments") or [])])
        if not isinstance(result, dict) or not isinstance(origins, list):
            raise ValueError
        coverage_items(result)
    except (ValueError, TypeError, AttributeError) as error:
        raise RecoveryConflict("source_evidence_invalid") from error
    if aggregate:
        from ocr_manager.review_conclusions import read_conclusion

        read_conclusion(db, job_id, source_attempt=job["attempts"], revision=aggregate["revision"])
    return job, result, aggregate["revision"] if aggregate else 0, origins


def current_hash(store: Store, settings: Settings, job: dict[str, Any]) -> str:
    """复用现有配置摘要，不调用 Git 或模型；执行前仍须重新校验。"""

    from ocr_manager.worker import config_hash

    try:
        return config_hash(store, settings, job["rule_digest"], job["repository_id"])
    except Exception as error:
        raise RecoveryConflict("configuration_unavailable") from error


def _label(value: Any) -> str:
    return value[:128] if isinstance(value, str) and value else "未知"


def eligibility(store: Store, settings: Settings, job_id: int) -> RecoveryEligibility:
    """部分任务默认可申请；有 SQLite 资格不代表工件与 Git 已在 HTTP 请求中核验。"""

    try:
        with store.connection() as db:
            db.execute("BEGIN")
            job, result, revision, _ = source_state(db, job_id)
            active = db.execute("SELECT id FROM review_recoveries WHERE job_id=? AND "
                                "status IN ('queued','running')", (job_id,)).fetchone()
            state = budget_state(db, settings, job_id, job["config_snapshot"], digest(result))
        remaining = len(coverage_items(result)["failed"])
        snapshot = json.loads(job["config_snapshot"])
        allowed_budget = min(state.max_total_tokens - state.committed_tokens,
                             snapshot["max_tokens_budget"] or 100_000_000)
        reason = ("active_recovery" if active else "nothing_remaining" if not remaining else
                  "recovery_limit" if state.used_batches >= state.max_batches
                  or allowed_budget <= 0 else
                  "budget_insufficient" if state.minimum_start_tokens > allowed_budget else
                  "configuration_changed" if current_hash(store, settings, job) !=
                  job["config_hash"] else None)
        return RecoveryEligibility(eligible=reason is None, reason_code=reason,
                                   source_attempt=job["attempts"], source_revision=revision,
                                   remaining_count=remaining,
                                   remaining_paths=sorted(coverage_items(result)["failed"]),
                                   max_token_budget=max(0, allowed_budget),
                                   max_timeout_seconds=min(3600, snapshot["timeout_seconds"]),
                                   remaining_batches=max(0, state.max_batches-state.used_batches),
                                   budget=state,
                                   active_recovery_id=active["id"] if active else None,
                                   snapshot=RecoverySnapshot(
                                       head_sha=job["commit_sha"], base_sha=job["base_sha"],
                                       provider=_label(snapshot.get("provider")),
                                       model=_label(snapshot.get("model")),
                                       model_version=(snapshot["model_version"] if
                                           type(snapshot.get("model_version")) is int else 0),
                                       ocr_version=(_label(snapshot["command"].get("package_version"))
                                           if isinstance(snapshot.get("command"), dict) else None),
                                       rule_digest=digest({key: snapshot.get(key) for key in
                                           ("rule_digest", "global_rule", "project_rule")})))
    except RecoveryConflict as error:
        return RecoveryEligibility(eligible=False, reason_code=str(error))


def enqueue(store: Store, settings: Settings, job_id: int, command: RecoveryCreate,
            requested_by: str | None = None) -> int:
    """工件锁排斥清理/全量重审；事务校验源版本和幂等键，不按客户端文件路径执行。"""

    # 1. 读取配置在写事务外完成；写事务重新读取源，Worker 在模型调用前再次核验。
    with artifact_lock(settings.data_dir, job_id) as acquired:
        if not acquired:
            raise RecoveryConflict("artifacts_busy")
        with store.connection() as db:
            row = db.execute("SELECT * FROM review_jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise RecoveryConflict("job_missing")
        expected_hash = current_hash(store, settings, dict(row))
        with store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute("SELECT * FROM review_recoveries WHERE client_key=?",
                               (str(command.client_key),)).fetchone()
            if prior:
                if any(prior[key] != value for key, value in {
                    "job_id": job_id, "source_attempt": command.source_attempt,
                    "source_revision": command.source_revision,
                    "token_budget": command.token_budget,
                    "timeout_seconds": command.timeout_seconds}.items()):
                    raise RecoveryConflict("idempotency_conflict")
                return int(prior["id"])
            # 2. 同一父任务最多一个活动批次；版本、范围和预算以锁内事实为准。
            job, source, revision, _ = source_state(db, job_id)
            state = budget_state(db, settings, job_id, job["config_snapshot"], digest(source))
            if (state.used_batches >= state.max_batches or
                    state.committed_tokens + command.token_budget > state.max_total_tokens):
                raise RecoveryConflict("recovery_limit")
            if command.token_budget < state.minimum_start_tokens:
                raise RecoveryConflict("budget_insufficient")
            if (job["attempts"] != command.source_attempt or revision != command.source_revision
                    or expected_hash != job["config_hash"]):
                raise RecoveryConflict("source_changed")
            snapshot = json.loads(job["config_snapshot"])
            if (command.timeout_seconds > snapshot["timeout_seconds"] or
                    snapshot["max_tokens_budget"] and
                    command.token_budget > snapshot["max_tokens_budget"]):
                raise RecoveryConflict("budget_exceeds_source")
            approved = [{"path": path, "item_id": item["item_id"]}
                        for path, item in sorted(coverage_items(source)["failed"].items())]
            if not approved:
                raise RecoveryConflict("nothing_remaining")
            try:
                cursor = db.execute("""INSERT INTO review_recoveries
                    (job_id,source_attempt,source_revision,client_key,source_digest,
                     source_result_json,config_snapshot,approved_json,token_budget,timeout_seconds,requested_by)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (job_id, job["attempts"], revision,
                    str(command.client_key), digest(source), encoded(source),
                    job["config_snapshot"],
                    encoded(approved), command.token_budget, command.timeout_seconds, requested_by))
            except sqlite3.IntegrityError as error:
                raise RecoveryConflict("active_recovery") from error
            assert cursor.lastrowid is not None
            return int(cursor.lastrowid)


def claim(store: Store, last_repository_id: int | None = None, *,
          respect_initial_turn: bool = True) -> dict[str, Any] | None:
    """补审与其他模型评审按仓库互斥；协调器统一轮转时不另用旧初审游标阻塞。"""

    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        turn = db.execute("SELECT next_kind FROM review_recovery_fairness WHERE id=1").fetchone()
        if respect_initial_turn and turn["next_kind"] == "initial" and db.execute(
            f"""SELECT 1 FROM review_jobs j
            JOIN repositories r ON r.id=j.repository_id WHERE j.status='queued' AND r.enabled=1
            AND j.repository_id NOT IN ({BUSY_MODEL_REPOSITORIES})
            AND j.next_run_at<=CURRENT_TIMESTAMP LIMIT 1""").fetchone():
            return None
        db.execute("""UPDATE review_recoveries SET status='stale',error_code='source_expired',
            finished_at=CURRENT_TIMESTAMP WHERE status='queued'
            AND created_at<datetime('now','-7 days')""")
        row = db.execute(f"""SELECT b.*,j.repository_id FROM review_recoveries b
            JOIN review_jobs j ON j.id=b.job_id JOIN repositories r ON r.id=j.repository_id
            WHERE b.status='queued' AND r.enabled=1
            AND j.repository_id NOT IN ({BUSY_MODEL_REPOSITORIES})
            ORDER BY CASE WHEN j.repository_id>? THEN 0 ELSE 1 END,
            j.repository_id,b.id LIMIT 1""", (last_repository_id,)).fetchone()
        if row is None:
            return None
        token = uuid.uuid4().hex
        db.execute("UPDATE review_recoveries SET status='running',execution_token=?,"
                   "started_at=CURRENT_TIMESTAMP WHERE id=?", (token, row["id"]))
        db.execute("UPDATE review_recovery_fairness SET next_kind='initial' WHERE id=1")
        return dict(row) | {"status": "running", "execution_token": token}


def cancel(store: Store, recovery_id: int) -> bool:
    """排队取消立即结束；运行取消只登记请求，由 Worker 在终态事务优先裁决。"""

    with store.connection() as db:
        cursor = db.execute("""UPDATE review_recoveries SET cancel_requested=1,
            finished_at=CASE WHEN status='queued' THEN CURRENT_TIMESTAMP ELSE finished_at END,
            status=CASE WHEN status='queued' THEN 'cancelled' ELSE status END
            WHERE id=? AND status IN ('queued','running')""", (recovery_id,))
        return cursor.rowcount == 1


def stopping(store: Store, task: dict[str, Any]) -> bool:
    """项目删除、父重审、令牌变化或用户取消都终止执行，不因心跳过期主动抢占。"""

    with store.connection() as db:
        row = db.execute("""SELECT b.cancel_requested,j.attempts,j.status,b.execution_token
            FROM review_recoveries b JOIN review_jobs j ON j.id=b.job_id
            WHERE b.id=? AND b.status='running'""", (task["id"],)).fetchone()
    return (row is None or bool(row["cancel_requested"])
            or row["attempts"] != task["source_attempt"] or row["status"] != "partial"
            or row["execution_token"] != task["execution_token"])


def finish(store: Store, task: dict[str, Any], child: dict[str, Any] | None,
           result_path: str | None = None, error_code: str | None = None) -> bool:
    """令牌和源版本共同裁决；候选、批次与新发现出现记录同事务，不改初审或投递。"""

    projection = project_review_result(child) if child is not None else None
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM review_recoveries WHERE id=? AND status='running' "
                         "AND execution_token=?", (task["id"], task["execution_token"])).fetchone()
        if row is None:
            return False
        if projection and projection.get("budget_gate"):
            if projection["budget_gate"]["budget_tokens"] != row["token_budget"]:
                projection.pop("budget_gate")
        cancelled = bool(row["cancel_requested"]) or error_code == "cancelled"
        state = "cancelled" if cancelled else "failed"
        # 1. 源快照在事务内重新核验；失效结果只结束本批次，不覆盖后来的聚合。
        if not cancelled and error_code is None and projection is not None:
            try:
                job, source, revision, origins = source_state(db, row["job_id"])
                if (job["attempts"] != row["source_attempt"] or revision != row["source_revision"]
                        or digest(source) != row["source_digest"]):
                    raise RecoveryConflict("source_changed")
                candidate, origins = merge_candidate(source, projection,
                    json.loads(row["approved_json"]), row["id"], origins)
                if not coverage_items(projection)["completed"]:
                    raise RecoveryConflict("no_progress")
                state = candidate["manifest"]["terminal_state"]
                db.execute("""INSERT INTO review_recovery_aggregates
                    (job_id,source_attempt,revision,recovery_id,result_json,origins_json)
                    VALUES(?,?,?,?,?,?)""", (row["job_id"], row["source_attempt"], revision + 1,
                    row["id"], encoded(candidate), encoded(origins)))
                # 只为本批次新增主身份记出现；精确重复保留原身份，不能另造问题或反馈。
                from ocr_manager.review_issues import capture_findings

                indices = [origin["comment_index"] for origin in origins
                           if origin.get("recovery_id") == row["id"]]
                capture_findings(db, job, projection.get("comments") or [],
                                 recovery_id=row["id"], comment_indices=indices)
            except RecoveryConflict as error:
                # 执行无有效进展不等于来源过期；两者均不得提升结论或自动重跑。
                error_code = str(error)
                state = ("failed" if error_code in {
                    "child_not_usable", "budget_unconfirmed", "no_progress"} else "stale")
        # 2. 失败/取消仍保留本批次已验证的安全用量；无 JSON 的未知用量绝不填零。
        db.execute("""UPDATE review_recoveries SET status=?,result_json=?,result_path=?,
            error_code=?,finished_at=CURRENT_TIMESTAMP WHERE id=?""",
            (state, encoded(projection) if projection is not None else None, result_path,
             "cancelled" if cancelled else error_code, row["id"]))
        if projection and projection.get("budget_gate"):
            from ocr_manager.recovery_budget import BudgetGate

            save_gate(db, row["id"], BudgetGate.model_validate(projection["budget_gate"]))
        if state in {"complete", "partial"}:
            from ocr_manager.review_effective import promote

            promote(db, row["job_id"])
        return True


def public_record(row: dict[str, Any]) -> dict[str, Any]:
    """仅返回固定批次元数据及安全用量，不暴露工件、快照和执行令牌。"""

    result = json.loads(row["result_json"]) if row.get("result_json") else {}
    snapshot = json.loads(row["config_snapshot"]) if row.get("config_snapshot") else None
    return {key: row[key] for key in ("id", "job_id", "source_attempt", "source_revision",
        "status", "token_budget", "timeout_seconds", "cancel_requested", "error_code",
        "created_at", "started_at", "finished_at", "requested_by")} | {"usage": result.get("usage"),
        "estimated_cost": estimate_cost(result.get("usage"), snapshot),
        "budget_gate": (result.get("budget_gate") if
                        (result.get("budget_gate") or {}).get("budget_tokens") ==
                        row["token_budget"] else None),
        "failure_summary": _failure_summary(result)}


def _failure_summary(result: dict[str, Any]) -> str | None:
    try:
        coverage = coverage_items(result)
    except RecoveryConflict:
        return None
    if not coverage["failed"]:
        return None
    count = len(coverage["completed"]) + len(coverage["reused"])
    summary = f"本批完成 {count}/{len(coverage['selected'])} 个文件"
    classifications = {item["classification"] for item in coverage["failed"].values()
                       if isinstance(item.get("classification"), str)}
    details = result.get("summary")
    if (isinstance(details, dict) and details.get("budget_exceeded") is True or
            "budget" in classifications):
        summary += "；触发 Token 预算限制，预算需覆盖计划和正式审核，请人工核对后调整"
    elif "timeout" in classifications:
        summary += "；覆盖项记录超时，具体触发层级仍需结合请求证据核对"
    else:
        summary += f"；{len(coverage['failed'])} 个文件未完成，具体原因未知"
    return summary + "。未自动重试或增加额度。"
