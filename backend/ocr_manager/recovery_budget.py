"""补审预算预检、固定数值诊断和逐任务人工授权；不执行模型，不自动增加额度或重置历史。"""

from __future__ import annotations

import json
import re
import sqlite3
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from ocr_manager.review_recovery_domain import RecoveryConflict

if TYPE_CHECKING:
    from ocr_manager.config import Settings
    from ocr_manager.storage import Store

MIGRATION = """
CREATE TABLE review_recovery_budget_evidence (
 recovery_id INTEGER PRIMARY KEY REFERENCES review_recoveries(id) ON DELETE CASCADE,
 used_tokens INTEGER NOT NULL, group_estimate_tokens INTEGER NOT NULL,
 projected_tokens INTEGER NOT NULL, budget_tokens INTEGER NOT NULL,
 artifact_digest TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE review_recovery_authorizations (
 job_id INTEGER NOT NULL REFERENCES review_jobs(id) ON DELETE CASCADE,
 version INTEGER NOT NULL, max_batches INTEGER NOT NULL CHECK(max_batches>0),
 max_total_tokens INTEGER NOT NULL CHECK(max_total_tokens>0),
 reason TEXT NOT NULL, actor TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(job_id,version)
);
"""
_GATE = re.compile(
    r"stopped dispatch: used (\d+) tokens \+ group estimate (\d+) = "
    r"projected (\d+) exceeds budget (\d+)"
)
# OCR 1.12.9：2000 + 400 + 2000*7 + 700*7 = 21300，不含 diff 和实际计划用量。
OCR_1129_MINIMUM = 21300


class BudgetGate(BaseModel):
    """只公开经过算术及用量复核的整数，不透传 warnings 原文、路径或模型响应。"""

    used_tokens: int = Field(ge=0, le=10**12, strict=True)
    group_estimate_tokens: int = Field(gt=0, le=10**12, strict=True)
    projected_tokens: int = Field(gt=0, le=10**12, strict=True)
    budget_tokens: int = Field(gt=0, le=10**12, strict=True)


class RecoveryBudget(BaseModel):
    """累计已批准而非实际账单；最低启动参考不是完成全批的保证或自动批准值。"""

    authorization_version: int = 0
    max_batches: int
    max_total_tokens: int
    used_batches: int
    committed_tokens: int
    minimum_start_tokens: int = 0
    previous_gate: BudgetGate | None = None


