"""注册管理员补审后端接口；仅操作 SQLite，不在 HTTP 中执行 Git、OCR 或通知。"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, Response

from ocr_manager.config import Settings
from ocr_manager.recovery_budget import BudgetAuthorization, authorize_budget, read_gate
from ocr_manager.review_conclusion_contracts import ConclusionDocument
from ocr_manager.review_conclusions import attach_conclusions, read_conclusion
from ocr_manager.review_effective import EFFECTIVE
from ocr_manager.review_recovery_contracts import (
    RecoveryCandidateResponse,
    RecoveryCreate,
    RecoveryDelivery,
    RecoveryEligibility,
    RecoveryRecord,
)
from ocr_manager.review_recovery_domain import RecoveryConflict
from ocr_manager.review_recovery_store import cancel, eligibility, enqueue, public_record
from ocr_manager.storage import Store


def register_recovery_api(app: FastAPI, store: Store, settings: Settings, admin: Any) -> None:
    """继承现有服务端授权；部分任务默认可申请，仍检查来源和预算，初审与有效版本分列。"""

    @app.get("/api/jobs/{job_id}/recovery-eligibility", dependencies=[admin],
             response_model=RecoveryEligibility)
    def get_eligibility(job_id: int) -> RecoveryEligibility:
        """查询数据库候选资格，不从工件或状态推测缺失的失败范围。"""

        return eligibility(store, settings, job_id)

    @app.put("/api/jobs/{job_id}/recovery-budget", dependencies=[admin])
    def set_budget(
        job_id: int, payload: BudgetAuthorization, request: Request
    ) -> dict[str, str | int]:
        """管理员显式追加任务预算；不重置历史、不自动排队。"""

        try:
            authorize_budget(store, job_id, payload, request.state.identity["username"])
        except RecoveryConflict as error:
            raise HTTPException(409, {"code": str(error)}) from error
        return {"status": "saved", "version": payload.expected_version + 1}

    @app.post("/api/jobs/{job_id}/recoveries", dependencies=[admin],
              response_model=RecoveryRecord, status_code=202)
    def create(job_id: int, payload: RecoveryCreate, request: Request) -> dict[str, Any]:
        """成功仅表示独立批次入队；同键重放返回原批次，不能宣称审核完成。"""

        try:
            recovery_id = enqueue(store, settings, job_id, payload,
                                  request.state.identity["username"])
        except RecoveryConflict as error:
            raise HTTPException(409, {"code": str(error)}) from error
        with store.connection() as db:
            row = db.execute("SELECT * FROM review_recoveries WHERE id=?",
                             (recovery_id,)).fetchone()
        if row is None:
            raise HTTPException(409, {"code": "job_removed"})
        return public_record(dict(row))

    @app.get("/api/jobs/{job_id}/recoveries", dependencies=[admin],
             response_model=list[RecoveryRecord])
    def history(job_id: int, before_id: int | None = Query(None, ge=1),
                limit: int = Query(50, ge=1, le=100)) -> list[dict[str, Any]]:
        """按稳定批次 ID 分页，历史只返回安全结果用量，不返回工件或完整快照。"""

        with store.connection() as db:
            rows = db.execute("""SELECT * FROM review_recoveries WHERE job_id=?
                AND (? IS NULL OR id<?) ORDER BY id DESC LIMIT ?""",
                (job_id, before_id, before_id, limit)).fetchall()
            records = [public_record(dict(row)) for row in rows]
            evidence = {row["recovery_id"]: read_gate(row).model_dump() for row in db.execute(
                """SELECT e.* FROM review_recovery_budget_evidence e JOIN review_recoveries r
                ON r.id=e.recovery_id WHERE r.job_id=? AND (? IS NULL OR r.id<?)
                ORDER BY r.id DESC LIMIT ?""", (job_id, before_id, before_id, limit))}
        for record in records:
            if record["id"] in evidence:
                record["budget_gate"] = evidence[record["id"]]
        return records

    @app.get("/api/jobs/{job_id}/recovery-candidate", dependencies=[admin],
             response_model=RecoveryCandidateResponse)
    def candidate(job_id: int) -> dict[str, Any]:
        """同一读快照返回候选与就绪状态；仅已完整校验提升的版本参与消费者。"""

        with store.connection() as db:
            db.execute("BEGIN")
            jobs: list[dict[str, Any]] = [{"id": job_id}]
            attach_conclusions(db, jobs)
            ready = db.execute(f"SELECT 1 FROM ({EFFECTIVE}) WHERE job_id=?",
                               (job_id,)).fetchone() is not None
        return {"consumer_integration_ready": ready,
                "candidate": jobs[0]["conclusions"]["candidate"]}

    @app.get("/api/jobs/{job_id}/conclusion", dependencies=[admin],
             response_model=ConclusionDocument)
    def conclusion(job_id: int, response: Response, source_attempt: int | None = Query(None, ge=1),
                   revision: int | None = Query(None, ge=0)) -> ConclusionDocument:
        """显式版本只读复核，稳定来源 ID 不与旧反馈/发布索引混用，历史不会回填。"""

        if source_attempt is not None and revision is None:
            raise HTTPException(422, {"code": "explicit_revision_required"})
        response.headers["Cache-Control"] = "no-store"
        try:
            with store.connection() as db:
                db.execute("BEGIN")
                document = read_conclusion(
                    db, job_id, source_attempt=source_attempt, revision=revision)
                effective = db.execute(f"SELECT revision FROM ({EFFECTIVE}) WHERE job_id=?",
                                       (job_id,)).fetchone()
                if (effective and document.is_current_source and
                        effective["revision"] == document.version.revision):
                    document.consumer_integration_ready = True
                    document.role = "effective"
                return document
        except RecoveryConflict as error:
            raise HTTPException(409, {"code": str(error)}) from error
        except LookupError as error:
            raise HTTPException(404, {"code": "conclusion_not_found"}) from error

    @app.post("/api/review-recoveries/{recovery_id}/cancel", dependencies=[admin])
    def request_cancel(recovery_id: int) -> dict[str, str]:
        """只持久化取消，不直接发送进程信号；终态批次返回冲突。"""

        if not cancel(store, recovery_id):
            raise HTTPException(409, {"code": "recovery_not_active"})
        return {"status": "cancel_requested"}

    @app.get("/api/jobs/{job_id}/recovery-deliveries", dependencies=[admin],
             response_model=list[RecoveryDelivery])
    def deliveries(job_id: int, before_id: int | None = Query(None, ge=1),
                   limit: int = Query(50, ge=1, le=100)) -> list[dict[str, Any]]:
        """分页返回独立通知安全状态，绝不输出冻结发现正文或执行令牌。"""

        with store.connection() as db:
            return [dict(row) for row in db.execute("""SELECT id,source_attempt,revision,
                recovery_id,status,attempts,error,created_at,sent_at FROM review_recovery_deliveries
                WHERE job_id=? AND (? IS NULL OR id<?) ORDER BY id DESC LIMIT ?""",
                (job_id, before_id, before_id, limit))]

    @app.post("/api/recovery-deliveries/{delivery_id}/retry", dependencies=[admin])
    def retry_supplement(delivery_id: int) -> dict[str, str]:
        """显式只重试失败补充通知，不创建补审批次；不创建补审或重跑模型。"""

        from ocr_manager.review_recovery_notifications import retry_delivery

        if not retry_delivery(store, delivery_id):
            raise HTTPException(409, {"code": "supplement_not_retryable"})
        return {"status": "pending"}
