"""执行有界 OCR 子进程并保存受控诊断；不解析评审结论，也不写入业务数据库。"""

from __future__ import annotations

import json
import os
import selectors
import signal
import subprocess
import time
from collections.abc import Callable
from contextvars import ContextVar
from pathlib import Path

from ocr_manager.cancellation import ReviewCancelled, check_cancellation
from ocr_manager.execution_guard import execution_group, inherited_fences
from ocr_manager.review_failures import ReviewFailure

Command = Callable[[list[str], dict[str, str], Path, float], tuple[int, str]]
OutputSink = Callable[[str, str], None]
_output_sink: ContextVar[OutputSink | None] = ContextVar("ocr_output_sink", default=None)
OUTPUT_LIMIT = 40000


def _read_output(selector: selectors.BaseSelector, buffers: dict[str, bytearray],
                 timeout: float) -> None:
    for key, _mask in selector.select(timeout):
        chunk = os.read(key.fd, 65536)
        if not chunk:
            selector.unregister(key.fileobj)
        else:
            buffer = buffers[key.data]
            buffer.extend(chunk[:max(0, OUTPUT_LIMIT - len(buffer))])


def _stop_process(process: subprocess.Popen[bytes], selector: selectors.BaseSelector,
                  buffers: dict[str, bytearray], group: int | None) -> None:
    # 父启动器可能已退出，但同组后代仍持有管道；终止必须面向整个进程组。
    for sig, grace in ((signal.SIGTERM, 5.0), (signal.SIGKILL, 1.0)):
        try:
            os.killpg(group or process.pid, sig)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + grace
        while (selector.get_map() or process.poll() is None) and time.monotonic() < deadline:
            _read_output(selector, buffers, 0.05)
        # 管道关闭不代表后代退出；即使启动器已结束，也继续向进程组发送 SIGKILL。
    process.wait(timeout=1)


def _redact_output(text: str, secret: str) -> str:
    if not secret:
        return text
    # 先替换完整密钥，避免重复前后缀互相干扰；采集截断时也遮蔽尾部密钥残片。
    text = text.replace(secret, "[REDACTED]")
    candidate = text.removesuffix("\ufffd")
    for length in range(min(len(secret) - 1, len(candidate)), 0, -1):
        if candidate.endswith(secret[:length]):
            text = candidate[:-length] + "[REDACTED]"
            break
    return text


def execute_ocr_command(command: list[str], env: dict[str, str], checkout: Path,
                        timeout: float) -> tuple[int, str, str]:
    """持续排空管道但只保留限量输出；取消、超时和退出信号均清理子进程组。"""

    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    with execution_group() as group, subprocess.Popen(
        command, env=env, cwd=checkout, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        start_new_session=group is None, process_group=group,
        pass_fds=inherited_fences(),
    ) as process, selectors.DefaultSelector() as selector:
        assert process.stdout is not None and process.stderr is not None
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        deadline = time.monotonic() + timeout
        try:
            while selector.get_map() or process.poll() is None:
                check_cancellation()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(command, timeout)
                _read_output(selector, buffers, min(0.25, remaining))
        except BaseException:
            _stop_process(process, selector, buffers, group)
            raise
        finally:
            sink = _output_sink.get()
            if sink:
                sink(buffers["stdout"].decode("utf-8", errors="replace"),
                     buffers["stderr"].decode("utf-8", errors="replace"))
        return process.wait(), buffers["stdout"].decode("utf-8", errors="replace"), buffers[
            "stderr"].decode("utf-8", errors="replace")


class ReviewCommands:
    """一次评审共享截止时间；逐命令诊断隔离保存，输出不进入普通日志或错误正文。"""

    def __init__(self, execute: Command, run_dir: Path, secret: str, deadline: float) -> None:
        self.execute = execute
        self.run_dir = run_dir
        self.secret = secret
        self.deadline = deadline

    def run(self, command: list[str], env: dict[str, str], cwd: Path,
            name: str) -> tuple[int, str]:
        """执行前检查剩余预算，所有退出路径写入限量日志和不含外部正文的元数据。"""

        # 1. 固定本命令剩余预算，输出接收器负责所有退出路径的受控脱敏落盘。
        started = time.monotonic()
        remaining = self.deadline - started
        captured = False

        def save(stdout: str, stderr: str) -> None:
            nonlocal captured
            captured = True
            for stream, text in (("stdout", stdout), ("stderr", stderr)):
                text = _redact_output(text, self.secret)
                path = self.run_dir / f"{name}.{stream}.log"
                path.write_text(text[:20000], encoding="utf-8")
                path.chmod(0o600)

        token = _output_sink.set(save)
        outcome, code = "interrupted", None
        # 2. 不给配置、预览或正式评审重新发放预算；取消与超时分别保留终止原因。
        try:
            check_cancellation()
            if remaining <= 0:
                outcome = "budget_exhausted"
                raise ReviewFailure("timeout", "OCR 整体运行预算耗尽，不自动整批重试")
            code, stderr = self.execute(command, env, cwd, remaining)
            if not captured:
                save("", stderr)
            outcome = "finished"
            return code, stderr
        except subprocess.TimeoutExpired as error:
            outcome = "timeout"
            raise ReviewFailure("timeout", f"OCR {name} 超时，不自动整批重试") from error
        except ReviewCancelled:
            outcome = "cancelled"
            raise
        except OSError as error:
            outcome = "launch_failed"
            raise ReviewFailure("command", "OCR 命令无法启动或诊断工件无法保存") from error
        finally:
            # 3. 即使未启动或尚无输出也保留元数据，清理宽限计入实际 elapsed_seconds。
            _output_sink.reset(token)
            if not captured:
                save("", "")
            path = self.run_dir / f"{name}.execution.json"
            path.write_text(json.dumps({"stage": name, "outcome": outcome, "exit_code": code,
                                        "elapsed_seconds": max(0, time.monotonic() - started),
                                        "budget_seconds": remaining}), encoding="utf-8")
            path.chmod(0o600)
