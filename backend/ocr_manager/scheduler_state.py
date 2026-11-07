"""持久化协调器身份、执行槽及心跳；锁为恢复栅栏，过期心跳本身不授予抢占权。"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ocr_manager.storage import Store

SCHEDULER_MIGRATION = """
CREATE TABLE worker_execution_slots (
 lane TEXT PRIMARY KEY CHECK(lane IN ('model','ingress','delivery')),
 owner TEXT NOT NULL,
 generation INTEGER NOT NULL DEFAULT 0,
 task_kind TEXT,
 task_id INTEGER,
 repository_id INTEGER,
 pid INTEGER NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('idle','running','stopped','interrupted')),
 started_at TEXT,
 heartbeat_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 finished_at TEXT,
 CHECK((task_kind IS NULL) = (task_id IS NULL))
);
"""
LANES = ("model", "ingress", "delivery")


def initialize_slots(store: Store, owner: str) -> None:
    """调用方先取得 Worker 独占栅栏并恢复业务任务，才允许切换执行身份。"""

    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        for lane in LANES:
            db.execute("""INSERT INTO worker_execution_slots(lane,owner,pid,state)
                VALUES(?,?,?,'idle') ON CONFLICT(lane) DO UPDATE SET
                owner=excluded.owner,pid=excluded.pid,state='idle',task_kind=NULL,task_id=NULL,
                repository_id=NULL,heartbeat_at=CURRENT_TIMESTAMP,finished_at=CURRENT_TIMESTAMP""",
                       (lane, owner, os.getpid()))


def start_slot(store: Store, owner: str, lane: str, kind: str,
               task: dict[str, Any]) -> int:
    """领取已经提交后登记执行身份；中间崩溃由 running 任务的独占恢复处理。"""

    with store.connection() as db:
        row = db.execute("""UPDATE worker_execution_slots SET generation=generation+1,
            task_kind=?,task_id=?,repository_id=?,state='running',started_at=CURRENT_TIMESTAMP,
            heartbeat_at=CURRENT_TIMESTAMP,finished_at=NULL
            WHERE lane=? AND owner=? AND state='idle' RETURNING generation""",
                         (kind, task["id"], task.get("repository_id"), lane, owner)).fetchone()
        if row is None:
            raise RuntimeError("执行槽身份不匹配，拒绝启动任务")
        return int(row[0])


def finish_slot(store: Store, owner: str, lane: str, generation: int,
                interrupted: bool = False) -> None:
    """按身份和代次更新，迟到执行单元不能释放另一轮执行槽。"""

    with store.connection() as db:
        db.execute("""UPDATE worker_execution_slots SET state=?,
            finished_at=CURRENT_TIMESTAMP,heartbeat_at=CURRENT_TIMESTAMP
            WHERE owner=? AND lane=? AND generation=? AND state='running'""",
                   ("interrupted" if interrupted else "idle", owner, lane, generation))


def heartbeat(store: Store, owner: str) -> None:
    """协调器独立续写心跳，不把正在等待网络的线程误判为失去所有权。"""

    with store.connection() as db:
        db.execute("UPDATE worker_execution_slots SET heartbeat_at=CURRENT_TIMESTAMP WHERE owner=?",
                   (owner,))


def stop_slots(store: Store, owner: str) -> None:
    """线程均已结束才记录停止；业务 running 保留给下一次独占恢复。"""

    with store.connection() as db:
        db.execute("""UPDATE worker_execution_slots SET state='stopped',
            heartbeat_at=CURRENT_TIMESTAMP,finished_at=CURRENT_TIMESTAMP WHERE owner=?""", (owner,))


def scheduler_snapshot(store: Store) -> dict[str, Any]:
    """返回受保护运维页所需的安全执行事实，心跳过期只提示异常，不自动抢占。"""

    with store.connection() as db:
        slots = [dict(row) for row in db.execute("""SELECT *,
            MAX(0,CAST((julianday('now')-julianday(heartbeat_at))*86400 AS INTEGER))
            AS heartbeat_age_seconds FROM worker_execution_slots ORDER BY lane""")]
    return {"model_task_concurrency": 1, "slots": slots,
            "recovery_policy": "exclusive_process_fence"}
