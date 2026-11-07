"""生成隔离的精确路径排除规则并核对覆盖；不改原规则、Git 对象或 OCR manifest。"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ocr_manager.review_failures import ReviewFailure

VERIFIED_OCR_VERSION = "open-code-review v1.12.9 (bccbc15)"


def literal_pattern(path: str) -> str | None:
    """按已验证的 OCR glob 语法转义相对路径；控制字符路径保守保留纳入。"""

    if (not path or path.startswith("/") or any(part in {"", ".", ".."}
                                             for part in path.split("/"))
        or any(ord(char) < 32 or ord(char) == 127 for char in path)
        or path != path.strip()):
        return None
    return "".join("\\" + char if char in "\\*?[]!#" else char for char in path)


def filtered_rule(checkout: Path, run_dir: Path, scope: dict[str, Any],
                  preview: dict[str, Any], global_rule: str | None,
                  project_rule: str | None) -> tuple[Path, set[str]] | None:
    """复制实际生效的规则后追加转义排除，返回必须精确匹配的预期候选集合。"""

    # 1. 仅从原预览实际选中路径中排除已由固定对象确认的纯换行文件。
    selected = selected_paths(preview)
    paths = sorted(selected.intersection(scope["newline_only_paths"]))
    patterns = {path: literal_pattern(path) for path in paths}
    removable = {path for path, pattern in patterns.items() if pattern is not None}
    scope["filter_unencodable_count"] = len(paths) - len(removable)
    if not removable:
        return None
    # 2. 保留项目 > 仓库 > 全局的原有优先级，绝不修改仓库或覆盖原规则内容。
    content = project_rule
    if content is None:
        repository_rule = checkout / ".opencodereview" / "rule.json"
        if repository_rule.is_symlink() or repository_rule.parent.is_symlink():
            raise ReviewFailure("scope_filter", "仓库规则为符号链接，不能安全生成过滤规则")
        if repository_rule.exists():
            if repository_rule.stat().st_size > 1024 * 1024:
                raise ReviewFailure("scope_filter", "仓库规则超过过滤合成上限")
            content = repository_rule.read_text(encoding="utf-8")
        else:
            content = global_rule
    rule = json.loads(content) if content is not None else {}
    if not isinstance(rule, dict) or not isinstance(rule.get("exclude", []), list):
        raise ReviewFailure("scope_filter", "原规则结构不兼容，未进入正式评审")
    rule["exclude"] = [*rule.get("exclude", []), *[patterns[path] for path in sorted(removable)]]
    # 3. 冻结输入工件供预览和正式评审共用，数量在预览核对成功后才标记已排除。
    path = run_dir / "newline-filter-rule.json"
    path.write_text(json.dumps(rule, ensure_ascii=False), encoding="utf-8")
    path.chmod(0o600)
    scope["filter_requested_paths"] = sorted(removable)
    return path, selected - removable


def selected_paths(preview: dict[str, Any]) -> set[str]:
    """读取已由主解析器校验的预览，区分原始变更集合与实际候选。"""

    return {item["path"] for item in preview["files"] if item["will_review"]}


def validate_filtered_preview(original: dict[str, Any], filtered: dict[str, Any],
                              expected: set[str]) -> None:
    """正式调用前拒绝新增、遗漏或误排除；失败不能降级成零文件跳过。"""

    if (selected_paths(filtered) != expected
        or {item["path"] for item in filtered["files"]}
        != {item["path"] for item in original["files"]}):
        raise ReviewFailure("scope_filter", "换行过滤预览集合不一致，未调用模型")


def validate_filtered_manifest(result: dict[str, Any], expected: set[str]) -> None:
    """只核验原始 manifest，不补写或修正正式覆盖；不一致不得发布为成功。"""

    selected = result["manifest"]["coverage"]["selected"]
    actual = [item.get("path") for item in selected]
    if (any(not isinstance(path, str) for path in actual) or len(actual) != len(expected)
        or set(actual) != expected):
        raise ReviewFailure("scope_filter", "正式 manifest 与冻结过滤预览不一致，结果不可信")


def prepare_filtered_preview(
    checkout: Path, run_dir: Path, scope: dict[str, Any],
    original: dict[str, Any], base: list[str], global_rule: str | None,
    project_rule: str | None, run_preview: Callable[[list[str], str], dict[str, Any]],
) -> tuple[list[str], dict[str, Any], set[str] | None]:
    """同一预览预算内冻结排除规则；调用方负责版本校验、结果解析及数据库写入。"""

    generated = filtered_rule(checkout, run_dir, scope, original, global_rule, project_rule)
    if generated is None:
        scope["filter_reason"] = "未找到可安全排除的已选中纯换行文件，保持原范围"
        return base, original, None
    rule_path, expected = generated
    filtered_base = base.copy()
    if "--rule" in filtered_base:
        index = filtered_base.index("--rule")
        del filtered_base[index:index + 2]
    filtered_base.extend(["--rule", str(rule_path)])
    original_path = run_dir / "original-preview.json"
    original_path.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")
    original_path.chmod(0o600)
    filtered = run_preview(filtered_base, "filtered-preview")
    validate_filtered_preview(original, filtered, expected)
    scope.update(mode="exclude_verified_paths",
                 excluded_count=len(selected_paths(original) - expected),
                 filter_reason="已通过双预览校验，精确排除确认仅 CRLF/LF 变化的选中文件")
    return filtered_base, filtered, expected
