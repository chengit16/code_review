"""保护 OCR manifest 覆盖判断，避免部分运行被写成通过。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from ocr_manager import ocr
from ocr_manager.config import Settings
from ocr_manager.ocr import check_model_connection, classify_result, run_ocr_command, run_review

SHA = "a" * 40


def result(state: str, failed: bool = False) -> dict[str, Any]:
    """构造一个文件的最小 OCR v1 manifest。"""

    item = {"item_id": "one", "path": "main.py"}
    return {
        "manifest": {
            "schema_version": "ocr.run-manifest/v1",
            "terminal_state": state,
            "input": {"mode": "commit", "resolved_head": SHA},
            "coverage": {
                "selected": [item],
                "completed": [] if failed else [item],
                "reused": [],
                "failed": [item] if failed else [],
                "waived": [],
            },
        },
        "comments": [],
    }


def test_complete_and_partial_are_distinct() -> None:
    """有失败文件时不能将零评论解释成已完整评审。"""

    assert classify_result(result("complete"), SHA) == "complete"
    assert classify_result(result("partial", failed=True), SHA) == "partial"
    with pytest.raises(ValueError, match="冲突"):
        classify_result(result("complete", failed=True), SHA)


def test_input_and_coverage_must_match() -> None:
    """错误 SHA 或覆盖分组缺项时拒绝发布可信结论。"""

    with pytest.raises(ValueError, match="SHA"):
        classify_result(result("complete"), "b" * 40)
    incomplete = result("complete")
    incomplete["manifest"]["coverage"]["completed"] = []
    with pytest.raises(ValueError, match="覆盖集合"):
        classify_result(incomplete, SHA)


def test_duplicate_coverage_items_are_not_complete() -> None:
    """同一文件不能在多个覆盖分组或分母中重复计数。"""

    duplicate = result("complete")
    item = duplicate["manifest"]["coverage"]["selected"][0]
    duplicate["manifest"]["coverage"]["selected"].append(item)
    duplicate["manifest"]["coverage"]["reused"].append(item)
    with pytest.raises(ValueError, match="重复"):
        classify_result(duplicate, SHA)


def test_budget_exhaustion_is_partial_even_with_complete_manifest() -> None:
    """预算耗尽不能向管理员和飞书宣称评审已全部完成。"""

    exhausted = result("complete")
    exhausted["summary"] = {"budget_exceeded": True}
    assert classify_result(exhausted, SHA) == "partial"


def test_custom_endpoint_is_configured_in_isolated_ocr_home(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """自定义 Base URL 的 provider 配置必须在本次诊断 HOME 中生效。"""

    commands: list[list[str]] = []

    def fake_run(
        command: list[str], _env: dict[str, str], _home: Path, _timeout: float
    ) -> tuple[int, str]:
        commands.append(command)
        return 0, ""

    monkeypatch.setattr(ocr, "run_ocr_command", fake_run)
    configured = replace(settings, ocr_base_url="https://gateway.example.test/v1")
    check_model_connection(configured, tmp_path / "custom-model-check")
    assert commands[0][-2:] == [
        "custom_providers.managed-gateway.url",
        "https://gateway.example.test/v1",
    ]
    assert commands[1][-2:] == ["custom_providers.managed-gateway.protocol", "openai"]
    assert commands[2][-2:] == ["provider", "managed-gateway"]
    assert commands[-1][-2:] == ["llm", "test"]


def test_empty_preview_skips_model_and_preserves_exclusions(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """零可审查文件只生成跳过结论，不启动正式 OCR 评审。"""

    commands: list[list[str]] = []
    preview = {
        "total_files": 1,
        "reviewable_count": 0,
        "excluded_count": 1,
        "files": [
            {"path": "vendor/a.js", "will_review": False, "exclude_reason": "provider_directory"}
        ],
    }

    def fake_run(command: list[str], *_args: Any) -> tuple[int, str]:
        commands.append(command)
        output = Path(command[command.index("--output") + 1])
        output.write_text(json.dumps(preview), encoding="utf-8")
        return 0, ""

    monkeypatch.setattr(ocr, "run_ocr_command", fake_run)
    status, payload = run_review(settings, tmp_path, tmp_path / "run", SHA)
    assert status == "skipped"
    assert len(commands) == 1
    assert "--preview" in commands[0]
    assert payload["source"] == "preview"
    assert payload["preview"]["files"][0]["exclude_reason"] == "provider_directory"
    assert (tmp_path / "run" / "result.json").exists()


def test_invalid_preview_does_not_start_model(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """预览格式未知时停止自动评审，避免无法解释的审查范围产生费用。"""

    calls = 0

    def fake_run(command: list[str], *_args: Any) -> tuple[int, str]:
        nonlocal calls
        calls += 1
        output = Path(command[command.index("--output") + 1])
        output.write_text('{"files":[]}', encoding="utf-8")
        return 0, ""

    monkeypatch.setattr(ocr, "run_ocr_command", fake_run)
    with pytest.raises(RuntimeError, match="预览字段"):
        run_review(settings, tmp_path, tmp_path / "run", SHA)
    assert calls == 1


def test_non_dashscope_review_does_not_set_dashscope_key(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """其他 provider 的密钥只进入 OCR 通用变量，不能误设为 DashScope 凭据。"""

    seen: list[dict[str, str]] = []

    def fake_run(command: list[str], env: dict[str, str], *_args: Any) -> tuple[int, str]:
        seen.append(env)
        output = Path(command[command.index("--output") + 1])
        output.write_text(json.dumps({"reviewable_count": 0, "files": []}), encoding="utf-8")
        return 0, ""

    monkeypatch.setattr(ocr, "run_ocr_command", fake_run)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "inherited-provider-key")
    monkeypatch.setenv("OCR_LLM_URL", "https://unconfigured.example")
    monkeypatch.setenv("OCR_APP_MASTER_KEY", "management-secret")
    monkeypatch.setenv("OCR_APP_GITLAB_API_TOKEN", "gitlab-secret")
    monkeypatch.setenv("OPENAI_API_KEY", "unrelated-model-secret")
    monkeypatch.setenv("NODE_OPTIONS", "--require=untrusted.js")
    other = replace(settings, ocr_provider="anthropic", ocr_api_key="other-provider-key")
    assert run_review(other, tmp_path, tmp_path / "run", SHA)[0] == "skipped"
    assert seen[0]["OCR_LLM_TOKEN"] == "other-provider-key"
    assert "DASHSCOPE_API_KEY" not in seen[0]
    assert "OCR_LLM_URL" not in seen[0]
    assert "OCR_APP_MASTER_KEY" not in seen[0]
    assert "OCR_APP_GITLAB_API_TOKEN" not in seen[0]
    assert "OPENAI_API_KEY" not in seen[0]
    assert "NODE_OPTIONS" not in seen[0]
    assert seen[0]["PATH"] == os.environ["PATH"]


def test_model_check_does_not_inherit_management_credentials(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """模型连接测试仅向 OCR 提供该模型的密钥，隔离服务自身凭据。"""

    seen: list[dict[str, str]] = []

    def fake_run(_command: list[str], env: dict[str, str], *_args: Any) -> tuple[int, str]:
        seen.append(env)
        return 0, ""

    monkeypatch.setattr(ocr, "run_ocr_command", fake_run)
    monkeypatch.setenv("OCR_APP_ADMIN_TOKEN", "management-secret")
    monkeypatch.setenv("OCR_LLM_URL", "https://unconfigured.example")
    check_model_connection(
        replace(settings, ocr_model="qwen", ocr_api_key="model-secret"), tmp_path
    )
    assert len(seen) == 3
    assert all(env["OCR_LLM_TOKEN"] == "model-secret" for env in seen)
    assert all("OCR_APP_ADMIN_TOKEN" not in env and "OCR_LLM_URL" not in env for env in seen)


def test_preview_and_review_share_one_deadline(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """预览耗时会扣减正式评审预算，不能让一次任务使用两倍超时。"""

    remaining: list[float] = []
    ticks = iter((100.0, 100.0, 105.0))
    monkeypatch.setattr(ocr.time, "monotonic", lambda: next(ticks))

    def fake_run(
        command: list[str], _env: dict[str, str], _checkout: Path, timeout: float
    ) -> tuple[int, str]:
        remaining.append(timeout)
        output = Path(command[command.index("--output") + 1])
        if "--preview" in command:
            output.write_text(
                json.dumps({"reviewable_count": 1, "files": [{"path": "main.py"}]}),
                encoding="utf-8",
            )
        else:
            output.write_text(json.dumps(result("complete")), encoding="utf-8")
        return 0, ""

    monkeypatch.setattr(ocr, "run_ocr_command", fake_run)
    assert run_review(settings, tmp_path, tmp_path / "run", SHA)[0] == "complete"
    assert remaining == [30.0, 25.0]


def test_timeout_stops_ocr_launcher_and_child(tmp_path: Path) -> None:
    """启动器超时后，继承同一进程组的评审子进程不能继续写出结果。"""

    marker = tmp_path / "orphan-result"
    child = "import pathlib,sys,time; time.sleep(2); pathlib.Path(sys.argv[1]).write_text('orphan')"
    launcher = (
        "import subprocess,sys; subprocess.run([sys.executable, '-c', sys.argv[1], sys.argv[2]])"
    )
    with pytest.raises(subprocess.TimeoutExpired):
        run_ocr_command(
            [sys.executable, "-c", launcher, child, str(marker)],
            os.environ.copy(),
            tmp_path,
            1,
        )
    time.sleep(1.2)
    assert not marker.exists()
