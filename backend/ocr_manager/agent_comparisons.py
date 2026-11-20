"""双评审查询与裁定事务；入队沿用 Agent Worker，人工记录不改变 OCR 或通知。"""

from __future__ import annotations

import json
import sqlite3
from typing import cast

from ocr_manager import agent_review_store as queue
from ocr_manager.agent_capabilities import effective_scheme, freeze_capabilities, get_scheme
from ocr_manager.agent_capabilities import project_selection as agent_selection
from ocr_manager.agent_capability_contracts import CapabilityRun
from ocr_manager.agent_comparison_contracts import (
    AgentComparison,
    ComparisonCreate,
    ComparisonCuration,
    ComparisonIndex,
    ComparisonPilot,
    ComparisonSummary,
    CurationSnapshot,
    CurationUpdate,
)
from ocr_manager.agent_comparison_results import agent_result, ocr_result, suggest_matches
from ocr_manager.agent_pilot import can_manage_pilot, repository_agent_config
from ocr_manager.agent_review_config import AgentReviewConfig
from ocr_manager.agent_review_profile import resolve_model
from ocr_manager.config import Settings
from ocr_manager.storage import Store

ACTIVE = {"queued", "running"}


class ComparisonConflict(ValueError):
    """业务冲突有可恢复的稳定码，响应不包含数据库行或连接参数。"""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def comparison_index(store: Store, settings: Settings, job_id: int,
                     before_id: int | None, limit: int) -> ComparisonIndex:
    """固定读取当前来源、待执行任务和有限历史，无可比任务时保留现有 OCR 入口。"""

    with store.connection() as db:
        db.execute("BEGIN")
        repository = db.execute("""SELECT r.id,r.name,r.enabled FROM review_jobs j
            JOIN repositories r ON r.id=j.repository_id WHERE j.id=?""", (job_id,)).fetchone()
        if repository is None:
            raise LookupError("任务不存在")
        config = repository_agent_config(db, settings, repository["id"])
        scheme = effective_scheme(db, repository["id"])
        pilot = ComparisonPilot(repository_name=repository["name"], enabled=config is not None,
            manageable=(bool(repository["enabled"]) or config is not None)
            and can_manage_pilot(settings, repository["id"]))
        source = queue.current_source(db, job_id)
        active = db.execute("""SELECT id FROM agent_reviews WHERE job_id=?
            AND status IN ('queued','running')""", (job_id,)).fetchone()
        previous = db.execute("""SELECT id FROM agent_reviews WHERE source_attempt_id=?
            ORDER BY id DESC LIMIT 1""", (source["attempt_id"],)).fetchone() if source else None
        rows = db.execute("""SELECT a.id,a.previous_id,a.status,a.created_at,a.finished_at,
            COALESCE(json_extract(c.snapshot,'$.trial'),0) AS trial,
            c.snapshot IS NOT NULL AS capability_recorded,
            o.attempt_number AS source_attempt FROM agent_reviews a
            JOIN review_attempts o ON o.id=a.source_attempt_id
            LEFT JOIN agent_run_capabilities c ON c.run_id=a.id
            WHERE a.job_id=? AND (? IS NULL OR a.id<?) ORDER BY a.id DESC LIMIT ?""",
            (job_id, before_id, before_id, limit + 1)).fetchall()
    return ComparisonIndex(current_source_attempt=source["attempts"] if source else None,
        previous_id=previous["id"] if previous else None,
        active_id=active["id"] if active else None,
        pilot=pilot,
        current_scheme_id=scheme.id, current_scheme_name=scheme.name,
        unavailable_reason=_unavailable(config, source, active is not None),
        items=[ComparisonSummary.model_validate(dict(row)) for row in rows[:limit]],
        next_before_id=rows[limit - 1]["id"] if len(rows) > limit else None)


def _unavailable(config: AgentReviewConfig | None, source: sqlite3.Row | None,
                 active: bool) -> str | None:
    if active:
        return "已有 Agent 评审排队或运行中"
    if config is None:
        return "Agent 试点尚未启用"
    if source is None or source["status"] not in queue.TERMINAL_OCR or source["superseded"]:
        return "需要当前且已结束的 OCR 初审"
    if not source["enabled"]:
        return "请先启用该仓库"
    try:
        queue.source_range(source)
    except ValueError:
        return "当前初审缺少可核对的固定提交范围"
    return None


