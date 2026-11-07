"""用本机合成进程验证栅栏、孤儿清理和仓库锁；不连接 GitLab 或模型服务。"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from ocr_manager.artifact_lock import artifact_lock
from ocr_manager.config import Settings
from ocr_manager.execution_guard import WorkerStopping, run_git, stopping_scope
from ocr_manager.git_repo import GitRepository
from ocr_manager.ocr_commands import execute_ocr_command
from ocr_manager.scheduler_state import scheduler_snapshot
from ocr_manager.storage import Store
from ocr_manager.worker import worker_is_running, worker_lock


def wait_until(condition: Callable[[], bool], timeout: float = 8) -> None:
    """等待明确的进程或文件事实，期限耗尽时暴露合成生命周期错误。"""

    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "进程生命周期未在期限内完成"
        time.sleep(0.02)


def alive(pid: int) -> bool:
    """僵尸已不可能继续调用模型，不把等待系统回收误认为仍在执行。"""

    result = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True,
                            text=True, check=False)
    return bool(result.stdout.strip()) and not result.stdout.strip().startswith("Z")


def test_coordinator_kill_keeps_fence_until_entire_command_group_stops(tmp_path: Path) -> None:
    """启动器关闭全部锁并提前退出，组长仍阻止恢复及 API 工件清理，随后清除后代。"""

    state = tmp_path / "state.json"
    command = tmp_path / "synthetic.py"
    command.write_text("""import json, os, signal, sys, time
pid = os.fork()
if pid:
    sys.exit(0)
os.closerange(3, 1024)
signal.signal(signal.SIGTERM, signal.SIG_IGN)
with open(sys.argv[1], 'w') as output:
    json.dump({'pid': os.getpid(), 'group': os.getpgrp()}, output)
while True:
    time.sleep(1)
""", encoding="utf-8")
    parent_script = """import os, sys
from pathlib import Path
from ocr_manager.worker import worker_lock
from ocr_manager.artifact_lock import artifact_lock
from ocr_manager.ocr_commands import execute_ocr_command
root = Path(sys.argv[1])
with worker_lock(root), artifact_lock(root, 1, blocking=True):
    execute_ocr_command([sys.executable, sys.argv[2], sys.argv[3]], dict(os.environ), root, 60)
"""
    with subprocess.Popen([sys.executable, "-c", parent_script, str(tmp_path), str(command),
                           str(state)], stdout=subprocess.DEVNULL,
                          stderr=subprocess.PIPE) as parent:
        group: int | None = None
        child: int | None = None
        sentinel: subprocess.Popen[bytes] | None = None
        group_finished = False
        try:
            wait_until(lambda: state.exists() and state.stat().st_size > 0)
            facts = json.loads(state.read_text())
            group, child = facts["group"], facts["pid"]
            # 保留测试进程的同组子进程，避免 Unix 对含暂停成员的孤儿组自动发送 HUP/CONT。
            sentinel = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                                        process_group=group)
            # 暂停栅栏制造可确定窗口：父进程消失，但命令仍在运行且尚未被组长清理。
            os.kill(group, signal.SIGSTOP)
            parent.kill()
            parent.wait(timeout=5)
            assert alive(child)
            assert worker_is_running(tmp_path)
            with pytest.raises(RuntimeError, match="已有 Worker"):
                with worker_lock(tmp_path):
                    pytest.fail("存活命令期间不得恢复队列")
            with artifact_lock(tmp_path, 1) as acquired:
                assert not acquired
            os.kill(group, signal.SIGCONT)
            wait_until(lambda: not alive(child) and not worker_is_running(tmp_path))
            group_finished = True
            with worker_lock(tmp_path), artifact_lock(tmp_path, 1) as acquired:
                assert acquired
        finally:
            if group is not None and not group_finished:
                try:
                    os.killpg(group, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            if parent.poll() is None:
                parent.kill()
                parent.wait(timeout=5)
            if sentinel is not None:
                sentinel.wait(timeout=5)


@pytest.mark.parametrize("adapter", ["git", "ocr"])
@pytest.mark.parametrize("parallelism", [1, 3])
def test_worker_stop_terminates_command_group(
    tmp_path: Path, adapter: str, parallelism: int,
) -> None:
    """协调器停止信号穿透用户取消域，多个 Git/OCR 进程组都清理后才释放栅栏。"""

    ready = [tmp_path / f"ready-{index}" for index in range(parallelism)]
    stopping = threading.Event()
    code = ("import os,sys,time; "
            "open(sys.argv[1],'w').write(str(os.getpid())); time.sleep(60)")
    def execute(path: Path) -> None:
        command = [sys.executable, "-c", code, str(path)]
        with stopping_scope(stopping):
            if adapter == "git":
                run_git(command, tmp_path, dict(os.environ), 60)
            else:
                execute_ocr_command(command, dict(os.environ), tmp_path, 60)

    with worker_lock(tmp_path), ThreadPoolExecutor(max_workers=parallelism) as executor:
        futures = [executor.submit(execute, path) for path in ready]
        try:
            wait_until(lambda: all(path.exists() and path.stat().st_size for path in ready))
        finally:
            stopping.set()
        for future in futures:
            with pytest.raises(WorkerStopping):
                future.result(timeout=8)
    assert all(not alive(int(path.read_text())) for path in ready)
    assert not worker_is_running(tmp_path)


def test_same_repository_mutations_serialize_but_other_repository_progresses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同仓库 fetch/worktree 互斥，但不得用全局 Git 锁阻塞另一仓库。"""

    repository = {"id": 1, "remote_url": "synthetic", "target_branch": "main"}
    first = GitRepository(tmp_path, repository)
    second = GitRepository(tmp_path, {**repository, "id": 2})
    started, release, checkout, other = (threading.Event() for _ in range(4))

    def fetch(self: GitRepository) -> None:
        if self.path == first.path:
            started.set()
            assert release.wait(4)
        else:
            other.set()

    def git(*_args: object, **_kwargs: object) -> str:
        checkout.set()
        return ""

    monkeypatch.setattr(GitRepository, "_fetch", fetch)
    monkeypatch.setattr(GitRepository, "_git", git)
    with ThreadPoolExecutor(max_workers=3) as executor:
        pending = executor.submit(first.fetch)
        try:
            assert started.wait(4)
            same = executor.submit(first.checkout, "a" * 40, tmp_path / "checkout")
            different = executor.submit(second.fetch)
            assert other.wait(4)
            assert not checkout.is_set()
        finally:
            release.set()
        pending.result(timeout=4)
        same.result(timeout=4)
        different.result(timeout=4)
    assert checkout.is_set()


