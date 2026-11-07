"""用本地 Python 子进程验证 OCR 诊断、共享预算与清理，不调用真实模型。"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from ocr_manager import ocr
from ocr_manager.cancellation import ReviewCancelled, cancellation_scope
from ocr_manager.config import Settings
from ocr_manager.ocr_commands import ReviewCommands
from ocr_manager.review_failures import ReviewFailure


def test_configuration_uses_remaining_review_budget(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """多个 provider 配置命令逐一扣减预算，不能分别重新获得整段超时。"""

    now = [100.0]
    budgets: list[float] = []
    monkeypatch.setattr(ocr.time, "monotonic", lambda: now[0])

    def fake(command: list[str], *_args: Any) -> tuple[int, str]:
        budgets.append(_args[-1])
        now[0] += 4
        if "--output" in command:
            Path(command[command.index("--output") + 1]).write_text(
                '{"reviewable_count":0,"files":[]}', encoding="utf-8")
        return 0, ""

    monkeypatch.setattr(ocr, "run_ocr_command", fake)
    custom = replace(settings, ocr_base_url="https://synthetic.invalid/v1")
    assert ocr.run_review(custom, tmp_path, tmp_path / "run", "a" * 40)[0] == "skipped"
    assert budgets == [30, 26, 22, 18, 14]


def test_exhausted_configuration_cannot_start_preview(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """配置耗尽整体预算后，下一阶段落下空日志与原因，不再启动评审。"""

    now = [100.0]
    monkeypatch.setattr(ocr.time, "monotonic", lambda: now[0])

    def fake(command: list[str], *_args: Any) -> tuple[int, str]:
        assert command[1] == "config"
        now[0] += 31
        return 0, ""

    monkeypatch.setattr(ocr, "run_ocr_command", fake)
    with pytest.raises(ReviewFailure, match="预算耗尽"):
        ocr.run_review(settings, tmp_path, tmp_path / "run", "a" * 40)
    metadata = json.loads((tmp_path / "run/preview.execution.json").read_text())
    assert metadata["outcome"] == "budget_exhausted"
    assert (tmp_path / "run/preview.stderr.log").exists()


@pytest.mark.parametrize("stop", ["timeout", "cancel", "exit"])
def test_interrupted_process_keeps_redacted_output_and_stops_child(
    tmp_path: Path, stop: str,
) -> None:
    """超时、用户取消和 Worker 退出都保留输出并清理同组子进程。"""

    marker = tmp_path / "orphan"
    child = "import pathlib,sys,time;time.sleep(1.2);pathlib.Path(sys.argv[1]).write_text('bad')"
    launcher = ("import subprocess,sys,time;print('start synthetic-secret',flush=True);"
                "print('diagnostic synthetic-secret',file=sys.stderr,flush=True);"
                "subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2]]);time.sleep(10)")
    commands = ReviewCommands(ocr.run_ocr_command, tmp_path, "synthetic-secret",
                              time.monotonic() + (0.4 if stop == "timeout" else 10))
    stop_at = time.monotonic() + 0.4

    def cancelled() -> bool:
        if time.monotonic() < stop_at or stop == "timeout":
            return False
        if stop == "exit":
            raise SystemExit(0)
        return True

    exception = {"timeout": ReviewFailure, "cancel": ReviewCancelled, "exit": SystemExit}[stop]
    with cancellation_scope(cancelled), pytest.raises(exception):
        commands.run([sys.executable, "-c", launcher, child, str(marker)],
                     os.environ.copy(), tmp_path, "result")
    assert "start [REDACTED]" in (tmp_path / "result.stdout.log").read_text()
    assert "diagnostic [REDACTED]" in (tmp_path / "result.stderr.log").read_text()
    assert (tmp_path / "result.stderr.log").stat().st_mode & 0o777 == 0o600
    metadata = json.loads((tmp_path / "result.execution.json").read_text())
    assert metadata["outcome"] == {"exit": "interrupted", "cancel": "cancelled",
                                    "timeout": "timeout"}[stop]
    time.sleep(1)
    assert not marker.exists()


def test_large_outputs_are_drained_but_not_saved_without_limit(tmp_path: Path) -> None:
    """持续排空两条管道避免死锁，保存长度有界并先脱敏再截断。"""

    commands = ReviewCommands(ocr.run_ocr_command, tmp_path, "synthetic-secret",
                              time.monotonic() + 5)
    program = ("import sys;print('synthetic-secret'+'x'*300000);"
               "print('synthetic-secret'+'y'*300000,file=sys.stderr)")
    code, _stderr = commands.run([sys.executable, "-c", program], os.environ.copy(),
                                 tmp_path, "preview")
    assert code == 0
    for stream in ("stdout", "stderr"):
        text = (tmp_path / f"preview.{stream}.log").read_text()
        assert len(text) <= 20000
        assert "synthetic-secret" not in text
        assert "[REDACTED]" in text


@pytest.mark.parametrize("secret", ["synthetic-secret-" + "密" * 40, "token-token"])
def test_truncated_secret_is_redacted_before_saving(tmp_path: Path, secret: str) -> None:
    """采集上限截断密钥时也不落盘残片，包含多字节密钥边界。"""

    commands = ReviewCommands(ocr.run_ocr_command, tmp_path, secret, time.monotonic() + 5)
    program = "import sys;sys.stdout.write(sys.argv[1]*10000)"
    commands.run([sys.executable, "-c", program, secret], os.environ.copy(), tmp_path, "result")
    text = (tmp_path / "result.stdout.log").read_text()
    assert text.replace("[REDACTED]", "") == ""


def test_closed_pipes_do_not_hide_surviving_child(tmp_path: Path) -> None:
    """后代关闭管道并忽略 SIGTERM 时仍必须被强制清理，不能继续执行模型工作。"""

    marker = tmp_path / "surviving-child"
    child = ("import signal,time,pathlib,sys;signal.signal(signal.SIGTERM,signal.SIG_IGN);"
             "time.sleep(1.2);pathlib.Path(sys.argv[1]).write_text('bad')")
    launcher = ("import subprocess,sys,time;subprocess.Popen([sys.executable,'-c',sys.argv[1],"
                "sys.argv[2]],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);time.sleep(10)")
    commands = ReviewCommands(ocr.run_ocr_command, tmp_path, "", time.monotonic() + 0.4)
    with pytest.raises(ReviewFailure, match="超时"):
        commands.run([sys.executable, "-c", launcher, child, str(marker)],
                     os.environ.copy(), tmp_path, "result")
    time.sleep(1.2)
    assert not marker.exists()
