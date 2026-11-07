"""按已验证来源身份处理反馈；仅写 SQLite，与问题决策同事务，不发布候选或调用外部服务。"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

from ocr_manager.feedback_issues import sync_feedback_issue
from ocr_manager.review_conclusions import read_conclusion
from ocr_manager.review_recovery_domain import RecoveryConflict

if TYPE_CHECKING:
    from ocr_manager.storage import Store

Verdict = Literal["helpful", "false_positive", "fixed"]


class FindingFeedbackVersion(BaseModel):
    """写入显式版本且拒绝未知字段；旧页面不能靠聚合下标误写补审反馈。"""

    model_config = ConfigDict(extra="forbid")
    source_attempt: int = Field(gt=0, strict=True)
    revision: int = Field(ge=0, strict=True)


class FindingFeedbackWrite(FindingFeedbackVersion):
    """操作者只从服务端鉴权身份取得，不接收客户端提供的作者。"""

    verdict: Verdict


class FindingFeedbackRecord(BaseModel):
    """反馈随稳定发现身份保留；重审后旧版本可读但不可继续写入。"""

    finding_id: str
    verdict: Verdict
    actor: str
    updated_at: str


def mirror_initial_feedback(db: sqlite3.Connection, job_id: int, attempt: int,
                            index: int, verdict: str | None, actor: str) -> None:
    """旧入口同事务双写稳定身份；历史反馈在全量重审清空旧索引后仍可审计。"""

    identifier = f"j{job_id}:a{attempt}:c{index}"
    if verdict is None:
        db.execute("DELETE FROM review_finding_feedback WHERE finding_id=?", (identifier,))
    else:
        db.execute("""INSERT INTO review_finding_feedback(finding_id,verdict,actor)
            SELECT finding_id,?,? FROM review_issue_occurrences WHERE finding_id=?
            ON CONFLICT(finding_id) DO UPDATE SET verdict=excluded.verdict,
            actor=excluded.actor,updated_at=CURRENT_TIMESTAMP""", (verdict, actor, identifier))


def read_feedback(db: sqlite3.Connection, job_id: int, source_attempt: int,
                  revision: int) -> list[FindingFeedbackRecord]:
    """调用方持有读事务；只读该版本主身份，附加重复来源不复制反馈。"""

    document = read_conclusion(db, job_id, source_attempt=source_attempt, revision=revision)
    identifiers = {item.finding_id for item in document.findings}
    return [FindingFeedbackRecord.model_validate(dict(row)) for row in db.execute("""SELECT f.*
        FROM review_finding_feedback f JOIN review_issue_occurrences o
        ON o.finding_id=f.finding_id WHERE o.job_id=? AND o.attempt_number=?""",
        (job_id, source_attempt)) if row["finding_id"] in identifiers]


def write_feedback(store: Store, job_id: int, finding_id: str,
                   version: FindingFeedbackVersion, verdict: Verdict | None,
                   actor: str) -> None:
    """写锁内校验当前最新版本与主身份；反馈、旧入口镜像和问题审计原子提交或回滚。"""

    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        # 1. 必须与当前最新可读结论一致；重审排队、旧版本和取消中的来源拒绝写入。
        current = read_conclusion(db, job_id)
        job = db.execute("SELECT cancel_requested FROM review_jobs WHERE id=?",
                         (job_id,)).fetchone()
        if (current.version.source_attempt != version.source_attempt
                or current.version.revision != version.revision or job["cancel_requested"]):
            raise RecoveryConflict("feedback_version_changed")
        finding = next((item for item in current.findings if item.finding_id == finding_id), None)
        if finding is None:
            raise LookupError("发现不属于该版本")
        occurrence = db.execute("SELECT 1 FROM review_issue_occurrences WHERE finding_id=?",
                                (finding_id,)).fetchone()
        if occurrence is None:
            raise RecoveryConflict("finding_occurrence_missing")
        # 2. 根发现仍兼容旧接口和旧统计；补审来源永不写入旧的评论索引空间。
        origin = finding.origin
        if verdict is None:
            if db.execute("DELETE FROM review_finding_feedback WHERE finding_id=?",
                          (finding_id,)).rowcount == 0:
                raise LookupError("反馈不存在")
        else:
            db.execute("""INSERT INTO review_finding_feedback(finding_id,verdict,actor)
                VALUES(?,?,?) ON CONFLICT(finding_id) DO UPDATE SET verdict=excluded.verdict,
                actor=excluded.actor,updated_at=CURRENT_TIMESTAMP""", (finding_id, verdict, actor))
        if origin.kind == "attempt":
            if verdict is None:
                db.execute("DELETE FROM review_feedback WHERE job_id=? AND comment_index=?",
                           (job_id, origin.comment_index))
            else:
                db.execute("""INSERT INTO review_feedback(job_id,comment_index,verdict)
                    VALUES(?,?,?) ON CONFLICT(job_id,comment_index) DO UPDATE SET
                    verdict=excluded.verdict,updated_at=CURRENT_TIMESTAMP""",
                    (job_id, origin.comment_index, verdict))
        # 3. 只撤销本来源拥有的关闭决定，不覆盖问题页面或其他发现的后续决策。
        sync_feedback_issue(db, job_id, origin.source_attempt, origin.comment_index,
                            verdict, actor, recovery_id=origin.recovery_id)