class BudgetAuthorization(BaseModel):
    """仅管理员显式提高或调整单任务上限；保存不是付费执行，不修改源快照约束。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_version: int = Field(ge=0, strict=True)
    max_batches: int = Field(ge=1, le=100, strict=True)
    max_total_tokens: int = Field(ge=1, le=100_000_000, strict=True)
    reason: str = Field(min_length=1, max_length=500)


def budget_gate(result: dict[str, Any]) -> BudgetGate | None:
    """严格匹配已验证版本的调度诊断并核算；未知格式保留未知而不猜预算缺口。"""

    warnings = result.get("warnings")
    summary = result.get("summary")
    if not isinstance(warnings, list) or not isinstance(summary, dict):
        return None
    total = summary.get("total_tokens")
    if type(total) is not int or total < 0 or summary.get("budget_exceeded") is not True:
        return None
    for warning in warnings[:200]:
        if not isinstance(warning, dict) or warning.get("type") != "token_budget_reached":
            continue
        text = warning.get("message")
        match = _GATE.fullmatch(text) if isinstance(text, str) and len(text) < 400 else None
        if not match:
            continue
        used, estimate, projected, budget = map(int, match.groups())
        if (
            used <= total
            and used + estimate == projected > budget > 0
            and estimate > 0
            and projected <= 10**12
        ):
            return BudgetGate(
                used_tokens=used,
                group_estimate_tokens=estimate,
                projected_tokens=projected,
                budget_tokens=budget,
            )
    return None


def save_gate(
    db: sqlite3.Connection, recovery_id: int, gate: BudgetGate, artifact_digest: str = ""
) -> None:
    """证据单独追加，不改旧批次 JSON；同内容幂等，不覆盖不同来源诊断。"""

    values = (
        gate.used_tokens,
        gate.group_estimate_tokens,
        gate.projected_tokens,
        gate.budget_tokens,
    )
    row = db.execute(
        "SELECT * FROM review_recovery_budget_evidence WHERE recovery_id=?", (recovery_id,)
    ).fetchone()
    if row:
        if tuple(row[key] for key in BudgetGate.model_fields) != values:
            raise RecoveryConflict("budget_evidence_conflict")
        return
    db.execute(
        """INSERT INTO review_recovery_budget_evidence
        (recovery_id,used_tokens,group_estimate_tokens,projected_tokens,budget_tokens,artifact_digest)
        VALUES(?,?,?,?,?,?)""",
        (recovery_id, *values, artifact_digest),
    )


def read_gate(row: sqlite3.Row | dict[str, Any]) -> BudgetGate:
    """从独立诊断表构建安全契约。"""

    return BudgetGate.model_validate({key: row[key] for key in BudgetGate.model_fields})


def budget_state(
    db: sqlite3.Connection, settings: Settings, job_id: int, snapshot_json: str, source_digest: str
) -> RecoveryBudget:
    """事务内读取最新人工授权和相同冻结来源的预算证据，旧来源不阻塞新范围。"""

    snapshot = json.loads(snapshot_json)
    authorization = db.execute(
        "SELECT * FROM review_recovery_authorizations WHERE job_id=? ORDER BY version DESC LIMIT 1",
        (job_id,),
    ).fetchone()
    count, committed = db.execute(
        "SELECT COUNT(*),COALESCE(SUM(token_budget),0) FROM review_recoveries WHERE job_id=?",
        (job_id,),
    ).fetchone()
    row = db.execute(
        """SELECT e.* FROM review_recovery_budget_evidence e JOIN review_recoveries r
        ON r.id=e.recovery_id WHERE r.job_id=? AND r.source_digest=? AND r.config_snapshot=?
        ORDER BY r.id DESC LIMIT 1""",
        (job_id, source_digest, snapshot_json),
    ).fetchone()
    gate = read_gate(row) if row else None
    command = snapshot.get("command")
    minimum = (
        OCR_1129_MINIMUM
        if isinstance(command, dict) and command.get("package_version") == "1.12.9"
        else 0
    )
    return RecoveryBudget(
        authorization_version=authorization["version"] if authorization else 0,
        max_batches=authorization["max_batches"]
        if authorization
        else settings.review_recovery_max_batches,
        max_total_tokens=authorization["max_total_tokens"]
        if authorization
        else settings.review_recovery_max_total_tokens,
        used_batches=count,
        committed_tokens=committed,
        minimum_start_tokens=max(minimum, gate.projected_tokens if gate else 0),
        previous_gate=gate,
    )


def authorize_budget(store: Store, job_id: int, payload: BudgetAuthorization, actor: str) -> None:
    """按版本追加人工上限与原因审计，不重置已用批次、不创建或自动重试评审。"""

    # 版本裁决、历史占用复核和审计追加共用写事务，避免并发管理员覆盖彼此授权。
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        if not db.execute("SELECT 1 FROM review_jobs WHERE id=?", (job_id,)).fetchone():
            raise RecoveryConflict("job_missing")
        row = db.execute(
            "SELECT max(version) FROM review_recovery_authorizations WHERE job_id=?", (job_id,)
        ).fetchone()
        if (row[0] or 0) != payload.expected_version:
            raise RecoveryConflict("budget_authorization_changed")
        count, tokens = db.execute(
            "SELECT count(*),coalesce(sum(token_budget),0) FROM review_recoveries WHERE job_id=?",
            (job_id,),
        ).fetchone()
        if payload.max_batches < count or payload.max_total_tokens < tokens:
            raise RecoveryConflict("budget_below_committed")
        db.execute(
            """INSERT INTO review_recovery_authorizations
            (job_id,version,max_batches,max_total_tokens,reason,actor) VALUES(?,?,?,?,?,?)""",
            (
                job_id,
                payload.expected_version + 1,
                payload.max_batches,
                payload.max_total_tokens,
                payload.reason,
                actor,
            ),
        )
