"""项目级执行参数管理；当前在途任务保持原快照，不接受中途改写。"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ocr_manager.project_limits import get_limits
from ocr_manager.storage import Store


class ProjectLimits(BaseModel):
    """空值继承全局模型或进程超时，预算及文件上限为无限制。"""

    model_config = ConfigDict(extra="forbid")
    model_profile_id: int | None = Field(None, gt=0)
    timeout_seconds: int | None = Field(None, ge=60, le=14400)
    max_files: int | None = Field(None, ge=1, le=5000)
    max_tokens_budget: int | None = Field(None, ge=1000, le=100000000)


def register_project_limits(app: FastAPI, store: Store, admin: Any) -> None:
    """模型配置可独立维护，项目只保存引用和审查上限。"""

    @app.get("/api/repositories/{repository_id}/limits", dependencies=[admin])
    def read(repository_id: int) -> dict[str, int | None]:
        """返回项目当前覆盖值，不回显模型凭据。"""

        if store.get_repository(repository_id) is None:
            raise HTTPException(404, "项目不存在")
        return get_limits(store, repository_id)

    @app.put("/api/repositories/{repository_id}/limits", dependencies=[admin])
    def save(repository_id: int, payload: ProjectLimits) -> dict[str, int | None]:
        """队列运行中拒绝改动，避免任务执行时的快照和参数分离。"""

        with store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM repositories WHERE id=?", (repository_id,)).fetchone():
                raise HTTPException(404, "项目不存在")
            if payload.model_profile_id and not db.execute(
                "SELECT 1 FROM model_profiles WHERE id=?", (payload.model_profile_id,)
            ).fetchone():
                raise HTTPException(409, "模型配置不存在")
            busy = db.execute("""SELECT EXISTS(SELECT 1 FROM review_jobs WHERE repository_id=?
                              AND status IN ('queued','running')) OR EXISTS(
                              SELECT 1 FROM merge_events WHERE repository_id=?
                              AND status IN ('queued','running'))""",
                              (repository_id, repository_id)).fetchone()[0]
            if busy:
                raise HTTPException(409, "项目队列运行期间不能修改评审参数")
            db.execute("""INSERT INTO project_review_limits
                       (repository_id,model_profile_id,timeout_seconds,max_files,max_tokens_budget)
                       VALUES(?,?,?,?,?) ON CONFLICT(repository_id) DO UPDATE SET
                       model_profile_id=excluded.model_profile_id,
                       timeout_seconds=excluded.timeout_seconds,max_files=excluded.max_files,
                       max_tokens_budget=excluded.max_tokens_budget""",
                       (repository_id, *payload.model_dump().values()))
        return get_limits(store, repository_id)
