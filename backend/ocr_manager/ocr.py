"""运行固定版本的 OCR CLI 并判定单提交或范围评审的覆盖状态。"""

from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ocr_manager.config import Settings
from ocr_manager.newline_filter import (
    VERIFIED_OCR_VERSION,
    prepare_filtered_preview,
    validate_filtered_manifest,
)
from ocr_manager.ocr_commands import Command, ReviewCommands
from ocr_manager.ocr_commands import execute_ocr_command as _execute_ocr_command
from ocr_manager.range_preflight import inspect_range
from ocr_manager.review_failures import ReviewFailure
from ocr_manager.review_recovery_scope import subset_preview
from ocr_manager.review_results import review_comments

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
    settings: Settings, env: dict[str, str], home: Path, timeout: float,
    execute: Command | None = None,
) -> str:
    """OCR 使用 OpenAI 兼容协议读取自定义端点；只把非密钥 URL 写入隔离 HOME。"""

    endpoint = _validated_model_endpoint(settings.ocr_base_url)
    if not endpoint:
        return settings.ocr_provider
    provider = "managed-gateway"
    for key, value in (
        (f"custom_providers.{provider}.url", endpoint),
        (f"custom_providers.{provider}.protocol", "openai"),
        # OCR 不会从通用变量读取自定义 provider 的密钥；命令只保存变量名。
        (f"custom_providers.{provider}.api_key_cmd", "printenv OCR_LLM_TOKEN"),
    ):
        code, _stderr = (execute or run_ocr_command)(
            [settings.ocr_command, "config", "set", key, value], env, home, timeout
        )
        if code:
            raise ReviewFailure("configuration", "OCR 自定义模型端点配置失败")
    return provider


