"""为一次评审绑定停止检查；预览、模型配置与评审共享同一停止边界。"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_check: ContextVar[Callable[[], bool] | None] = ContextVar("review_cancellation", default=None)


class ReviewCancelled(Exception):
    """用户停止属于任务终态，不进入网络失败重试。"""


def check_cancellation() -> None:
    """Worker 在外部调用边界检查，子进程执行期间也定期调用。"""

    checker = _check.get()
    if checker and checker():
        raise ReviewCancelled("用户请求停止评审")


@contextmanager
def cancellation_scope(checker: Callable[[], bool]) -> Iterator[None]:
    """任务结束后撤销检查器，其他诊断与下一任务不继承停止请求。"""

    token = _check.set(checker)
    try:
        check_cancellation()
        yield
    finally:
        _check.reset(token)
