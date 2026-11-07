"""注册管理员稳定身份反馈接口；仅编排 SQLite 用例，写入仍校验管理员和当前来源。"""

from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, Response

from ocr_manager.config import Settings
from ocr_manager.review_finding_feedback import (
    FindingFeedbackRecord,
    FindingFeedbackVersion,
    FindingFeedbackWrite,
    Verdict,
    read_feedback,
    write_feedback,
)
from ocr_manager.review_recovery_domain import RecoveryConflict
from ocr_manager.storage import Store


def register_finding_api(app: FastAPI, store: Store, settings: Settings, admin: Any) -> None:
    """继承可信管理员身份；不以按钮可见性代替权限，不提供生产启用入口。"""

    @app.get("/api/jobs/{job_id}/finding-feedback", dependencies=[admin],
             response_model=list[FindingFeedbackRecord])
    def history(job_id: int, response: Response, source_attempt: int = Query(..., ge=1),
                revision: int = Query(..., ge=0)) -> list[FindingFeedbackRecord]:
        """显式版本读取历史反馈；根发现和补审发现都以主身份过滤，无写入副作用。"""

        response.headers["Cache-Control"] = "no-store"
        try:
            with store.connection() as db:
                db.execute("BEGIN")
                return read_feedback(db, job_id, source_attempt, revision)
        except RecoveryConflict as error:
            raise HTTPException(409, {"code": str(error)}) from error
        except LookupError as error:
            raise HTTPException(404, {"code": "conclusion_not_found"}) from error

    def apply(job_id: int, finding_id: str, payload: FindingFeedbackVersion,
              verdict: Verdict | None, request: Request) -> None:
        try:
            write_feedback(store, job_id, finding_id, payload, verdict,
                           request.state.identity["username"])
        except RecoveryConflict as error:
            raise HTTPException(409, {"code": str(error)}) from error
        except LookupError as error:
            raise HTTPException(404, {"code": "finding_or_feedback_not_found"}) from error

    @app.put("/api/jobs/{job_id}/finding-feedback/{finding_id}", dependencies=[admin])
    def put(job_id: int, finding_id: str, payload: FindingFeedbackWrite,
            request: Request) -> dict[str, str]:
        """提交主身份反馈，要求当前源尝试和最新候选版本，操作者由鉴权上下文注入。"""

        apply(job_id, finding_id, payload, payload.verdict, request)
        return {"verdict": payload.verdict}

    @app.delete("/api/jobs/{job_id}/finding-feedback/{finding_id}", dependencies=[admin])
    def clear(job_id: int, finding_id: str, request: Request,
              source_attempt: int = Query(..., ge=1),
              revision: int = Query(..., ge=0)) -> dict[str, str]:
        """撤销要求当前版本，不能用重审前的旧页面重开历史问题；不存在返回 404。"""

        apply(job_id, finding_id, FindingFeedbackVersion(source_attempt=source_attempt,
              revision=revision), None, request)
        return {"status": "deleted"}
