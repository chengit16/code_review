"""维护单 Worker 调度容量与版本；不改变评审快照，不执行外部请求。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ocr_manager.storage import Store

CONCURRENCY_MIGRATION = """
ALTER TABLE worker_execution_slots RENAME TO worker_execution_slots_v38;
CREATE TABLE worker_execution_slots (
 slot_id TEXT PRIMARY KEY,
 lane TEXT NOT NULL CHECK(lane IN ('model','ingress','delivery')),
 slot_index INTEGER NOT NULL CHECK(slot_index BETWEEN 1 AND 10),
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
 UNIQUE(lane,slot_index),
 CHECK(lane='model' OR slot_index=1),
 CHECK((task_kind IS NULL) = (task_id IS NULL))
);
INSERT INTO worker_execution_slots
 SELECT lane,lane,1,owner,generation,task_kind,task_id,repository_id,pid,state,
 started_at,heartbeat_at,finished_at FROM worker_execution_slots_v38;
DROP TABLE worker_execution_slots_v38;
CREATE TABLE worker_scheduler_settings (
 id INTEGER PRIMARY KEY CHECK(id=1),
 model_task_concurrency INTEGER NOT NULL DEFAULT 1 CHECK(model_task_concurrency BETWEEN 1 AND 10),
 version INTEGER NOT NULL DEFAULT 1,
 applied_concurrency INTEGER CHECK(applied_concurrency BETWEEN 1 AND 10),
 applied_version INTEGER,
 applied_owner TEXT,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO worker_scheduler_settings(id) VALUES(1);
CREATE TABLE worker_scheduler_changes (
 id INTEGER PRIMARY KEY,
 previous_concurrency INTEGER NOT NULL,
 model_task_concurrency INTEGER NOT NULL,
 version INTEGER NOT NULL UNIQUE,
 actor TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

# 业务 running 与执行槽共同保护仓库；取消或删除业务行不能提前释放仍在退出的执行单元。
BUSY_MODEL_REPOSITORIES = """
 SELECT repository_id FROM worker_execution_slots
 WHERE lane='model' AND state='running' AND repository_id IS NOT NULL
 UNION SELECT repository_id FROM review_jobs WHERE status='running'
 UNION SELECT repository_id FROM premerge_reviews WHERE status='running'
 UNION SELECT j.repository_id FROM review_recoveries b
 JOIN review_jobs j ON j.id=b.job_id WHERE b.status='running'
 UNION SELECT repository_id FROM connection_checks
 WHERE kind='model' AND status='running' AND repository_id IS NOT NULL
"""


class SchedulerConfigConflict(Exception):
    """页面读取的版本已过时，必须保留草稿并重新核对，不能自动覆盖。"""


def read_scheduler_config(store: Store) -> dict[str, int]:
    """只返回调度上限和版本，不把保存当作 Worker 已应用。"""

    with store.connection() as db:
        row = db.execute("SELECT model_task_concurrency,version FROM worker_scheduler_settings "
                         "WHERE id=1").fetchone()
    return dict(row)


def save_scheduler_config(store: Store, concurrency: int, version: int,
                          actor: str) -> dict[str, int]:
    """短事务内比较版本并记录前后值；不修改任务、模型参数或补审授权。"""

    if type(concurrency) is not int or not 1 <= concurrency <= 10:
        raise ValueError("模型任务并发数必须为 1～10 的整数")
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        previous = db.execute("SELECT model_task_concurrency,version "
                              "FROM worker_scheduler_settings WHERE id=1").fetchone()
        if previous["version"] != version:
            raise SchedulerConfigConflict()
        db.execute("""UPDATE worker_scheduler_settings SET model_task_concurrency=?,
            version=version+1,updated_at=CURRENT_TIMESTAMP WHERE id=1""", (concurrency,))
        db.execute("""INSERT INTO worker_scheduler_changes
            (previous_concurrency,model_task_concurrency,version,actor) VALUES(?,?,?,?)""",
                   (previous["model_task_concurrency"], concurrency, version + 1, actor))
    return {"model_task_concurrency": concurrency, "version": version + 1}
