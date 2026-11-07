"""调度配置管理接口；继承管理权限，只保存版本化容量，不执行评审。"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from ocr_manager.scheduler_config import (
    SchedulerConfigConflict,
    read_scheduler_config,
    save_scheduler_config,
)
from ocr_manager.storage import Store


class SchedulerConfigRequest(BaseModel):
    """严格整数边界；拒绝布尔值、隐式字符串转换和未知配置键。"""

    model_config = ConfigDict(extra="forbid")
    model_task_concurrency: int = Field(strict=True, ge=1, le=10)
    version: int = Field(strict=True, ge=1)


def register_scheduler_api(app: FastAPI, store: Store, admin: Any) -> None:
    """写操作由既有角色鉴权及管理审计保护，版本冲突不自动重放。"""

    @app.get("/api/worker-scheduler/config", dependencies=[admin])
    def read() -> dict[str, int]:
        """读取期望容量，与监控中的已应用容量分别展示。"""

        return read_scheduler_config(store)

    @app.put("/api/worker-scheduler/config", dependencies=[admin])
    def save(payload: SchedulerConfigRequest, request: Request) -> dict[str, int]:
        """只保存用户明确提交的容量；Worker 下一轮应用，降低时排空不强杀。"""

        try:
            return save_scheduler_config(store, payload.model_task_concurrency,
                                         payload.version, request.state.identity["username"])
        except SchedulerConfigConflict as error:
            raise HTTPException(409, detail={"code": "scheduler_config_conflict",
                "message": "并发配置已被修改，草稿已保留；请刷新配置后重新核对并保存"}) from error