def _validated_model_endpoint(base_url: str) -> str:
    """仅在真正测试或调用模型时检查自定义端点，保存草稿不受限制。"""

    endpoint = base_url.strip().rstrip("/")
    if not endpoint:
        return ""
    try:
        parsed = urlparse(endpoint)
        valid = (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("OCR 自定义 Base URL 必须是无凭据的 HTTPS 地址")
    return endpoint


def _prepare_review_language(
    settings: Settings, env: dict[str, str], home: Path, timeout: float,
    execute: Command | None = None,
) -> None:
    """通过 OCR 官方配置接口固定模型输出语言。"""

    code, _stderr = (execute or run_ocr_command)(
        [settings.ocr_command, "config", "set", "language", settings.review_language],
        env,
        home,
        timeout,
    )
    if code:
        raise ReviewFailure("configuration", "OCR 评审输出语言配置失败")


def classify_result(result: dict[str, Any], commit_sha: str,
                    base_sha: str | None = None) -> str:
    """以 manifest 的输入及覆盖事实判定结果，避免仅凭退出码宣称通过。"""

    manifest = result.get("manifest")
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "ocr.run-manifest/v1":
        raise ValueError("OCR manifest 版本不兼容")
    input_data = manifest.get("input")
    coverage = manifest.get("coverage")
    if not isinstance(input_data, dict) or not isinstance(coverage, dict):
        raise ValueError("OCR manifest 字段缺失")
    expected_mode = "range" if base_sha else "commit"
    if (input_data.get("mode") != expected_mode or
        input_data.get("resolved_head") != commit_sha or
        base_sha is not None and input_data.get("resolved_base") != base_sha):
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
    review_comments(result)
    summary = result.get("summary")
    if state == "complete" and isinstance(summary, dict) and summary.get("budget_exceeded") is True:
        # 预算耗尽代表评审无法确认全量完成，即使 OCR 顶层仍给出 complete 也应披露部分覆盖。
        return "partial"
    return str(state)


def read_preview(path: Path) -> dict[str, Any]:
    """校验 OCR 预览的关键字段，防止损坏或旧版输出误触发模型调用。"""

    try:
        if path.stat().st_size > 16 * 1024 * 1024:
            raise ReviewFailure("preview_format", "OCR 预览工件超过可验证大小上限")
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ReviewFailure("preview_format", "OCR 预览 JSON 不可用") from error
    if not isinstance(payload, dict):
        raise ReviewFailure("preview_format", "OCR 预览 JSON 不是对象")
    count = payload.get("reviewable_count")
    files = payload.get("files")
    if (
        not isinstance(count, int)
        or isinstance(count, bool)
        or count < 0
        or not isinstance(files, list)
        or count > len(files)
    ):
        raise ReviewFailure("preview_format", "OCR 预览字段不兼容")
    if any(not isinstance(file, dict) or not isinstance(file.get("path"), str)
           or type(file.get("will_review")) is not bool for file in files):
        raise ReviewFailure("preview_format", "OCR 预览路径或选中标记无效")
    if len({file["path"] for file in files}) != len(files) or count != sum(
        file["will_review"] for file in files
    ):
        raise ReviewFailure("preview_format", "OCR 预览数量与实际选中集合冲突")
    return payload


def skipped_result(preview: dict[str, Any], sha: str,
                   base_sha: str | None = None) -> dict[str, Any]:
    """无可审查文件时保留预览证据，明确结论来自预览而非模型。"""

    return {
        "source": "preview",
        "message": "无可审查文件",
        "comments": [],
        "preview": preview,
        "manifest": {
            "schema_version": "ocr.run-manifest/v1",
            "terminal_state": "skipped",
            "input": {"mode": "range" if base_sha else "commit",
                      "resolved_head": sha, **({"resolved_base": base_sha} if base_sha else {})},
            "coverage": {
                "selected": [],
                "completed": [],
                "reused": [],
                "failed": [],
                "waived": [],
            },
        },
    }


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
                if status and status.group(1) == "401":
                    detail += "，API Key 鉴权失败，请检查密钥是否完整以及是否属于当前端点"
                elif status and status.group(1) == "502":
                    detail += "，模型网关或上游服务暂时不可用；这不是保存配置时的字段校验"
                raise RuntimeError(f"OCR 模型连接测试失败（{detail}）")
            raise RuntimeError("OCR 模型测试配置失败")


def _review_arguments(settings: Settings, checkout: Path, run_dir: Path, sha: str,
                      base_sha: str | None, provider: str, project_rule: str | None,
                      background: str | None) -> list[str]:
    base = [settings.ocr_command, "review", "--repo", str(checkout),
            *(["--from", base_sha, "--to", sha] if base_sha else ["--commit", sha]),
            "--format", "json", "--provider", provider,
            "--concurrency", str(settings.ocr_concurrency), "--effort", settings.ocr_effort]
    if settings.ocr_model:
        base.extend(["--model", settings.ocr_model])
    if settings.ocr_max_tokens_budget:
        base.extend(["--max-tokens-budget", str(settings.ocr_max_tokens_budget)])
    if project_rule is not None:
        rule_path = run_dir / "managed-rule.json"
        rule_path.write_text(project_rule, encoding="utf-8")
        base.extend(["--rule", str(rule_path)])
    if background:
        background_path = run_dir / "background.md"
        background_path.write_text(background, encoding="utf-8")
        base.extend(["--background-file", str(background_path)])
    return base


def _filter_scope(settings: Settings, configuration: ReviewCommands, env: dict[str, str],
                  checkout: Path, run_dir: Path, sha: str, base_sha: str | None,
                  scope: dict[str, Any] | None) -> dict[str, Any] | None:
    if not settings.ocr_newline_filter_enabled:
        return scope
    code, _ = configuration.run([settings.ocr_command, "--version"], env, checkout,
                                "filter-version")
    version = (run_dir / "filter-version.stdout.log").read_text().strip()
    if code or not (version == VERIFIED_OCR_VERSION or
                    version.startswith(VERIFIED_OCR_VERSION + " ")):
        raise ReviewFailure("scope_filter", "当前 OCR 版本未经换行过滤验证，未调用模型")
    if scope is None:
        scope = inspect_range(checkout, sha, base_sha, filter_enabled=True)
    if (scope.get("head_sha") != sha or
        base_sha is not None and scope.get("base_sha") != base_sha):
        raise ReviewFailure("scope_filter", "换行分析与冻结范围不一致，未调用模型")
    return scope


def _load_review_result(path: Path, sha: str, base_sha: str | None,
                        returncode: int) -> tuple[str, dict[str, Any]]:
    if not path.exists():
        raise ReviewFailure("result_format", "OCR 未生成 JSON 结果")
    try:
        if path.stat().st_size > 16 * 1024 * 1024:
            raise ReviewFailure("result_format", "OCR JSON 结果超过可验证大小上限")
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ReviewFailure("result_format", "OCR JSON 结果无法解析") from error
    if not isinstance(payload, dict):
        raise ReviewFailure("result_format", "OCR JSON 结果不是对象")
    # 策略排除是平台事实，只能由本次双预览校验产生，不能沿用外部同名字段。
    payload.pop("input_filter", None)
    status = classify_result(payload, sha, base_sha)
    if returncode and status not in {"failed", "partial"}:
        raise ReviewFailure("result_conflict", "OCR 退出码与结果状态冲突")
    return status, payload


def run_review(
    settings: Settings, checkout: Path, run_dir: Path, sha: str,
    global_rule: str | None = None, project_rule: str | None = None,
    on_stage: Callable[[str], None] | None = None,
    base_sha: str | None = None,
    background: str | None = None,
    scope_analysis: dict[str, Any] | None = None,
    recovery_selection: tuple[set[str], set[str]] | None = None,
) -> tuple[str, dict[str, Any]]:
    """保存 preview、JSON 与诊断输出；合并前范围以冻结的 base/head 验证。"""

    # 1. 建立隔离工件和共享截止时间，配置命令同样扣减本次预算。
    run_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    deadline = time.monotonic() + settings.ocr_timeout_seconds
    commands = ReviewCommands(run_ocr_command, run_dir, settings.ocr_api_key, deadline)
    configuration = ReviewCommands(run_ocr_command, run_dir, settings.ocr_api_key,
                                   min(deadline, time.monotonic() + 30))
    configuration_step = 0

    def configure(command: list[str], env: dict[str, str], home: Path,
                  _timeout: float) -> tuple[int, str]:
        nonlocal configuration_step
        configuration_step += 1
        return configuration.run(command, env, home, f"configuration-{configuration_step}")

    # OCR 与管理服务共享进程用户，但不应共享管理凭据或旧版模型端点。
    isolated_home = run_dir / "home"
    isolated_home.mkdir(exist_ok=True, mode=0o700)
    if global_rule is not None:
        # OCR 的 HOME 每次评审隔离；把全局规则放在其标准位置才保留仓库文件的优先级。
        global_dir = isolated_home / ".opencodereview"
        global_dir.mkdir(exist_ok=True, mode=0o700)
        (global_dir / "rule.json").write_text(global_rule, encoding="utf-8")
    env = _ocr_environment(settings, isolated_home)
    _prepare_review_language(settings, env, isolated_home, settings.ocr_timeout_seconds, configure)
    provider = _prepare_custom_provider(
        settings, env, isolated_home, settings.ocr_timeout_seconds, configure)
    scope_analysis = _filter_scope(settings, configuration, env, checkout, run_dir, sha,
                                   base_sha, scope_analysis)
    if recovery_selection is not None:
        code, _ = configuration.run([settings.ocr_command, "--version"], env, checkout,
                                     "recovery-version")
        version = (run_dir / "recovery-version.stdout.log").read_text().strip()
        if code or not (version == VERIFIED_OCR_VERSION or
                        version.startswith(VERIFIED_OCR_VERSION + " ")):
            raise ReviewFailure("recovery_scope", "当前 OCR 版本未经补审子集验证，未调用模型")
        from ocr_manager.recovery_budget import OCR_1129_MINIMUM

        if 0 < settings.ocr_max_tokens_budget < OCR_1129_MINIMUM:
            raise ReviewFailure("budget_insufficient", "补审预算低于已验证执行器的最低启动估算，"
                                "正式审核未调用模型；请先确认预算")
    # 2. 预览和正式评审复用固定 SHA、规则、背景及模型参数，避免范围漂移。
    base = _review_arguments(settings, checkout, run_dir, sha, base_sha, provider,
                             project_rule, background)
    # 3. 两次预览共享六十秒，精确集合核对通过后才使用过滤后数量检查限额。
    preview_runner = ReviewCommands(run_ocr_command, run_dir, settings.ocr_api_key,
                                    min(deadline, time.monotonic() + 60))

    def run_preview(arguments: list[str], name: str) -> dict[str, Any]:
        code, _ = preview_runner.run(
            [*arguments, "--preview", "--output", str(run_dir / "preview.json")],
            env, checkout, name)
        if code:
            raise ReviewFailure("preview", "OCR 预览失败，请查看受控诊断工件")
        return read_preview(run_dir / "preview.json")

    expected: set[str] | None = None
    for name in ("preview", "result"):
        if on_stage:
            on_stage("preview" if name == "preview" else "review")
        # 配置、预览和正式评审共用截止时间，所有退出路径保留脱敏诊断。
        if name == "preview":
            preview = run_preview(base, name)
            if settings.ocr_newline_filter_enabled and scope_analysis is not None:
                base, preview, expected = prepare_filtered_preview(
                    checkout, run_dir, scope_analysis, preview, base,
                    global_rule, project_rule, run_preview)
            if recovery_selection is not None:
                selected, remaining = recovery_selection
                base, preview = subset_preview(checkout, run_dir, base, preview, selected,
                                                remaining, global_rule, run_preview)
                expected = remaining
            if on_stage:
                on_stage("scope_validation")
            if settings.ocr_max_files and preview["reviewable_count"] > settings.ocr_max_files:
                raise ReviewFailure("scope_limit", "可审查文件超过项目上限，未调用模型；"
                                    f"选中 {preview['reviewable_count']} 个，上限 "
                                    f"{settings.ocr_max_files} 个，请拆分范围或调整项目限额")
            if preview["reviewable_count"] == 0:
                # 只在明确的零文件预览下跳过，保留文件及排除原因供管理页查看。
                payload = skipped_result(preview, sha, base_sha)
                if expected is not None:
                    assert scope_analysis is not None
                    payload["input_filter"] = {"excluded_count": scope_analysis["excluded_count"]}
                (run_dir / "result.json").write_text(
                    json.dumps(payload, ensure_ascii=False), encoding="utf-8"
                )
                return "skipped", payload
        if name == "result":
            # 4. 正式评审沿用最终预览的完整参数；原始 manifest 不得被平台修补。
            returncode, _stderr = commands.run(
                [*base, "--audience", "agent", "--output", str(run_dir / "result.json")],
                env, checkout, name)
            if on_stage:
                on_stage("validation")
            status, payload = _load_review_result(run_dir / "result.json", sha, base_sha,
                                                  returncode)
            if expected is not None:
                validate_filtered_manifest(payload, expected)
                if settings.ocr_newline_filter_enabled and scope_analysis is not None:
                    payload["input_filter"] = {"excluded_count": scope_analysis["excluded_count"]}
            # 原始工件保持 OCR 输出；数据库结果补入同一输入的范围预览供管理页核对。
            payload["preview"] = preview
            return status, payload
    raise ReviewFailure("result_format", "OCR 未返回结果")
