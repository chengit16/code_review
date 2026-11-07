"""注册管理员专用的平台改进接口；协议层不直接操作数据库或执行外部任务。"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request

from ocr_manager.improvement_archive_contracts import ArchiveChange, ArchiveFilter
from ocr_manager.improvement_archives import change_archive
from ocr_manager.improvement_contracts import (
    ImprovementCategory,
    ImprovementCreate,
    ImprovementHistory,
    ImprovementKind,
    ImprovementPage,
    ImprovementRecord,
    ImprovementStatus,
    ImprovementUpdate,
)
from ocr_manager.improvement_maintenance import maintenance_status, set_maintenance_policy
from ocr_manager.improvement_maintenance_contracts import MaintenancePolicy, MaintenanceStatus
from ocr_manager.improvement_summary import summarize_improvements
from ocr_manager.improvement_summary_contracts import ImprovementSummary
from ocr_manager.improvements import (
    create_improvement,
    get_improvement,
    improvement_history,
    list_improvements,
    update_improvement,
)

if TYPE_CHECKING:
    from ocr_manager.config import Settings
    from ocr_manager.storage import Store


def register_improvements(app: FastAPI, store: Store, admin: Any, settings: Settings) -> None:
    """沿用会话鉴权，再限制管理员读写，避免只读账号访问内部排障记录。"""

    def authorize(request: Request) -> None:
        if request.state.identity["role"] != "admin":
            raise HTTPException(403, "只有管理员可以访问问题与改进记录")

    dependencies = [admin, Depends(authorize)]

    @app.get("/api/improvement-maintenance", dependencies=dependencies,
             response_model=MaintenanceStatus)
    def maintenance() -> MaintenanceStatus:
        """管理员只读运行状态和候选预览，不执行文件扫描或触发业务任务。"""

        return maintenance_status(store, settings)

    @app.put("/api/improvement-maintenance", dependencies=dependencies,
             response_model=MaintenanceStatus)
    def maintenance_update(payload: MaintenancePolicy) -> MaintenanceStatus:
        """仅保存归档策略，来源仍由服务器配置；后台下一轮才执行。"""

        try:
            set_maintenance_policy(store, payload)
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
        return maintenance_status(store, settings)

    @app.get("/api/improvement-summary", dependencies=dependencies,
             response_model=ImprovementSummary)
    def summary(start_date: date | None = None, end_date: date | None = None,
                category: ImprovementCategory | None = None) -> ImprovementSummary:
        """当前累计与活动窗口分开返回；只读账号不能通过统计读取平台内部信息。"""

        try:
            return summarize_improvements(store, start_date, end_date, category)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.get("/api/improvements", dependencies=dependencies, response_model=ImprovementPage)
    def listing(status: ImprovementStatus | None = None, kind: ImprovementKind | None = None,
                category: ImprovementCategory | None = None, q: str = Query("", max_length=200),
                page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
                archive: ArchiveFilter = "active"
                ) -> ImprovementPage:
        """分页搜索平台问题，不混入 OCR 发现的问题表。"""

        return list_improvements(store, status, kind, category, q, page, page_size, archive)

    @app.post("/api/improvements", dependencies=dependencies,
              response_model=ImprovementRecord, status_code=201)
    def create(payload: ImprovementCreate, request: Request) -> ImprovementRecord:
        """创建记录并保存初始历史；同键同内容重试不会重复创建。"""

        try:
            return create_improvement(store, payload, request.state.identity["username"])
        except ValueError as error:
            raise HTTPException(409, str(error)) from error

    @app.get("/api/improvements/{record_id}", dependencies=dependencies,
             response_model=ImprovementRecord)
    def detail(record_id: int) -> ImprovementRecord:
        """返回服务端当前记录；不推断尚未确认的部署状态。"""

        try:
            return get_improvement(store, record_id)
        except LookupError as error:
            raise HTTPException(404, str(error)) from error

    @app.put("/api/improvements/{record_id}", dependencies=dependencies,
             response_model=ImprovementRecord)
    def update(record_id: int, payload: ImprovementUpdate, request: Request) -> ImprovementRecord:
        """保存版本化进展；冲突不写入摘要或历史。"""

        try:
            return update_improvement(store, record_id, payload, request.state.identity["username"])
        except LookupError as error:
            raise HTTPException(404, str(error)) from error
        except ValueError as error:
            raise HTTPException(409, str(error)) from error

    @app.get("/api/improvements/{record_id}/history", dependencies=dependencies,
             response_model=ImprovementHistory)
    def history(record_id: int, page: int = Query(1, ge=1),
                page_size: int = Query(25, ge=1, le=100)) -> ImprovementHistory:
        """分页读取历史快照，保留操作者与每次处理说明。"""

        try:
            return improvement_history(store, record_id, page, page_size)
        except LookupError as error:
            raise HTTPException(404, str(error)) from error

    @app.post("/api/improvements/{record_id}/archive", dependencies=dependencies,
              response_model=ImprovementRecord)
    def archive_change(record_id: int, payload: ArchiveChange,
                       request: Request) -> ImprovementRecord:
        """显式归档或恢复，管理员身份、版本及原因均由服务端约束。"""

        try:
            return change_archive(store, "record", record_id, payload,
                           request.state.identity["username"])
        except LookupError as error:
            raise HTTPException(404, str(error)) from error
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
