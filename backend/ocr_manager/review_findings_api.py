"""当前有效发现的分页、详情及显式批量反馈；复用质量集合与版本写入，不修改历史处置。"""

from datetime import datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ocr_manager.review_finding_feedback import (
    FeedbackChoice,
    FindingFeedbackVersion,
    write_feedback,
)
from ocr_manager.review_quality import FeedbackFilter, quality_findings
from ocr_manager.review_recovery_domain import RecoveryConflict
from ocr_manager.storage import Store


class FeedbackTarget(FindingFeedbackVersion):
    """显式冻结的发现与来源版本；拒绝客户端提供作者或使用问题编号代替身份。"""

    job_id: int = Field(gt=0, strict=True)
    finding_id: str = Field(min_length=1, max_length=120)


class BatchFeedback(BaseModel):
    """限定批量大小与唯一目标；逐项提交，冲突项保留原记录，不自动重试。"""

    model_config = ConfigDict(extra="forbid")
    targets: list[FeedbackTarget] = Field(min_length=1, max_length=100)
    verdict: FeedbackChoice

    @model_validator(mode="after")
    def unique_targets(self) -> "BatchFeedback":
        """同一发现只能出现一次，避免重复结果或用不同版本覆盖选择。"""

        if len({item.finding_id for item in self.targets}) != len(self.targets):
            raise ValueError("发现目标不能重复")
        return self


def validate_window(since: str | None, until: str | None) -> None:
    """显式 UTC 窗口须成对、规范且不超过九十天；无窗口表示全部历史当前发现。"""

    if since is None and until is None:
        return
    try:
        if since is None or until is None:
            raise ValueError
        start, end = (datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
                      for value in (since, until))
        if (start.strftime("%Y-%m-%d %H:%M:%S") != since
                or end.strftime("%Y-%m-%d %H:%M:%S") != until
                or not timedelta(0) < end - start <= timedelta(days=90)):
            raise ValueError
    except ValueError as error:
        raise HTTPException(422, "请提供成对的 UTC 时间，窗口须大于零且不超过 90 天") from error


def register_review_findings(app: FastAPI, store: Store, admin: Any) -> None:
    """读者可查询，写入继承管理授权；不创建后台任务或触发外部服务。"""

    @app.get("/api/review-findings", dependencies=[admin])
    def listing(repository_id: int | None = Query(None, gt=0),
                feedback: Annotated[FeedbackFilter, Query()] = "all",
                handling: Literal["all", "pending", "handled"] = "pending",
                category: str | None = Query(None, max_length=200),
                severity: str | None = Query(
                    None, pattern="^(critical|high|medium|low|unclassified)$"),
                issue_id: int | None = Query(None, gt=0),
                q: str | None = Query(None, max_length=200),
                since: str | None = None, until: str | None = None,
                page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
                ) -> dict[str, Any]:
        """所有条件先过滤再稳定分页；首页携带原始窗口，不在翻页时重新计算。"""

        validate_window(since, until)
        with store.connection() as db:
            db.execute("BEGIN")
            return quality_findings(db, repository_id, 0, feedback, category, page, page_size,
                                    since, until, severity, handling=handling,
                                    issue_id=issue_id, keyword=q)

    @app.get("/api/review-findings/{finding_id}", dependencies=[admin])
    def detail(finding_id: str) -> dict[str, Any]:
        """详情只读当前有效主身份；来源离开当前版本时明确报错，不跳到其他发现。"""

        with store.connection() as db:
            db.execute("BEGIN")
            result = quality_findings(db, None, 0, "all", None, 1, 1,
                                      finding_id=finding_id, detail=True)
            if not result["items"]:
                raise HTTPException(404, "该发现已不在当前有效结论中，请刷新列表核对历史")
            return dict(result["items"][0])

    @app.post("/api/review-findings/batch-feedback", dependencies=[admin])
    def batch(payload: BatchFeedback, request: Request) -> dict[str, Any]:
        """每项独立版本事务；允许部分成功，返回全部失败身份，客户端不得悄悄换成最新版本。"""

        results = []
        for target in payload.targets:
            try:
                write_feedback(store, target.job_id, target.finding_id, target,
                               payload.verdict, request.state.identity["username"])
                results.append({"finding_id": target.finding_id, "status": "updated"})
            except RecoveryConflict as error:
                results.append({"finding_id": target.finding_id, "status": "conflict",
                                "code": str(error)})
            except LookupError:
                results.append({"finding_id": target.finding_id, "status": "not_found",
                                "code": "finding_or_feedback_not_found"})
        return {"results": results, "updated": sum(row["status"] == "updated" for row in results)}
