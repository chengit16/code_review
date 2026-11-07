"""只读分析固定 Git 对象的换行变化；不改工作区，实际排除由双预览校验裁决。"""

from __future__ import annotations

import json
import os
import re
import selectors
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

from ocr_manager.cancellation import check_cancellation
from ocr_manager.execution_guard import execution_group, inherited_fences

INPUT_POLICY: dict[str, Any] = {
    "version": 2, "newline_mode": "analyze_only", "max_paths": 5000,
    "max_blob_bytes": 1024 * 1024, "max_total_bytes": 32 * 1024 * 1024,
    "preflight_seconds": 10, "configuration_seconds": 30, "preview_seconds": 60,
    "filter_compatibility": "ocr-1.12.9-bccbc15-json-rule-exact-paths-v1",
}
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def input_policy(enabled: bool = False) -> dict[str, Any]:
    """为任务快照生成不可变的分析或精确路径排除策略。"""

    policy = INPUT_POLICY.copy()
    policy["newline_mode"] = "exclude_verified_paths" if enabled else "analyze_only"
    policy["filter_enabled"] = enabled
    return policy


def _git(root: Path, args: list[str], deadline: float, limit: int) -> bytes:
    env = {key: value for key, value in os.environ.items()
           if key in {"PATH", "TMPDIR", "LANG", "LC_ALL"}}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_NO_REPLACE_OBJECTS="1")
    command = ["git", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", *args]
    with execution_group() as group, subprocess.Popen(
                          command, cwd=root, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                          start_new_session=group is None, process_group=group,
                          pass_fds=inherited_fences()) as process:
        assert process.stdout is not None
        output = bytearray()
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while selector.get_map():
                    check_cancellation()
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("范围预检预算耗尽")
                    for key, _ in selector.select(min(remaining, 0.1)):
                        chunk = os.read(key.fd, 65536)
                        if not chunk:
                            selector.unregister(key.fileobj)
                        output.extend(chunk)
                        if len(output) > limit:
                            raise ValueError("范围预检读取超限")
            if process.wait(timeout=max(0.01, deadline - time.monotonic())):
                raise ValueError("范围预检 Git 对象不可用")
            return bytes(output)
        finally:
            if process.poll() is None:
                os.killpg(group or process.pid, signal.SIGKILL)
                process.wait()


def inspect_range(checkout: Path, head: str, base: str | None = None,
                  *, filter_enabled: bool = False) -> dict[str, Any]:
    """在十秒及字节上限内比较 CRLF 归一化字节；无法确认时仍保留纳入评审。"""

    # 1. 对象和父提交均固定；根提交以空树比较，不读取当前分支 HEAD。
    started = time.monotonic()
    deadline = started + INPUT_POLICY["preflight_seconds"]
    report: dict[str, Any] = {"version": 1, "mode": "analyze_only", "status": "complete",
                              "head_sha": head, "base_sha": base, "original_count": None,
                              "newline_only_paths": [], "excluded_count": 0,
                              "checked_count": 0, "unconfirmed_count": 0, "bytes_read": 0,
                              "filter_enabled": filter_enabled,
                              "filter_reason": ("已请求纯换行路径排除，等待预览校验"
                                                if filter_enabled
                                                else "当前仅分析不排除")}
    try:
        if not re.fullmatch(r"[0-9a-f]{40}", head) or (
            base is not None and not re.fullmatch(r"[0-9a-f]{40}", base)
        ):
            raise ValueError("范围 SHA 无效")
        if base is None:
            parents = _git(checkout, ["rev-list", "--parents", "-n", "1", head],
                           deadline, 2048).decode().split()
            base = parents[1] if len(parents) > 1 else EMPTY_TREE
        report["base_sha"] = base
        raw = _git(checkout, ["diff", "--raw", "--no-renames", "--no-ext-diff", "--no-textconv",
                             "--abbrev=40", "-z", base, head, "--"], deadline, 2 * 1024 * 1024)
        entries = raw.split(b"\0")[:-1]
        if len(entries) % 2:
            raise ValueError("范围路径结构无效")
        report["original_count"] = len(entries) // 2
        # 2. 仅分析同模式普通文件修改，增删、改名、权限和类型变化均不能算纯换行。
        for index in range(0, len(entries), 2):
            check_cancellation()
            if index // 2 >= INPUT_POLICY["max_paths"] or time.monotonic() >= deadline:
                report["status"] = "limited"
                break
            fields = entries[index].decode("ascii").split()
            path = entries[index + 1].decode("utf-8")
            old_mode, new_mode, old, new, status = fields
            if status != "M" or old_mode[1:] not in {"100644", "100755"} or (
                old_mode[1:] != new_mode
            ):
                report["unconfirmed_count"] += 1
                continue
            sizes = [int(_git(checkout, ["cat-file", "-s", oid], deadline, 32))
                     for oid in (old, new)]
            if max(sizes) > INPUT_POLICY["max_blob_bytes"] or (
                report["bytes_read"] + sum(sizes) > INPUT_POLICY["max_total_bytes"]
            ):
                report["unconfirmed_count"] += 1
                report["status"] = "limited"
                continue
            before, after = [_git(checkout, ["cat-file", "blob", oid], deadline,
                                  INPUT_POLICY["max_blob_bytes"]) for oid in (old, new)]
            report["bytes_read"] += sum(sizes)
            report["checked_count"] += 1
            if b"\0" in before or b"\0" in after:
                continue
            try:
                before.decode("utf-8")
                after.decode("utf-8")
            except UnicodeError:
                report["unconfirmed_count"] += 1
                continue
            if before != after and before.replace(b"\r\n", b"\n") == after.replace(b"\r\n", b"\n"):
                report["newline_only_paths"].append(path)
    except (OSError, ValueError, TimeoutError, subprocess.TimeoutExpired):
        # 分析失败只标记未知，不把尚未确认的文件猜测成可豁免文件。
        report["status"] = "unavailable" if report["original_count"] is None else "limited"
    # 3. 摘要不含文件正文；原始范围和 OCR 候选范围保持各自口径。
    report["newline_only_count"] = len(report["newline_only_paths"])
    report["elapsed_seconds"] = round(time.monotonic() - started, 3)
    return report


def save_preflight(run_dir: Path, report: dict[str, Any]) -> None:
    """在受控工件目录保存只读分析证据，不改写 OCR 原始 manifest。"""

    run_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = run_dir / "scope-analysis.json"
    path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    path.chmod(0o600)
