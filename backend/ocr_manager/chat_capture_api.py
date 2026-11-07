"""提供管理员聊天收件箱和可逆关联；绑定仅限本机 CLI，HTTP 不可扩大采集范围。"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request

from ocr_manager.chat_capture_contracts import (
    ChatBindingChange,
    ChatEvent,
    ChatEventLink,
    ChatInbox,
)
from ocr_manager.chat_capture_store import change_binding, inbox, link_event
from ocr_manager.storage import Store


def register_chat_capture(app: FastAPI, store: Store, admin: Any) -> None:
    """注册只读收件箱与管理员更正接口；服务端角色鉴权仍是最终边界。"""

    def authorize(request: Request) -> None:
        if request.state.identity["role"] != "admin":
            raise HTTPException(403, "只有管理员可以查看聊天收件箱")

    dependencies = [admin, Depends(authorize)]

    @app.get("/api/chat-capture", dependencies=dependencies, response_model=ChatInbox)
    def listing(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)) -> ChatInbox:
        """返回绑定健康度与脱敏候选，不返回会话路径、原文或凭据。"""

        return inbox(store, page, page_size)

    @app.put("/api/chat-capture/bindings/{binding_id}", dependencies=dependencies)
    def binding_update(binding_id: int, payload: ChatBindingChange) -> dict[str, str]:
        """只允许暂停/恢复既有绑定；新增绑定必须在本机显式执行 CLI。"""

        try:
            change_binding(store, binding_id, payload)
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
        return {"status": "saved"}

    @app.post(
        "/api/chat-capture/events/{event_id}/link",
        dependencies=dependencies,
        response_model=ChatEvent,
    )
    def event_link(event_id: int, payload: ChatEventLink, request: Request) -> ChatEvent:
        """人工关联、解除或提升候选，保留关联审计且不自动改变验证/部署状态。"""

        try:
            return link_event(store, event_id, payload, request.state.identity["username"])
        except LookupError as error:
            raise HTTPException(404, str(error)) from error
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
