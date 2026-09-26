"""保护跨 API 与 Worker 进程的任务工件；锁文件不位于可清理目录中。"""

from __future__ import annotations

import fcntl
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def artifact_lock(data_dir: Path, job_id: int) -> Iterator[bool]:
    """非阻塞领取单任务工件锁；调用方须在失败时返回冲突或跳过候选。"""

    directory = data_dir / ".artifact-locks"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(directory / f"{job_id}.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
        else:
            # 文件描述符在事务和目录操作结束后关闭，进程退出也会自动释放。
            yield True
    finally:
        os.close(descriptor)
