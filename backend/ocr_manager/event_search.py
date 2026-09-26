"""事件全量检索与补审申请；GitLab 查询始终在独立 Worker 执行。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from ocr_manager.storage import Store

EVENT_SEARCH_MIGRATION = """
CREATE TABLE mr_backfills (
 id INTEGER PRIMARY KEY,
 repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
 since TEXT NOT NULL, until TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued',
 scanned INTEGER NOT NULL DEFAULT 0, enqueued INTEGER NOT NULL DEFAULT 0,
 error TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 finished_at TEXT
);
CREATE INDEX idx_events_search ON merge_events(repository_id,status,created_at,id DESC);
"""


class BackfillRequest(BaseModel):
    """时间范围最多 31 天，避免一个运维命令占用 Worker 太久。"""

    model_config = ConfigDict(extra="forbid")
    since: datetime
    until: datetime


def normalized_range(start: datetime, end: datetime) -> tuple[str, str]:
    """所有补审与搜索区间使用 UTC；日期范围非法时拒绝而非交换。"""

    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("时间必须包含时区")
    if end <= start or (end - start).days > 31:
        raise ValueError("时间范围须大于零且不超过 31 天")
    return (start.astimezone(UTC).isoformat(), end.astimezone(UTC).isoformat())


def register_event_search(app: FastAPI, store: Store, admin: Any) -> None:
    """分页结果包含关联任务数量，补审命令只持久化申请。"""

    @app.get("/api/event-search", dependencies=[admin])
    def search(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
               repository_id: int | None = Query(None, gt=0),
               status: str | None = Query(None, max_length=30),
               mr_iid: int | None = None,
               since: datetime | None = None, until: datetime | None = None) -> dict[str, Any]:
        """返回全量事件的稳定分页，任务数量和最新任务 ID 同事务读取。"""

        if since and until and since > until:
            raise HTTPException(422, "起始时间不能晚于结束时间")
        if (since and since.tzinfo is None) or (until and until.tzinfo is None):
            raise HTTPException(422, "时间必须包含时区")
        conditions: list[str] = []
        args: list[Any] = []
        for name, filter_value in (("repository_id", repository_id), ("status", status),
                                   ("mr_iid", mr_iid)):
            if filter_value is not None:
                conditions.append(f"e.{name}=?")
                args.append(filter_value)
        for operator, time_value in ((">=", since), ("<=", until)):
            if time_value:
                conditions.append(f"e.created_at {operator} ?")
                args.append(time_value.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S"))
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        with store.connection() as db:
            db.execute("BEGIN")
            total = db.execute(f"SELECT COUNT(*) FROM merge_events e{where}", args).fetchone()[0]
            rows = db.execute(f"""SELECT e.*, COUNT(j.id) AS job_count, MAX(j.id) AS latest_job_id
                FROM merge_events e LEFT JOIN review_jobs j ON j.event_id=e.id{where}
                GROUP BY e.id ORDER BY e.id DESC LIMIT ? OFFSET ?""",
                (*args, page_size, (page-1)*page_size)).fetchall()
        return {"items": [dict(row) for row in rows], "total": total,
                "page": page, "page_size": page_size}

    @app.post("/api/repositories/{repository_id}/mrs/backfill", dependencies=[admin])
    def enqueue(repository_id: int, payload: BackfillRequest) -> dict[str, int]:
        """只保存补审范围；网页请求不调用 GitLab。"""

        try:
            start, end = normalized_range(payload.since, payload.until)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        with store.connection() as db:
            if not db.execute("SELECT 1 FROM repositories WHERE id=? AND enabled=1",
                              (repository_id,)).fetchone():
                raise HTTPException(409, "项目不存在或已暂停")
            cursor = db.execute("INSERT INTO mr_backfills(repository_id,since,until) VALUES(?,?,?)",
                                (repository_id, start, end))
        assert cursor.lastrowid is not None
        return {"id": cursor.lastrowid}

    @app.get("/api/mr-backfills", dependencies=[admin])
    def list_backfills() -> list[dict[str, Any]]:
        """最近申请及错误供管理员确认；不包含 API 凭据。"""

        with store.connection() as db:
            return [dict(row) for row in db.execute(
                "SELECT * FROM mr_backfills ORDER BY id DESC LIMIT 100")]
