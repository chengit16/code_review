"""保护纯换行过滤的规则隔离、范围冻结与失败关闭；全部使用合成数据。"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from ocr_manager import feishu, ocr
from ocr_manager.config import Settings
from ocr_manager.newline_filter import (
    VERIFIED_OCR_VERSION,
    filtered_rule,
    literal_pattern,
    validate_filtered_manifest,
    validate_filtered_preview,
)
from ocr_manager.review_failures import ReviewFailure
from ocr_manager.review_observability import reason_code
from ocr_manager.review_results import project_review_result

SHA = "a" * 40
BASE = "b" * 40


def preview(paths: list[str], selected: set[str]) -> dict[str, Any]:
    """构造数量与选中路径一致的最小 OCR 预览。"""

    return {"files": [{"path": path, "will_review": path in selected} for path in paths],
            "reviewable_count": len(selected)}


@pytest.mark.parametrize(("path", "expected"), [
    ("comma,name.py", "comma,name.py"), ("x[1].py", r"x\[1\].py"),
    ("star*.py", r"star\*.py"), ("question?.py", r"question\?.py"),
    ("back\\slash.py", r"back\\slash.py"), ("#hash.py", r"\#hash.py"),
    ("!leading.py", r"\!leading.py"), ("dir/中文.py", "dir/中文.py"),
    ("bad\n.py", None), (" leading.py", None), ("trailing.py ", None),
    ("../a.py", None), ("/a.py", None), ("a//b.py", None), ("", None),
])
def test_literal_paths_are_encoded_or_retained(path: str, expected: str | None) -> None:
    """glob 字符必须转义；无法保证精确匹配的路径不能自动免审。"""

    assert literal_pattern(path) == expected


@pytest.mark.parametrize("source", ["project", "repository", "global", "default"])
def test_rules_are_copied_with_original_priority(tmp_path: Path, source: str) -> None:
    """项目 > 仓库 > 全局，原有 include、exclude 和其他字段保持不变。"""

    checkout, run = tmp_path / "checkout", tmp_path / "run"
    checkout.mkdir()
    run.mkdir()
    repository_rule = checkout / ".opencodereview/rule.json"
    repository_rule.parent.mkdir()
    contents = {name: json.dumps({"include": ["*.py"], "exclude": [name + ".py"],
                                 "rules": [{"name": name}]})
                for name in ("project", "repository", "global")}
    if source in {"project", "repository"}:
        repository_rule.write_text(contents["repository"])
    before = repository_rule.read_bytes() if repository_rule.exists() else None
    scope = {"newline_only_paths": ["comma,name.py", "already-excluded.py", " leading.py"]}
    generated = filtered_rule(
        checkout, run, scope,
        preview(["logic.py", "comma,name.py", " leading.py"],
                {"logic.py", "comma,name.py", " leading.py"}),
        contents["global"] if source != "default" else None,
        contents["project"] if source == "project" else None)
    assert generated is not None
    path, expected = generated
    rule = json.loads(path.read_text())
    assert expected == {"logic.py", " leading.py"}
    assert scope["filter_unencodable_count"] == 1
    assert rule["exclude"] == ([] if source == "default" else [source + ".py"]) + ["comma,name.py"]
    if source != "default":
        assert rule["include"] == ["*.py"] and rule["rules"] == [{"name": source}]
    assert (repository_rule.read_bytes() if repository_rule.exists() else None) == before
    assert path.stat().st_mode & 0o777 == 0o600


def test_repository_symlink_rule_is_not_followed(tmp_path: Path) -> None:
    """隔离规则合成不得通过仓库符号链接读取目录外文件。"""

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "rule.json").write_text("{}")
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / ".opencodereview").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ReviewFailure, match="符号链接"):
        filtered_rule(checkout, tmp_path, {"newline_only_paths": ["a.py"]},
                      preview(["a.py"], {"a.py"}), None, None)


def test_preview_and_manifest_cannot_silently_change_scope() -> None:
    """误伤同名文件、丢失原始文件或正式范围漂移均明确失败，不修改 manifest。"""

    original = preview(["a.py", "dir/a.py"], {"a.py", "dir/a.py"})
    for incorrect in (preview(["a.py", "dir/a.py"], set()),
                      preview(["dir/a.py"], {"dir/a.py"})):
        with pytest.raises(ReviewFailure):
            validate_filtered_preview(original, incorrect, {"dir/a.py"})
    result = {"manifest": {"coverage": {"selected": [{"path": "a.py"}]}}}
    frozen = json.dumps(result)
    with pytest.raises(ReviewFailure):
        validate_filtered_manifest(result, {"dir/a.py"})
    assert json.dumps(result) == frozen


@pytest.mark.parametrize("base_sha", [None, BASE])
@pytest.mark.parametrize("count", [1, 201])
def test_run_review_filters_before_limit_and_reuses_rule(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    base_sha: str | None, count: int,
) -> None:
    """零候选不调用模型，201 个文件先过滤再限额，commit/range 复用冻结规则。"""

    paths = [f"{number}.py" for number in range(count)]
    scope = {"head_sha": SHA, "base_sha": base_sha,
             "newline_only_paths": paths[:1], "excluded_count": 0}
    calls: list[list[str]] = []
    run = tmp_path / "run"

    def execute(command: list[str], env: dict[str, str], cwd: Path,
                timeout: float) -> tuple[int, str]:
        calls.append(command)
        if "--version" in command:
            code, _, stderr = ocr._execute_ocr_command(
                [sys.executable, "-c", f"print({VERIFIED_OCR_VERSION!r})"], env, cwd, timeout)
            return code, stderr
        if command[1] != "review":
            return 0, ""
        selected = set(paths)
        if "--rule" in command:
            rule = json.loads(Path(command[command.index("--rule") + 1]).read_text())
            selected -= set(rule["exclude"])
        output = Path(command[command.index("--output") + 1])
        if "--preview" in command:
            output.write_text(json.dumps(preview(paths, selected)))
        else:
            items = [{"path": path, "item_id": path} for path in sorted(selected)]
            payload = {"comments": [], "manifest": {
                "schema_version": "ocr.run-manifest/v1", "terminal_state": "complete",
                "input": {"mode": "range" if base_sha else "commit", "resolved_head": SHA,
                          **({"resolved_base": base_sha} if base_sha else {})},
                "coverage": {"selected": items, "completed": items, "reused": [],
                             "failed": [], "waived": []}}}
            output.write_text(json.dumps(payload))
        return 0, ""

    monkeypatch.setattr(ocr, "run_ocr_command", execute)
    status, result = ocr.run_review(
        replace(settings, ocr_newline_filter_enabled=True, ocr_max_files=200),
        tmp_path, run, SHA, base_sha=base_sha, scope_analysis=scope)
    reviews = [call for call in calls if call[1] == "review"]
    assert len(reviews) == (2 if count == 1 else 3)
    assert status == ("skipped" if count == 1 else "complete")
    assert scope["excluded_count"] == 1
    assert json.loads((run / "original-preview.json").read_text())["reviewable_count"] == count
    assert all("--exclude" not in call for call in calls)
    if count > 1:
        assert reviews[-1][reviews[-1].index("--rule") + 1] == str(run / "newline-filter-rule.json")
    projected = project_review_result(result)
    assert projected["input_filter"] == {"excluded_count": 1}
    if count == 1:
        assert reason_code(status, projected, None) == "newline_filtered"


def test_unverified_version_fails_before_preview(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """开启过滤但版本未知不能悄悄降级成开启状态或进入模型评审。"""

    calls: list[list[str]] = []

    def execute(command: list[str], *_args: Any) -> tuple[int, str]:
        calls.append(command)
        return 0, ""

    monkeypatch.setattr(ocr, "run_ocr_command", execute)
    with pytest.raises(ReviewFailure, match="版本未经"):
        ocr.run_review(replace(settings, ocr_newline_filter_enabled=True),
                       tmp_path, tmp_path / "run", SHA)
    assert all(call[1] != "review" for call in calls)


@pytest.mark.parametrize("fault", ["preview", "manifest"])
def test_runtime_scope_drift_is_rejected(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str,
) -> None:
    """预览误伤时模型零调用；正式 manifest 漂移时不得发布成功结果。"""

    calls: list[list[str]] = []
    paths = ["a.py", "dir/a.py"]

    def execute(command: list[str], env: dict[str, str], cwd: Path,
                timeout: float) -> tuple[int, str]:
        calls.append(command)
        if "--version" in command:
            code, _, stderr = ocr._execute_ocr_command(
                [sys.executable, "-c", f"print({VERIFIED_OCR_VERSION!r})"], env, cwd, timeout)
            return code, stderr
        if command[1] != "review":
            return 0, ""
        selected = set(paths) if "--rule" not in command else {"dir/a.py"}
        output = Path(command[command.index("--output") + 1])
        if "--preview" in command:
            if fault == "preview" and "--rule" in command:
                selected = set()
            output.write_text(json.dumps(preview(paths, selected)))
        else:
            items = [{"item_id": "a.py", "path": "a.py"}]
            output.write_text(json.dumps({"comments": [], "manifest": {
                "schema_version": "ocr.run-manifest/v1", "terminal_state": "complete",
                "input": {"mode": "commit", "resolved_head": SHA},
                "coverage": {"selected": items, "completed": items, "reused": [],
                             "failed": [], "waived": []}}}))
        return 0, ""

    monkeypatch.setattr(ocr, "run_ocr_command", execute)
    with pytest.raises(ReviewFailure) as error:
        ocr.run_review(replace(settings, ocr_newline_filter_enabled=True),
                       tmp_path, tmp_path / "run", SHA,
                       scope_analysis={"head_sha": SHA, "newline_only_paths": ["a.py"]})
    assert error.value.category == "scope_filter"
    formal = [call for call in calls if call[1] == "review" and "--preview" not in call]
    assert len(formal) == (0 if fault == "preview" else 1)


def test_notification_discloses_filtered_files_without_full_range_green() -> None:
    """选中范围完成仍须披露免审，不对原始全范围给出绿色通过暗示。"""

    card = feishu.build_review_card({
        "repository_name": "合成项目", "target_branch": "main", "mr_iid": 7,
        "commit_sha": SHA, "job_id": 1, "review_status": "complete", "review_error": None,
        "detail_url": "https://synthetic.invalid/jobs/1", "mr_url": "https://synthetic.invalid/mr/7",
        "commit_url": "https://synthetic.invalid/commit/" + SHA,
        "result_json": {"comments": [], "input_filter": {"excluded_count": 9},
                        "manifest": {"coverage": {"selected": [1], "completed": [1],
                                                 "failed": [], "reused": [], "waived": []}}}})
    text = json.dumps(card, ensure_ascii=False)
    assert "纯换行策略排除 9 个文件" in text
    assert "不代表原始变更全范围均由模型评审" in text
    assert card["card"]["header"]["template"] != "green"


def test_disabled_filter_does_not_trust_external_filter_claim(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """关闭开关不增加版本查询或二次预览，也不把外部同名字段当成策略排除事实。"""

    calls: list[list[str]] = []

    def execute(command: list[str], *_args: Any) -> tuple[int, str]:
        calls.append(command)
        if command[1] == "review":
            output = Path(command[command.index("--output") + 1])
            if "--preview" in command:
                output.write_text(json.dumps(preview(["a.py"], {"a.py"})))
            else:
                items = [{"item_id": "a.py", "path": "a.py"}]
                output.write_text(json.dumps({"comments": [], "input_filter": {"excluded_count": 9},
                    "manifest": {"schema_version": "ocr.run-manifest/v1",
                        "terminal_state": "complete", "input": {
                            "mode": "commit", "resolved_head": SHA},
                        "coverage": {"selected": items, "completed": items,
                                     "failed": [], "reused": [], "waived": []}}}))
        return 0, ""

    monkeypatch.setattr(ocr, "run_ocr_command", execute)
    status, result = ocr.run_review(settings, tmp_path, tmp_path / "run", SHA)
    assert status == "complete" and "input_filter" not in result
    assert sum("--preview" in call for call in calls) == 1
    assert all("--version" not in call and "--exclude" not in call for call in calls)
