"""补充通知的独立 Outbox；按不可变版本投递，有限重试只涉及通知，不重新运行 OCR。"""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, Any

from ocr_manager.review_conclusions import read_conclusion
from ocr_manager.review_recovery_domain import RecoveryConflict

if TYPE_CHECKING:
    from ocr_manager.storage import Store


def claim_delivery(store: Store) -> dict[str, Any] | None:
    """短写事务领取并设置令牌；初审投递仍在途时等待，旧源待发送记录标记失效。"""

    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("""UPDATE review_recovery_deliveries SET status='superseded'
            WHERE status IN ('pending','failed') AND NOT EXISTS (
            SELECT 1 FROM review_jobs j WHERE j.id=job_id AND j.attempts=source_attempt
            AND j.status='partial' AND j.cancel_requested=0)""")
        row = db.execute("""SELECT d.*,j.repository_id,j.commit_sha,j.commit_author,j.mr_iid,
            j.notification_min_severity,r.name AS repository_name,r.target_branch,
            n.status AS initial_delivery_status FROM review_recovery_deliveries d
            JOIN review_jobs j ON j.id=d.job_id JOIN repositories r ON r.id=j.repository_id
            LEFT JOIN notification_deliveries n ON n.job_id=j.id
            WHERE d.status='pending' AND d.next_run_at<=CURRENT_TIMESTAMP AND r.enabled=1
            AND COALESCE(n.status,'sent') IN ('sent','failed') ORDER BY d.id LIMIT 1""").fetchone()
        if row is None:
            return None
        # 冻结版本也必须能从当前证据重新核验；源损坏时宁可停发，不发布假成功。
        try:
            verified = read_conclusion(db, row["job_id"], source_attempt=row["source_attempt"],
                            revision=row["revision"])
            frozen = json.loads(row["document_json"])
            if (frozen.get("version") != verified.version.model_dump() or
                    frozen.get("findings") != [item.model_dump() for item in verified.findings]):
                raise RecoveryConflict("conclusion_evidence_invalid")
        except (RecoveryConflict, LookupError):
            db.execute("UPDATE review_recovery_deliveries SET status='superseded',"
                       "error='结论来源失效，未发送' WHERE id=?", (row["id"],))
            return None
        token = uuid.uuid4().hex
        db.execute("""UPDATE review_recovery_deliveries SET status='sending',
            execution_token=?,attempts=attempts+1 WHERE id=?""", (token, row["id"]))
        document = json.loads(row["document_json"])
        coverage = document["version"]["coverage"]
        result = {"comments": [item for item in document["findings"]
            if item["origin"]["recovery_id"] == row["recovery_id"]],
            "manifest": {"terminal_state": document["version"]["terminal_state"],
                         "coverage": {key: [None] * value for key, value in coverage.items()}}}
        return dict(row) | {"execution_token": token, "delivery_kind": "recovery",
            "review_status": document["version"]["terminal_state"],
            "result_json": json.dumps(result, ensure_ascii=False),
            "effective_finding_count": len(document["findings"]),
            "effective_has_high": any(item.get("severity") in {"high", "critical"}
                                      for item in document["findings"]),
            "review_error": None, "correlation_id": f"recovery-{row['recovery_id']}"}


def finish_delivery(store: Store, delivery: dict[str, Any], error: str | None,
                    retryable: bool = True) -> None:
    """仅匹配本次执行令牌；响应不确定仍可能造成外部重复，不承诺机器人绝对幂等。"""

    with store.connection() as db:
        db.execute("""UPDATE review_recovery_deliveries SET
            status=CASE WHEN ? IS NULL THEN 'sent'
                WHEN ? OR attempts>=5 THEN 'failed' ELSE 'pending' END,
            sent_at=CASE WHEN ? IS NULL THEN CURRENT_TIMESTAMP ELSE sent_at END,
            error=?,next_run_at=datetime('now',printf('+%d seconds',min(300,attempts*attempts*10)))
            WHERE id=? AND status='sending' AND execution_token=?""",
            (error, not retryable, error, error[:500] if error else None,
             delivery["id"], delivery["execution_token"]))


def retry_delivery(store: Store, delivery_id: int) -> bool:
    """只重发仍属于当前源的失败通知，成功通知不自动重发，也不复活旧根尝试。"""

    with store.connection() as db:
        row = db.execute("""UPDATE review_recovery_deliveries SET status='pending',attempts=0,
            error=NULL,next_run_at=CURRENT_TIMESTAMP WHERE id=? AND status='failed'
            AND EXISTS (SELECT 1 FROM review_jobs j WHERE j.id=job_id
            AND j.attempts=source_attempt AND j.status='partial' AND j.cancel_requested=0
            )""", (delivery_id,))
        return row.rowcount == 1


def delivery_current(store: Store, delivery: dict[str, Any]) -> bool:
    """发出网络请求前再核对源与领取令牌；外部在途请求仍无法撤回。"""

    with store.connection() as db:
        current = db.execute("""SELECT 1 FROM review_recovery_deliveries d
            JOIN review_jobs j ON j.id=d.job_id WHERE d.id=? AND d.execution_token=?
            AND d.status='sending' AND j.attempts=d.source_attempt
            AND j.status='partial' AND j.cancel_requested=0""",
            (delivery["id"], delivery["execution_token"])).fetchone()
        if current is None:
            db.execute("UPDATE review_recovery_deliveries SET status='superseded' "
                       "WHERE id=? AND execution_token=? AND status='sending'",
                       (delivery["id"], delivery["execution_token"]))
        return current is not None