@pytest.mark.parametrize("capacity", [1, 10])
def test_real_worker_entrypoint_initializes_heartbeats_and_stops(
    settings: Settings, capacity: int,
) -> None:
    """真实入口从临时库加载容量、拒绝第二进程，SIGTERM 后全部槽停止并释放锁。"""

    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith("OCR_APP_")}
    environment.update(OCR_APP_DATA_DIR=str(settings.data_dir), OCR_APP_DEV_MODE="1",
                       OCR_APP_MASTER_KEY=settings.master_key)
    store = Store(settings.data_dir / "app.db")
    store.migrate()
    from ocr_manager.scheduler_config import save_scheduler_config

    save_scheduler_config(store, capacity, 1, "合成管理员")

    def initialized() -> bool:
        return len(scheduler_snapshot(store)["slots"]) == capacity + 2

    with subprocess.Popen([sys.executable, "-m", "ocr_manager.worker"], env=environment,
                          stdout=subprocess.DEVNULL, stderr=subprocess.PIPE) as process:
        try:
            wait_until(initialized)
            with store.connection() as db:
                db.execute("UPDATE worker_execution_slots SET heartbeat_at='2000-01-01 00:00:00'")
            wait_until(lambda: all(slot["heartbeat_age_seconds"] < 2
                                   for slot in scheduler_snapshot(store)["slots"]))
            second = subprocess.run([sys.executable, "-m", "ocr_manager.worker"],
                                    env=environment, capture_output=True, timeout=5)
            assert second.returncode != 0
            assert "已有 Worker" in second.stderr.decode()
            assert all(slot["state"] == "idle" for slot in scheduler_snapshot(store)["slots"])
            process.terminate()
            assert process.wait(timeout=5) == 0
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
    assert all(slot["state"] == "stopped" for slot in scheduler_snapshot(store)["slots"])
    assert not worker_is_running(settings.data_dir)


def test_cancel_one_ocr_does_not_cancel_other_active_process_group(tmp_path: Path) -> None:
    """两个 OCR 命令同时运行，任务级取消仅终止自己的进程组，另一组继续受 Worker 栅栏保护。"""

    from ocr_manager.cancellation import ReviewCancelled, cancellation_scope

    cancelled = [threading.Event(), threading.Event()]
    ready = [tmp_path / f"cancel-isolation-{index}" for index in range(2)]
    code = ("import os,sys,time; "
            "open(sys.argv[1],'w').write(str(os.getpid())); time.sleep(60)")

    def execute(index: int) -> None:
        with cancellation_scope(cancelled[index].is_set), artifact_lock(tmp_path, index + 1):
            execute_ocr_command([sys.executable, "-c", code, str(ready[index])],
                                dict(os.environ), tmp_path, 60)

    with worker_lock(tmp_path), ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(execute, index) for index in range(2)]
        try:
            wait_until(lambda: all(path.exists() and path.stat().st_size for path in ready))
            cancelled[0].set()
            with pytest.raises(ReviewCancelled):
                futures[0].result(timeout=8)
            assert not alive(int(ready[0].read_text()))
            assert alive(int(ready[1].read_text())) and not futures[1].done()
            assert worker_is_running(tmp_path)
        finally:
            for event in cancelled:
                event.set()
            for future in futures:
                with pytest.raises(ReviewCancelled):
                    future.result(timeout=8)
    assert all(not alive(int(path.read_text())) for path in ready)
    assert not worker_is_running(tmp_path)
