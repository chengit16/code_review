"""持久化协调器身份、执行槽及心跳；锁为恢复栅栏，过期心跳本身不授予抢占权。"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from ocr_manager.scheduler_config import read_scheduler_config

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
        db.execute("""UPDATE worker_execution_slots SET state='stopped',
            heartbeat_at=CURRENT_TIMESTAMP,finished_at=CURRENT_TIMESTAMP""")
        for lane in LANES:
            db.execute("""INSERT INTO worker_execution_slots
                (slot_id,lane,slot_index,owner,pid,state)
                VALUES(?,?,1,?,?,'idle') ON CONFLICT(slot_id) DO UPDATE SET
                owner=excluded.owner,pid=excluded.pid,state='idle',task_kind=NULL,task_id=NULL,
                repository_id=NULL,heartbeat_at=CURRENT_TIMESTAMP,finished_at=CURRENT_TIMESTAMP""",
                       (lane, lane, owner, os.getpid()))
        db.execute("""UPDATE worker_scheduler_settings SET applied_concurrency=NULL,
            applied_version=NULL,applied_owner=? WHERE id=1""", (owner,))


def apply_capacity(store: Store, owner: str, concurrency: int, version: int) -> None:
    """先登记独立模型槽再确认应用；旧 owner 无权确认，新上限不终止现有执行。"""

    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        identity = db.execute("SELECT owner FROM worker_execution_slots WHERE slot_id='model'")\
            .fetchone()
        if identity is None or identity["owner"] != owner:
            raise RuntimeError("执行槽身份不匹配，拒绝应用并发配置")
        for index in range(2, concurrency + 1):
            db.execute("""INSERT INTO worker_execution_slots
                (slot_id,lane,slot_index,owner,pid,state) VALUES(?,'model',?,?,?,'idle')
                ON CONFLICT(slot_id) DO UPDATE SET owner=excluded.owner,pid=excluded.pid,
                state=CASE WHEN worker_execution_slots.owner=excluded.owner
                  THEN worker_execution_slots.state ELSE 'idle' END,
                heartbeat_at=CURRENT_TIMESTAMP""", (f"model:{index}", index, owner, os.getpid()))
        db.execute("""UPDATE worker_scheduler_settings SET applied_concurrency=?,
            applied_version=?,applied_owner=? WHERE id=1""", (concurrency, version, owner))


def start_slot(store: Store, owner: str, lane: str, kind: str,
               task: dict[str, Any]) -> int:
    """领取已经提交后登记执行身份；中间崩溃由 running 任务的独占恢复处理。"""

    with store.connection() as db:
        row = db.execute("""UPDATE worker_execution_slots SET generation=generation+1,
            task_kind=?,task_id=?,repository_id=?,state='running',started_at=CURRENT_TIMESTAMP,
            heartbeat_at=CURRENT_TIMESTAMP,finished_at=NULL
            WHERE slot_id=? AND owner=? AND state='idle' RETURNING generation""",
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
            WHERE owner=? AND slot_id=? AND generation=? AND state='running'""",
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
            AS heartbeat_age_seconds FROM worker_execution_slots ORDER BY lane,slot_index""")]
        applied = db.execute("SELECT applied_concurrency,applied_version,applied_owner "
                             "FROM worker_scheduler_settings WHERE id=1").fetchone()
    config = read_scheduler_config(store)
    live = any(slot["owner"] == applied["applied_owner"] and slot["state"] in {"idle", "running"}
               and slot["heartbeat_age_seconds"] <= 15 for slot in slots)
    running = sum(slot["lane"] == "model" and slot["state"] == "running" for slot in slots)
    limit = applied["applied_concurrency"] if live else None
    return {"model_task_concurrency": config["model_task_concurrency"],
            "config_version": config["version"], "applied_concurrency": limit,
            "applied_version": applied["applied_version"] if live else None,
            "running_model_tasks": running, "draining": limit is not None and running > limit,
            "slots": slots,
            "recovery_policy": "exclusive_process_fence"}
