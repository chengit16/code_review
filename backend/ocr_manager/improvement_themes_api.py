"""注册优化主题接口；主题与问题记录分离建模并由显式编号关联。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request

from ocr_manager.improvement_archive_contracts import ArchiveChange, ArchiveFilter
from ocr_manager.improvement_archives import change_archive
from ocr_manager.improvement_contracts import ImprovementCategory
from ocr_manager.improvement_theme_contracts import (
    ImprovementThemeCreate,
    ImprovementThemeHistory,
    ImprovementThemePage,
    ImprovementThemeRecord,
    ImprovementThemeStatus,
    ImprovementThemeUpdate,
)
from ocr_manager.improvement_themes import (
    create_theme,
    get_theme,
    list_themes,
    theme_history,
    update_theme,
)

if TYPE_CHECKING:
    from ocr_manager.storage import Store


def register_improvement_themes(app: FastAPI, store: Store, admin: Any) -> None:
    """与问题台账共享管理员会话；只读账号不能读取平台优化策略。"""

    def authorize(request: Request) -> None:
        if request.state.identity["role"] != "admin":
            raise HTTPException(403, "只有管理员可以访问优化主题")

    dependencies = [admin, Depends(authorize)]

    @app.get("/api/improvement-themes", dependencies=dependencies,
             response_model=ImprovementThemePage)
    def listing(status: ImprovementThemeStatus | None = None,
                category: ImprovementCategory | None = None,
                q: str = Query("", max_length=200), page: int = Query(1, ge=1),
                page_size: int = Query(25, ge=1, le=100),
                improvement_id: int | None = Query(None, gt=0),
                archive: ArchiveFilter = "active") -> ImprovementThemePage:
        """按状态、类别和文字筛选，阶段与问题关联一并返回。"""

        return list_themes(store, status, category, q, page, page_size, improvement_id, archive)

    @app.post("/api/improvement-themes", dependencies=dependencies,
              response_model=ImprovementThemeRecord, status_code=201)
    def create(payload: ImprovementThemeCreate, request: Request) -> ImprovementThemeRecord:
        """创建主题、阶段、关联和历史；同键同内容重试幂等。"""

        try:
            return create_theme(store, payload, request.state.identity["username"])
        except ValueError as error:
            raise HTTPException(409, str(error)) from error

    @app.get("/api/improvement-themes/{theme_id}", dependencies=dependencies,
             response_model=ImprovementThemeRecord)
    def detail(theme_id: int) -> ImprovementThemeRecord:
        """返回有序阶段及当前显式关联的记录编号。"""

        try:
            return get_theme(store, theme_id)
        except LookupError as error:
            raise HTTPException(404, str(error)) from error

    @app.put("/api/improvement-themes/{theme_id}", dependencies=dependencies,
             response_model=ImprovementThemeRecord)
    def update(theme_id: int, payload: ImprovementThemeUpdate,
               request: Request) -> ImprovementThemeRecord:
        """版本化替换摘要、阶段与关联，任何校验失败整体不写。"""

        try:
            return update_theme(store, theme_id, payload, request.state.identity["username"])
        except LookupError as error:
            raise HTTPException(404, str(error)) from error
        except ValueError as error:
            raise HTTPException(409, str(error)) from error

    @app.get("/api/improvement-themes/{theme_id}/history", dependencies=dependencies,
             response_model=ImprovementThemeHistory)
    def history(theme_id: int, page: int = Query(1, ge=1),
                page_size: int = Query(25, ge=1, le=100)) -> ImprovementThemeHistory:
        """分页返回阶段快照及历史问题关联，保持旧方案可追溯。"""

        try:
            return theme_history(store, theme_id, page, page_size)
        except LookupError as error:
            raise HTTPException(404, str(error)) from error

    @app.post("/api/improvement-themes/{theme_id}/archive", dependencies=dependencies,
              response_model=ImprovementThemeRecord)
    def archive_change(theme_id: int, payload: ArchiveChange,
                       request: Request) -> ImprovementThemeRecord:
        """显式归档或恢复，管理员身份、版本及原因均由服务端约束。"""

        try:
            return change_archive(store, "theme", theme_id, payload,
                           request.state.identity["username"])
        except LookupError as error:
            raise HTTPException(404, str(error)) from error
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