def create_comparison(store: Store, settings: Settings, job_id: int, body: ComparisonCreate) -> int:
    """只登记 Agent 尝试，响应丢失后同键可找回既有结果，Worker 验证实际模型。"""

    with store.connection() as db:
        row = db.execute("SELECT repository_id FROM review_jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise LookupError("任务不存在")
        existing = db.execute("""SELECT a.id,a.previous_id,c.snapshot AS capability_snapshot,
            o.attempt_number
            FROM agent_reviews a
            JOIN review_attempts o ON o.id=a.source_attempt_id
            LEFT JOIN agent_run_capabilities c ON c.run_id=a.id
            WHERE a.job_id=? AND a.request_key=?""", (job_id, body.request_key)).fetchone()
        repository_id = int(row["repository_id"])
        if existing:
            if _same_request(existing, body):
                return int(existing["id"])
            raise ComparisonConflict("request_key_mismatch", "同一请求键已用于其他评审版本")
        config = repository_agent_config(db, settings, repository_id)
        if config is None:
            raise ComparisonConflict("agent_disabled", "Agent 试点尚未启用")
        try:
            config, frozen = _resolve_run(db, store, config, repository_id, job_id, body)
        except (LookupError, ValueError) as error:
            raise ComparisonConflict("agent_enqueue_conflict", str(error)) from error
    try:
        return queue.enqueue(store, config, job_id, body.request_key, body.previous_id,
                             source_attempt=body.source_attempt, capabilities=frozen)
    except ValueError as error:
        raise ComparisonConflict("agent_enqueue_conflict", str(error)) from error


def _same_request(row: sqlite3.Row, body: ComparisonCreate) -> bool:
    frozen = json.loads(row["capability_snapshot"] or "{}")
    return (
        row["previous_id"] == body.previous_id and row["attempt_number"] == body.source_attempt
        and frozen.get("config_mode", "current") == body.config_mode
        and (body.config_mode == "original" or bool(frozen.get("trial")) ==
             (body.trial_scheme_id is not None))
        and (body.trial_scheme_id is None or body.trial_scheme_id == frozen.get("scheme_id"))
        and (body.config_mode != "original" or (body.original_run_id or body.previous_id)
             == frozen.get("original_run_id"))
        and (body.expected_scheme_id is None or body.expected_scheme_id == frozen.get("scheme_id"))
    )


def _resolve_run(
    db: sqlite3.Connection, store: Store, config: AgentReviewConfig, repository_id: int,
    job_id: int, body: ComparisonCreate,
) -> tuple[AgentReviewConfig, CapabilityRun]:
    selected = agent_selection(db, repository_id)
    model_id = selected["model_profile_id"] if selected else None
    if body.config_mode == "original":
        if body.trial_scheme_id is not None or body.expected_scheme_id is not None:
            raise ValueError("按原配置重跑不能选择其他方案")
        original_id = body.original_run_id or body.previous_id
        original = db.execute("""SELECT c.snapshot AS capability_snapshot,a.model_snapshot
            FROM agent_reviews a JOIN agent_run_capabilities c ON c.run_id=a.id
            JOIN review_attempts o ON o.id=a.source_attempt_id
            WHERE a.job_id=? AND a.id=? AND o.attempt_number=?""",
            (job_id, original_id, body.source_attempt)).fetchone()
        if not original or not original["capability_snapshot"]:
            raise ValueError("上一次运行没有可复用的配置快照")
        frozen = CapabilityRun.model_validate_json(original["capability_snapshot"])
        config = resolve_model(store, config, repository_id,
                               profile_id=frozen.model_profile_id, db=db)
        previous_model = json.loads(original["model_snapshot"])
        if config.snapshot(previous_model.get("ocr_rule_sha256")) != original["model_snapshot"]:
            raise ValueError("原模型档案或执行参数已变化，请按当前项目配置运行")
        scheme = get_scheme(db, frozen.scheme_id)
        current = freeze_capabilities(db, scheme, repository_id, config, trial=frozen.trial)
        if current.mcp_signature != frozen.mcp_signature:
            raise ValueError("原 MCP 工具契约已变化，请按当前项目配置运行")
        return config, current.model_copy(update={"config_mode": "original",
                                                  "original_run_id": original_id})
    if body.original_run_id is not None:
        raise ValueError("原运行编号只适用于按原配置重跑")
    scheme = (get_scheme(db, body.trial_scheme_id) if body.trial_scheme_id
              else effective_scheme(db, repository_id))
    if body.expected_scheme_id is not None and scheme.id != body.expected_scheme_id:
        raise ValueError("项目方案已更新，请核对后重新确认")
    config = resolve_model(store, config, repository_id, profile_id=model_id, db=db)
    return config, freeze_capabilities(db, scheme, repository_id, config,
                                      trial=body.trial_scheme_id is not None)


def _run(db: sqlite3.Connection, job_id: int, run_id: int) -> sqlite3.Row:
    row = db.execute(f"{queue.RUN_SQL} AND a.job_id=?", (run_id, job_id)).fetchone()
    if row is None:
        raise LookupError("比较版本不存在")
    return cast(sqlite3.Row, row)


def _curation(db: sqlite3.Connection, run_id: int, version: int | None) -> CurationSnapshot:
    if version == 0:
        return CurationSnapshot(version=0, document=ComparisonCuration())
    row = db.execute("""SELECT version,actor,created_at,document FROM agent_comparison_curations
        WHERE agent_review_id=? AND (? IS NULL OR version=?) ORDER BY version DESC LIMIT 1""",
        (run_id, version, version)).fetchone()
    if row:
        return CurationSnapshot(version=row["version"], actor=row["actor"],
            created_at=row["created_at"], document=ComparisonCuration.model_validate_json(
                row["document"]))
    if version is not None:
        raise LookupError("裁定版本不存在")
    return CurationSnapshot(version=0, document=ComparisonCuration())


def comparison_detail(store: Store, job_id: int, run_id: int,
                      curation_version: int | None) -> AgentComparison:
    """将两路状态、覆盖、证据和裁定绑定到同一 SQLite 读快照。"""

    with store.connection() as db:
        db.execute("BEGIN")
        row = _run(db, job_id, run_id)
        ocr = ocr_result(db, row)
        agent = agent_result(db, row)
        latest = _curation(db, run_id, None)
        curation = latest if curation_version is None or latest.version == curation_version else (
            _curation(db, run_id, curation_version))
    return AgentComparison(id=row["id"], source_attempt=row["ocr_attempt"],
        trial=bool(agent.capabilities and agent.capabilities.trial),
        capability_recorded=agent.capabilities is not None,
        previous_id=row["previous_id"], status=row["status"], created_at=row["created_at"],
        finished_at=row["finished_at"], base_sha=row["base_sha"], head_sha=row["head_sha"],
        ocr=ocr, agent=agent, suggestions=suggest_matches(ocr, agent), curation=curation,
        latest_curation_version=latest.version)


def _validate_curation(
    document: ComparisonCuration, ocr_ids: set[str], agent_ids: set[str],
) -> None:
    evaluated = [item.finding_id for item in document.evaluations]
    if (not set(evaluated) <= (ocr_ids | agent_ids) or len(evaluated) != len(set(evaluated))):
        raise ComparisonConflict("invalid_evaluation", "裁定引用了重复或不属于本次比较的发现")
    left = [item for group in document.matches for item in group.ocr_ids]
    right = [item for group in document.matches for item in group.agent_ids]
    if (not set(left) <= ocr_ids or not set(right) <= agent_ids
            or len(left) != len(set(left)) or len(right) != len(set(right))):
        raise ComparisonConflict("invalid_match", "每条发现只能加入一个有效的同根因组")
    if (len({item.id for item in document.matches}) != len(document.matches)
            or len({item.id for item in document.missed}) != len(document.missed)):
        raise ComparisonConflict("duplicate_curation_id", "同根因组或漏报编号重复")


def save_curation(store: Store, job_id: int, run_id: int, body: CurationUpdate,
                  actor: str) -> CurationSnapshot:
    """锁内确认比较终态、旧版本与发现身份，原子追加，不修改引擎结论。"""

    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = _run(db, job_id, run_id)
        if row["status"] in ACTIVE:
            raise ComparisonConflict("comparison_running", "评审结束后才能保存裁定")
        latest = _curation(db, run_id, None)
        if latest.version != body.expected_version:
            raise ComparisonConflict(
                "curation_conflict", "另一位评审者已更新裁定，请保留草稿并核对",
            )
        _validate_curation(body.document, {item.id for item in ocr_result(db, row).findings},
                           {item.id for item in agent_result(db, row).findings})
        db.execute("""INSERT INTO agent_comparison_curations
            (agent_review_id,version,document,actor) VALUES(?,?,?,?)""",
            (run_id, latest.version + 1, body.document.model_dump_json(), actor))
        return _curation(db, run_id, latest.version + 1)
