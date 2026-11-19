"""注册任务详情的双评审接口；权限沿用管理台，HTTP 只执行 SQLite 用例。"""

from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.params import Depends

from ocr_manager.agent_comparison_contracts import (
    AgentComparison,
    ComparisonCreate,
    ComparisonCreated,
    ComparisonIndex,
    CurationSnapshot,
    CurationUpdate,
)
from ocr_manager.agent_comparisons import (
    ComparisonConflict,
    comparison_detail,
    comparison_index,
    create_comparison,
    save_curation,
)
from ocr_manager.config import Settings
from ocr_manager.storage import Store

PATH = "/api/jobs/{job_id}/agent-comparisons"


def register_agent_comparison_api(app: FastAPI, store: Store, settings: Settings,
                                  access: Depends) -> None:
    """读者可查看固定证据；修改使用现有管理员授权和管理审计。"""

    @app.get(PATH, dependencies=[access])
    def history(job_id: int, response: Response,
                before_id: Annotated[int | None, Query(ge=1)] = None,
                limit: Annotated[int, Query(ge=1, le=100)] = 50) -> ComparisonIndex:
        """读取任务级历史及当前版本的运行资格。"""

        response.headers["Cache-Control"] = "no-store"
        try:
            return comparison_index(store, settings, job_id, before_id, limit)
        except LookupError as error:
            raise HTTPException(404, str(error)) from error

    @app.get(f"{PATH}/{{comparison_id}}", dependencies=[access])
    def detail(job_id: int, comparison_id: int, response: Response,
               curation_version: Annotated[int | None, Query(ge=0)] = None) -> AgentComparison:
        """限定到任务内的比较及裁定版本，不回退到另一条任务或当前结果。"""

        response.headers["Cache-Control"] = "no-store"
        try:
            return comparison_detail(store, job_id, comparison_id, curation_version)
        except LookupError as error:
            raise HTTPException(404, str(error)) from error
        except ValueError as error:
            raise HTTPException(409, {"code": "comparison_evidence_invalid",
                                     "message": "固定版本证据不可用"}) from error

    @app.post(PATH, dependencies=[access], status_code=202)
    def create(job_id: int, payload: ComparisonCreate) -> ComparisonCreated:
        """返回已登记的 Agent 尝试，浏览器等待 Worker 领取及执行。"""

        try:
            return ComparisonCreated(id=create_comparison(store, settings, job_id, payload))
        except LookupError as error:
            raise HTTPException(404, str(error)) from error
        except ComparisonConflict as error:
            raise HTTPException(409, {"code": error.code, "message": str(error)}) from error

    @app.put(f"{PATH}/{{comparison_id}}/curation", dependencies=[access])
    def update(job_id: int, comparison_id: int, payload: CurationUpdate,
               request: Request) -> CurationSnapshot:
        """按起始版本保存人审，冲突保留既有裁定并由前端管理草稿。"""

        try:
            return save_curation(store, job_id, comparison_id, payload,
                                 request.state.identity["username"])
        except LookupError as error:
            raise HTTPException(404, str(error)) from error
        except ComparisonConflict as error:
            raise HTTPException(409, {"code": error.code, "message": str(error)}) from error
        except ValueError as error:
            raise HTTPException(409, {"code": "comparison_evidence_invalid",
                                     "message": "固定版本证据不可用"}) from error
