"""维护本机执行栅栏及停止信号；只保护进程生命周期，不领取队列或按心跳抢占。"""

from __future__ import annotations

import os
import select
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

_worker_descriptor: int | None = None
_stopping: ContextVar[threading.Event | None] = ContextVar("worker_stopping", default=None)
_resources: ContextVar[tuple[int, ...]] = ContextVar("execution_resources", default=())


class WorkerStopping(BaseException):
    """正常停止不能被业务的 Exception 捕获后误写为用户取消或普通失败。"""


@contextmanager
def worker_fence(descriptor: int) -> Iterator[None]:
    """在单实例锁作用域登记描述符，Git/OCR 后代继承同一栅栏防止孤儿重复执行。"""

    global _worker_descriptor
    previous, _worker_descriptor = _worker_descriptor, descriptor
    try:
        yield
    finally:
        _worker_descriptor = previous


def inherited_fences() -> tuple[int, ...]:
    """仅传递非凭据锁描述符；父进程被强杀后存活后代仍阻止新 Worker 恢复旧任务。"""

    worker = () if _worker_descriptor is None else (_worker_descriptor,)
    return worker + _resources.get()


@contextmanager
def resource_fence(descriptor: int) -> Iterator[None]:
    """在耗时命令期间向栅栏进程传递仓库/工件锁，避免协调器崩溃后被 API 清理。"""

    token = _resources.set((*_resources.get(), descriptor))
    try:
        yield
    finally:
        _resources.reset(token)


@contextmanager
def execution_group() -> Iterator[int | None]:
    """先建立持锁组长再启动命令；控制管道关闭即整组强杀，不依赖启动器转传锁。"""

    if not inherited_fences():
        yield None
        return
    with subprocess.Popen([sys.executable, "-m", "ocr_manager.process_fence"],
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, process_group=0,
                          pass_fds=inherited_fences()) as guardian:
        assert guardian.stdout is not None and guardian.stdin is not None
        try:
            # 先确认组长已忽略 SIGTERM，避免宽限清理提前释放锁而命令后代仍存活。
            if not select.select([guardian.stdout], [], [], 5)[0] or (
                guardian.stdout.readline() != b"ready\n"
            ):
                raise RuntimeError("执行栅栏无法就绪，拒绝启动外部命令")
            yield guardian.pid
        finally:
            guardian.stdin.close()
            try:
                guardian.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(guardian.pid, signal.SIGKILL)
                guardian.wait()


@contextmanager
def stopping_scope(event: threading.Event) -> Iterator[None]:
    """线程各自绑定停止检查，避免跨任务污染用户取消检查器。"""

    token = _stopping.set(event)
    try:
        yield
    finally:
        _stopping.reset(token)


def check_stopping() -> None:
    """在有界外部命令循环中停止执行，保留 running 供独占恢复记录真实中断。"""

    event = _stopping.get()
    if event is not None and event.is_set():
        raise WorkerStopping()


def run_git(command: list[str], cwd: Path, env: dict[str, str],
            timeout: float) -> subprocess.CompletedProcess[str]:
    """独立进程组执行 Git，停止或超时后终止整组；输出仅交给原 Git 解析器。"""

    from ocr_manager.cancellation import check_cancellation

    with execution_group() as group, subprocess.Popen(
                          command, cwd=cwd, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                          start_new_session=group is None, process_group=group,
                          pass_fds=inherited_fences()) as process:
        deadline = time.monotonic() + timeout
        try:
            while True:
                check_cancellation()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(command, timeout)
                try:
                    stdout, stderr = process.communicate(timeout=min(0.25, remaining))
                    return subprocess.CompletedProcess(command, process.returncode,
                                                       stdout.decode(), stderr.decode())
                except subprocess.TimeoutExpired:
                    continue
        except BaseException:
            for sig in (signal.SIGTERM, signal.SIGKILL):
                try:
                    os.killpg(group or process.pid, sig)
                except ProcessLookupError:
                    pass
                try:
                    process.communicate(timeout=1)
                except subprocess.TimeoutExpired:
                    pass
            process.wait()
            raise
