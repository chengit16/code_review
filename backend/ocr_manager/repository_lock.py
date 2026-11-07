"""串行化同仓库 Git 元数据修改；锁位于工件目录外，不在模型执行期间持有。"""

from __future__ import annotations

import fcntl
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from ocr_manager.cancellation import check_cancellation
from ocr_manager.execution_guard import resource_fence


@contextmanager
def repository_lock(repository: Path) -> Iterator[None]:
    """跨线程和进程保护 clone/fetch/worktree；有界等待且响应 Worker 停止。"""

    directory = repository.parent / ".locks"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(directory / f"{repository.name}.lock", os.O_CREAT | os.O_RDWR, 0o600)
    deadline = time.monotonic() + 660
    try:
        while True:
            check_cancellation()
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("仓库锁等待超时") from None
                time.sleep(0.05)
        with resource_fence(descriptor):
            yield
    finally:
        os.close(descriptor)
