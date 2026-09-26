"""运行固定版本的 OCR CLI 并判定逐提交评审的覆盖状态。"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ocr_manager.config import Settings

OCR_ENV_PASSTHROUGH = frozenset(
    {
        "PATH",
        "TMPDIR",
        "TMP",
        "TEMP",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "NODE_EXTRA_CA_CERTS",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NO_PROXY",
        "http_proxy",
        "https_proxy",
        "no_proxy",
    }
)


def _ocr_environment(settings: Settings, home: Path) -> dict[str, str]:
    """仅继承运行与网络环境，并注入本次评审指定的模型配置。"""

    # 服务进程可能持有任意名称的其他系统密钥，因此使用允许列表而非排除特定前缀。
    env = {key: value for key, value in os.environ.items() if key in OCR_ENV_PASSTHROUGH}
    env["HOME"] = str(home)
    env["OCR_NO_UPDATE"] = "1"
    if settings.ocr_model:
        env["OCR_LLM_MODEL"] = settings.ocr_model
    if settings.ocr_api_key:
        env["OCR_LLM_TOKEN"] = settings.ocr_api_key
        if settings.ocr_provider == "dashscope":
            env["DASHSCOPE_API_KEY"] = settings.ocr_api_key
    return env


def _prepare_custom_provider(
    settings: Settings, env: dict[str, str], home: Path, timeout: int
) -> str:
    """OCR 使用 OpenAI 兼容协议读取自定义端点；只把非密钥 URL 写入隔离 HOME。"""

    if not settings.ocr_base_url:
        return settings.ocr_provider
    provider = "managed-gateway"
    for key, value in (
        (f"custom_providers.{provider}.url", settings.ocr_base_url),
        (f"custom_providers.{provider}.protocol", "openai"),
        # OCR 不会从通用变量读取自定义 provider 的密钥；命令只保存变量名。
        (f"custom_providers.{provider}.api_key_cmd", "printenv OCR_LLM_TOKEN"),
    ):
        code, _stderr = run_ocr_command(
            [settings.ocr_command, "config", "set", key, value], env, home, timeout
        )
        if code:
            raise RuntimeError("OCR 自定义模型端点配置失败")
    return provider


def classify_result(result: dict[str, Any], commit_sha: str) -> str:
    """以 manifest 的输入及覆盖事实判定结果，避免仅凭退出码宣称通过。"""

    manifest = result.get("manifest")
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "ocr.run-manifest/v1":
        raise ValueError("OCR manifest 版本不兼容")
    input_data = manifest.get("input")
    coverage = manifest.get("coverage")
    if not isinstance(input_data, dict) or not isinstance(coverage, dict):
        raise ValueError("OCR manifest 字段缺失")
    if input_data.get("mode") != "commit" or input_data.get("resolved_head") != commit_sha:
        raise ValueError("OCR 审查输入 SHA 不匹配")
    sets = [coverage.get(name) for name in ("completed", "reused", "failed", "waived")]
    selected = coverage.get("selected")
    if not isinstance(selected, list) or any(not isinstance(items, list) for items in sets):
        raise ValueError("OCR 覆盖集合无效")
    groups: list[list[Any]] = [group for group in sets if isinstance(group, list)]
    identifiers: list[str] = [
        item["item_id"]
        for group in groups
        for item in group
        if isinstance(item, dict) and isinstance(item.get("item_id"), str)
    ]
    selected_ids: list[str] = [
        item["item_id"]
        for item in selected
        if isinstance(item, dict) and isinstance(item.get("item_id"), str)
    ]
    if (
        len(identifiers) != sum(len(group) for group in groups)
        or len(selected_ids) != len(selected)
        or len(set(identifiers)) != len(identifiers)
        or len(set(selected_ids)) != len(selected_ids)
        or sorted(identifiers) != sorted(selected_ids)
    ):
        raise ValueError("OCR 覆盖集合不完整或重复")
    state = manifest.get("terminal_state")
    if state not in {"complete", "partial", "failed", "skipped"}:
        raise ValueError("OCR 评审状态未知")
    if state == "complete" and coverage["failed"]:
        raise ValueError("OCR 完成状态与失败文件冲突")
    summary = result.get("summary")
    if state == "complete" and isinstance(summary, dict) and summary.get("budget_exceeded") is True:
        # 预算耗尽代表评审无法确认全量完成，即使 OCR 顶层仍给出 complete 也应披露部分覆盖。
        return "partial"
    return str(state)


def read_preview(path: Path) -> dict[str, Any]:
    """校验 OCR 预览的关键字段，防止损坏或旧版输出误触发模型调用。"""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RuntimeError("OCR 预览 JSON 不可用") from error
    if not isinstance(payload, dict):
        raise RuntimeError("OCR 预览 JSON 不是对象")
    count = payload.get("reviewable_count")
    files = payload.get("files")
    if (
        not isinstance(count, int)
        or isinstance(count, bool)
        or count < 0
        or not isinstance(files, list)
        or count > len(files)
    ):
        raise RuntimeError("OCR 预览字段不兼容")
    return payload


def skipped_result(preview: dict[str, Any], sha: str) -> dict[str, Any]:
    """无可审查文件时保留预览证据，明确结论来自预览而非模型。"""

    return {
        "source": "preview",
        "message": "无可审查文件",
        "comments": [],
        "preview": preview,
        "manifest": {
            "schema_version": "ocr.run-manifest/v1",
            "terminal_state": "skipped",
            "input": {"mode": "commit", "resolved_head": sha},
            "coverage": {
                "selected": [],
                "completed": [],
                "reused": [],
                "failed": [],
                "waived": [],
            },
        },
    }


def _execute_ocr_command(
    command: list[str], env: dict[str, str], checkout: Path, timeout: float
) -> tuple[int, str, str]:
    """将 npm 启动器及 OCR 子进程放入同一进程组，并收集诊断输出。"""

    process = subprocess.Popen(
        command,
        env=env,
        cwd=checkout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except BaseException:
        # Popen 的直接子进程可能是 npm 包装器，必须连同实际 OCR 进程一起终止。
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()
        raise
    return process.returncode, stdout, stderr


def run_ocr_command(
    command: list[str], env: dict[str, str], checkout: Path, timeout: float
) -> tuple[int, str]:
    """正式评审只使用退出码与 stderr；stdout 不进入评审结果。"""

    code, _stdout, stderr = _execute_ocr_command(command, env, checkout, timeout)
    return code, stderr


def check_rule(
    settings: Settings, checkout: Path, run_dir: Path, file_path: str,
    global_rule: str | None, project_rule: str | None,
) -> str:
    """按正式评审的优先级调用 OCR 规则查询，不调用模型。"""

    home = run_dir / "home"
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    if global_rule is not None:
        global_dir = home / ".opencodereview"
        global_dir.mkdir(exist_ok=True, mode=0o700)
        (global_dir / "rule.json").write_text(global_rule, encoding="utf-8")
    command = [settings.ocr_command, "rules", "check", "--repo", str(checkout)]
    if project_rule is not None:
        rule_path = run_dir / "managed-rule.json"
        rule_path.write_text(project_rule, encoding="utf-8")
        command.extend(["--rule", str(rule_path)])
    command.append(file_path)
    code, stdout, _stderr = _execute_ocr_command(
        command, _ocr_environment(settings, home), checkout, 45
    )
    if code:
        raise RuntimeError("OCR 规则预览失败，请检查规则文件格式")
    if not stdout.strip():
        raise RuntimeError("OCR 规则预览未返回结果")
    # 仓库规则可能很长，数据库只保留可读上限并明确标记截断。
    return stdout[:20000] + ("\n…结果已截断" if len(stdout) > 20000 else "")


def check_model_connection(settings: Settings, run_dir: Path) -> None:
    """用隔离 OCR 配置发起真实模型测试，不把密钥放进命令参数或工件。"""

    if not settings.ocr_model or not settings.ocr_api_key:
        raise ValueError("模型或 API key 未配置")
    home = run_dir / "home"
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    env = _ocr_environment(settings, home)
    timeout = min(max(settings.ocr_timeout_seconds, 10), 90)
    provider = _prepare_custom_provider(settings, env, home, timeout)
    # llm test 没有 provider/model 参数，先在本次诊断专用 HOME 中写入非密钥配置。
    for args in (
        ["config", "set", "provider", provider],
        ["config", "set", "model", settings.ocr_model],
        ["llm", "test"],
    ):
        code, stderr = run_ocr_command([settings.ocr_command, *args], env, home, timeout)
        if code:
            if args[0] == "llm":
                # 仅提取 HTTP 状态码，不把可能含密钥或服务响应的 stderr 写入数据库。
                status = re.search(r"\b([45][0-9]{2})\s+[A-Za-z]", stderr)
                detail = f"HTTP {status.group(1)}" if status else f"退出码 {code}"
                raise RuntimeError(f"OCR 模型连接测试失败（{detail}）")
            raise RuntimeError("OCR 模型测试配置失败")


def run_review(
    settings: Settings, checkout: Path, run_dir: Path, sha: str,
    global_rule: str | None = None, project_rule: str | None = None,
    on_stage: Callable[[str], None] | None = None,
) -> tuple[str, dict[str, Any]]:
    """保存 preview、JSON 与诊断输出；全程不经过 shell。"""

    run_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    deadline = time.monotonic() + settings.ocr_timeout_seconds
    # OCR 与管理服务共享进程用户，但不应共享管理凭据或旧版模型端点。
    isolated_home = run_dir / "home"
    isolated_home.mkdir(exist_ok=True, mode=0o700)
    if global_rule is not None:
        # OCR 的 HOME 每次评审隔离；把全局规则放在其标准位置才保留仓库文件的优先级。
        global_dir = isolated_home / ".opencodereview"
        global_dir.mkdir(exist_ok=True, mode=0o700)
        (global_dir / "rule.json").write_text(global_rule, encoding="utf-8")
    env = _ocr_environment(settings, isolated_home)
    provider = _prepare_custom_provider(settings, env, isolated_home, settings.ocr_timeout_seconds)
    base = [
        settings.ocr_command,
        "review",
        "--repo",
        str(checkout),
        "--commit",
        sha,
        "--format",
        "json",
        "--provider",
        provider,
    ]
    if settings.ocr_model:
        base.extend(["--model", settings.ocr_model])
    if project_rule is not None:
        # 管理台按项目设置的规则显式覆盖仓库版本化文件，预览和正式评审共用同一份。
        rule_path = run_dir / "managed-rule.json"
        rule_path.write_text(project_rule, encoding="utf-8")
        base.extend(["--rule", str(rule_path)])
    for name, command in (
        ("preview", [*base, "--preview", "--output", str(run_dir / "preview.json")]),
        ("result", [*base, "--audience", "agent", "--output", str(run_dir / "result.json")]),
    ):
        if on_stage:
            on_stage("preview" if name == "preview" else "review")
        # preview 与正式评审共用一个截止时间，避免两步各占用整段运行预算。
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError("OCR 整体运行超时")
        try:
            returncode, stderr = run_ocr_command(command, env, checkout, remaining)
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(f"OCR {name} 超时") from error
        diagnostic = stderr[:20000]
        for secret in (settings.ocr_api_key,):
            if secret:
                diagnostic = diagnostic.replace(secret, "[REDACTED]")
        (run_dir / f"{name}.stderr.log").write_text(diagnostic, encoding="utf-8")
        if returncode and name == "preview":
            raise RuntimeError("OCR 预览失败，请查看受控诊断工件")
        if name == "preview":
            preview = read_preview(run_dir / "preview.json")
            if preview["reviewable_count"] == 0:
                # 只在明确的零文件预览下跳过，保留文件及排除原因供管理页查看。
                payload = skipped_result(preview, sha)
                (run_dir / "result.json").write_text(
                    json.dumps(payload, ensure_ascii=False), encoding="utf-8"
                )
                return "skipped", payload
        if name == "result":
            if on_stage:
                on_stage("validation")
            path = run_dir / "result.json"
            if not path.exists():
                raise RuntimeError("OCR 未生成 JSON 结果")
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except ValueError as error:
                raise RuntimeError("OCR JSON 结果无法解析") from error
            if not isinstance(payload, dict):
                raise RuntimeError("OCR JSON 结果不是对象")
            status = classify_result(payload, sha)
            if returncode and status not in {"failed", "partial"}:
                raise RuntimeError("OCR 退出码与结果状态冲突")
            # 原始工件保持 OCR 输出；数据库结果补入同一输入的范围预览供管理页核对。
            payload["preview"] = preview
            return status, payload
    raise RuntimeError("OCR 未返回结果")
