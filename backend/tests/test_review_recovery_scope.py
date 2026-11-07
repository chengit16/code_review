"""用合成命令验证补审与规则/换行过滤组合；不联网、不调用模型，不伪造 Git 提交。"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from ocr_manager import ocr
from ocr_manager.config import Settings
from ocr_manager.newline_filter import VERIFIED_OCR_VERSION, literal_pattern
from ocr_manager.review_failures import ReviewFailure
from test_newline_filter import BASE, SHA, preview

PATHS = ["done/comma,name[1].py", "pending/space name.py", "newline.py"]


@pytest.mark.parametrize("source", ["project", "repository", "global", "default"])
@pytest.mark.parametrize("filtered", [False, True])
@pytest.mark.parametrize("base_sha", [None, BASE])
def test_recovery_reuses_effective_rules_and_fixed_input(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    source: str, filtered: bool, base_sha: str | None,
) -> None:
    """组合过滤只能减少失败集合，规则字段与跨文件上下文保留，两个预览复用相同输入。"""

    # 1. 构造各规则优先级和完整 checkout，保留未选中的上下文文件。
    checkout, run = tmp_path / "checkout", tmp_path / "run"
    checkout.mkdir()
    # 未选中为评审项的上下文仍在 checkout，不通过删除文件实现子集。
    context = checkout / "dependency.py"
    context.write_text("CONTEXT = True\n")
    contents = {name: json.dumps({
        "exclude": [name + ".py"], "include": ["**/*.py"],
        "merge_system_rule": False, "rules": [{"name": name}],
    }) for name in ("project", "repository", "global")}
    repository_rule = checkout / ".opencodereview/rule.json"
    if source in {"project", "repository"}:
        repository_rule.parent.mkdir()
        repository_rule.write_text(contents["repository"])
    original = repository_rule.read_bytes() if repository_rule.exists() else None
    selected = set(PATHS[:-1] if filtered else PATHS)
    remaining = selected - {PATHS[0]}
    calls: list[list[str]] = []

    # 2. 合成命令核对每次固定输入、实际规则和预览/正式评审的路径集合。
    def execute(command: list[str], env: dict[str, str], cwd: Path,
                timeout: float) -> tuple[int, str]:
        calls.append(command)
        assert Path(env["HOME"]) == run / "home"
        if "--version" in command:
            code, _, stderr = ocr._execute_ocr_command(
                [sys.executable, "-c", f"print({VERIFIED_OCR_VERSION!r})"],
                env, cwd, timeout)
            return code, stderr
        if command[1] != "review":
            return 0, ""
        assert command[command.index("--repo") + 1] == str(checkout)
        if base_sha:
            assert command[command.index("--from") + 1] == base_sha
            assert command[command.index("--to") + 1] == SHA
        else:
            assert command[command.index("--commit") + 1] == SHA
        rule_path = (Path(command[command.index("--rule") + 1]) if "--rule" in command
                     else repository_rule if repository_rule.exists()
                     else run / "home/.opencodereview/rule.json")
        rule = json.loads(rule_path.read_text()) if rule_path.exists() else {}
        exclusions = rule.get("exclude", [])
        active = {path for path in PATHS if literal_pattern(path) not in exclusions}
        if source != "default":
            assert rule["rules"] == [{"name": source}]
            assert rule["include"] == ["**/*.py"]
            assert rule["merge_system_rule"] is False
            assert exclusions[0] == source + ".py"
        output = Path(command[command.index("--output") + 1])
        if "--preview" in command:
            output.write_text(json.dumps(preview(PATHS, active)))
        else:
            assert active == remaining
            assert context.read_text() == "CONTEXT = True\n"
            assert rule_path == run / "recovery-subset-rule.json"
            items = [{"path": path, "item_id": path} for path in sorted(active)]
            output.write_text(json.dumps({"comments": [], "manifest": {
                "schema_version": "ocr.run-manifest/v1", "terminal_state": "complete",
                "input": {"mode": "range" if base_sha else "commit", "resolved_head": SHA,
                          **({"resolved_base": base_sha} if base_sha else {})},
                "coverage": {"selected": items, "completed": items, "failed": [],
                             "reused": [], "waived": []}}}))
        return 0, ""

    # 3. 运行正式编排而非另造选择算法，确认原规则不变且只有一个正式评审批次。
    monkeypatch.setattr(ocr, "run_ocr_command", execute)
    status, result = ocr.run_review(
        replace(settings, ocr_newline_filter_enabled=filtered), checkout, run, SHA,
        global_rule=contents["global"] if source != "default" else None,
        project_rule=contents["project"] if source == "project" else None,
        base_sha=base_sha, scope_analysis={
            "head_sha": SHA, "base_sha": base_sha, "newline_only_paths": [PATHS[-1]],
            "excluded_count": 0}, recovery_selection=(selected, remaining))
    assert status == "complete"
    assert {item["path"] for item in result["manifest"]["coverage"]["selected"]} == remaining
    assert sum("--preview" in call for call in calls) == (3 if filtered else 2)
    assert sum(call[1] == "review" and "--preview" not in call for call in calls) == 1
    assert (repository_rule.read_bytes() if repository_rule.exists() else None) == original
    assert (run / "recovery-subset-rule.json").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("fault", ["source", "preview", "manifest"])
def test_recovery_scope_drift_fails_closed(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str,
) -> None:
    """源或子集预览漂移时零模型调用；正式范围漂移不生成可发布结论。"""

    calls: list[list[str]] = []

    def execute(command: list[str], env: dict[str, str], cwd: Path,
                timeout: float) -> tuple[int, str]:
        calls.append(command)
        if "--version" in command:
            code, _, stderr = ocr._execute_ocr_command(
                [sys.executable, "-c", f"print({VERIFIED_OCR_VERSION!r})"],
                env, cwd, timeout)
            return code, stderr
        if command[1] != "review":
            return 0, ""
        output = Path(command[command.index("--output") + 1])
        selected = set(PATHS[1:]) if "--rule" in command else set(PATHS)
        if "--preview" in command:
            if fault == "source" or fault == "preview" and "--rule" in command:
                selected = set(PATHS)
                selected.remove(PATHS[-1])
            output.write_text(json.dumps(preview(PATHS, selected)))
        else:
            items = [{"path": PATHS[0], "item_id": "unexpected"}]
            output.write_text(json.dumps({"comments": [], "manifest": {
                "schema_version": "ocr.run-manifest/v1", "terminal_state": "complete",
                "input": {"mode": "commit", "resolved_head": SHA},
                "coverage": {"selected": items, "completed": items, "failed": [],
                             "reused": [], "waived": []}}}))
        return 0, ""

    monkeypatch.setattr(ocr, "run_ocr_command", execute)
    with pytest.raises(ReviewFailure):
        ocr.run_review(settings, tmp_path, tmp_path / "run", SHA,
                       recovery_selection=(set(PATHS), set(PATHS[1:])))
    assert sum(call[1] == "review" and "--preview" not in call for call in calls) == (
        1 if fault == "manifest" else 0)
