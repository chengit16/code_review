"""单协调器将已持久化任务交给三个有界执行槽；不增加模型并发，不按心跳抢占。"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from types import TracebackType
from typing import Any

from ocr_manager.artifact_lock import artifact_lock
from ocr_manager.config import Settings
from ocr_manager.execution_guard import WorkerStopping, check_stopping, stopping_scope
from ocr_manager.scheduler_state import (
    finish_slot,
    heartbeat,
    initialize_slots,
    start_slot,
    stop_slots,
)
from ocr_manager.storage import Store

Task = dict[str, Any]
Claim = Callable[[], Task | None]
Execute = Callable[[Task], None]


@dataclass
class Action:
    """固定领取与执行配对；载荷为数据库记录，密钥仍由执行阶段读取。"""

    kind: str
    claim: Claim
    execute: Execute


@dataclass
class Lane:
    """每类最多一个在途单元；轮转游标只决定调度机会，不替代 SQLite 业务事实。"""

    name: str
    actions: list[Action]
    executor: ThreadPoolExecutor
    cursor: int = 0
    future: Future[None] | None = None
    generation: int = 0


class WorkerScheduler:
    """须在 worker_lock 及独占恢复后启动；线程不共享 SQLite 连接，停止后等待外部命令清理。"""

    def __init__(self, store: Store, settings: Settings) -> None:
        from ocr_manager import worker
        from ocr_manager.checks import run_connection_check
        from ocr_manager.publications import next_publication
        from ocr_manager.review_recovery_notifications import claim_delivery
        from ocr_manager.review_recovery_store import claim as claim_recovery
        from ocr_manager.review_recovery_worker import execute_recovery

        self.store, self.settings = store, settings
        self.owner = uuid.uuid4().hex
        self.stopping = threading.Event()
        self.last_repository_id: int | None = None
        self.last_event_repository: int | None = None
        self.last_premerge_repository: int | None = None
        self.last_heartbeat = 0.0
        self.closed = False

        def action(kind: str, claim: Claim,
                   execute: Callable[[Store, Settings, Task], None]) -> Action:
            return Action(kind, claim, lambda task: execute(store, settings, task))

        # 模型诊断也占唯一模型槽；通知不与 Git/事件共用线程，避免大仓库 fetch 再次阻塞消息。
        groups = {
            "model": [Action("review", self._claim_job, self._review),
                      action("review_recovery", lambda: claim_recovery(store), execute_recovery),
                      action("premerge", self._claim_premerge, worker.review_premerge),
                      action("model_check", lambda: store.next_connection_check(("model",)),
                             run_connection_check)],
            "ingress": [action("event", self._claim_event, worker.expand_event),
                        action("backfill", lambda: worker.claim_backfill(store),
                               worker.execute_backfill),
                        action("git_check", lambda: store.next_connection_check(("git", "gitlab")),
                               run_connection_check),
                        action("rule_preview", store.next_rule_preview, worker.preview_rule)],
            "delivery": [Action("notification", store.next_delivery, self._deliver),
                         Action("recovery_notification", lambda: claim_delivery(store),
                             self._deliver_supplement),
                         Action("publication", lambda: next_publication(store),
                                self._publish),
                         action("feishu_check", lambda: store.next_connection_check(("feishu",)),
                                run_connection_check)],
        }
        initialize_slots(store, self.owner)
        self.lanes = [Lane(name, actions, ThreadPoolExecutor(max_workers=1,
                                                           thread_name_prefix=f"ocr-{name}"))
                      for name, actions in groups.items()]

    def _claim_job(self) -> Task | None:
        task = self.store.next_job(self.last_repository_id)
        if task is not None:
            self.last_repository_id = int(task["repository_id"])
            with self.store.connection() as db:
                db.execute("UPDATE review_recovery_fairness SET next_kind='recovery' WHERE id=1")
        return task

    def _review(self, task: Task) -> None:
        from ocr_manager.worker import review_job

        with artifact_lock(self.settings.data_dir, task["id"], blocking=True):
            review_job(self.store, self.settings, task)

    def _claim_event(self) -> Task | None:
        task = self.store.next_event(self.last_event_repository)
        if task:
            self.last_event_repository = int(task["repository_id"])
        return task

    def _claim_premerge(self) -> Task | None:
        from ocr_manager.premerge import next_premerge

        task = next_premerge(self.store, self.last_premerge_repository)
        if task:
            self.last_premerge_repository = int(task["repository_id"])
        return task

    def _execute(self, execute: Execute, task: Task) -> None:
        with stopping_scope(self.stopping):
            check_stopping()
            execute(task)

    def _deliver(self, task: Task) -> None:
        from ocr_manager.worker import deliver_notification

        with artifact_lock(self.settings.data_dir, task["job_id"], blocking=True):
            with self.store.connection() as db:
                valid = db.execute("""SELECT 1 FROM notification_deliveries d
                    JOIN review_jobs j ON j.id=d.job_id WHERE d.id=? AND d.status='sending'
                    AND j.attempts=? AND j.status IN ('complete','partial','failed','skipped')""",
                                   (task["id"], task["review_attempt_number"])).fetchone()
            if valid:
                deliver_notification(self.store, self.settings, task)

    def _deliver_supplement(self, task: Task) -> None:
        from ocr_manager.worker import deliver_notification

        # 与全量重审/清理共用工件锁；发送前再检查源和独立投递令牌。
        with artifact_lock(self.settings.data_dir, task["job_id"], blocking=True):
            deliver_notification(self.store, self.settings, task)

    def _publish(self, task: Task) -> None:
        from ocr_manager.publications import publish_one

        with artifact_lock(self.settings.data_dir, task["job_id"], blocking=True):
            with self.store.connection() as db:
                valid = db.execute("""SELECT 1 FROM gitlab_publications p
                    JOIN review_jobs j ON j.id=p.job_id WHERE p.id=? AND p.status='sending'
                    AND j.attempts=? AND j.status IN ('complete','partial')""",
                                   (task["id"], task["attempt_number"])).fetchone()
            if valid:
                publish_one(self.store, self.settings, task)

    def tick(self) -> bool:
        """仅协调线程领取；每槽每轮最多一个，持续事件不能饿死通知、预审或诊断。"""

        if self.closed:
            raise RuntimeError("调度器已停止")
        handled = False
        # 1. 心跳独立于耗时执行；不因心跳失联而释放栅栏或重发外部请求。
        if time.monotonic() - self.last_heartbeat >= 1:
            heartbeat(self.store, self.owner)
            self.last_heartbeat = time.monotonic()
        # 2. 异常单元停止调度，保留 running 供下一次独占恢复，不能吞掉故障继续占槽。
        for lane in self.lanes:
            if lane.future is not None:
                if not lane.future.done():
                    continue
                lane.future.result()
                finish_slot(self.store, self.owner, lane.name, lane.generation)
                lane.future = None
            # 3. 每次成功领取后轮转类型，跨仓库继续使用原有 MR/事件顺序约束。
            for offset in range(len(lane.actions)):
                index = (lane.cursor + offset) % len(lane.actions)
                action = lane.actions[index]
                task = action.claim()
                if task is None:
                    continue
                lane.generation = start_slot(self.store, self.owner, lane.name, action.kind, task)
                lane.future = lane.executor.submit(self._execute, action.execute, task)
                lane.cursor = (index + 1) % len(lane.actions)
                handled = True
                break
        return handled

    def close(self) -> None:
        """停止领取，通知三个执行单元结束；等待进程组清理后才允许外层释放 Worker 栅栏。"""

        if self.closed:
            return
        self.closed = True
        self.stopping.set()
        for lane in self.lanes:
            lane.executor.shutdown(wait=True, cancel_futures=False)
            interrupted = False
            if lane.future is not None:
                try:
                    lane.future.result()
                except WorkerStopping:
                    interrupted = True
                except BaseException:
                    interrupted = True
                finish_slot(self.store, self.owner, lane.name, lane.generation, interrupted)
        stop_slots(self.store, self.owner)

    def __enter__(self) -> WorkerScheduler:
        """启动后由调用方定期 tick，不自行创建第二个领取协调器。"""

        return self

    def __exit__(self, _type: type[BaseException] | None, _error: BaseException | None,
                 _traceback: TracebackType | None) -> None:
        self.close()
