"""复制实际生效规则并冻结独立失败子集；不改 Git、原规则或 OCR 的原始 manifest。"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ocr_manager.newline_filter import literal_pattern, selected_paths, validate_filtered_preview
from ocr_manager.review_failures import ReviewFailure


def subset_preview(checkout: Path, run_dir: Path, base: list[str], preview: dict[str, Any],
                   selected: set[str], remaining: set[str], global_rule: str | None,
                   run_preview: Callable[[list[str], str], dict[str, Any]]) -> tuple[
                       list[str], dict[str, Any]]:
    """全选中集合必须与初审精确一致，二次预览精确等于剩余项后才允许模型调用。"""

    if not remaining or not remaining <= selected or selected_paths(preview) != selected:
        raise ReviewFailure("recovery_scope", "补审原始候选与冻结覆盖不一致，未调用模型")
    # 1. 参数中的规则已包含项目/换行过滤；否则保留仓库高于全局的优先级。
    arguments = base.copy()
    if "--rule" in arguments:
        index = arguments.index("--rule")
        path = Path(arguments[index + 1])
        del arguments[index:index + 2]
    else:
        path = checkout / ".opencodereview" / "rule.json"
    if path.is_symlink() or path.parent.is_symlink():
        raise ReviewFailure("recovery_scope", "补审规则为符号链接，未调用模型")
    if path.exists() and path.stat().st_size > 1024 * 1024:
        raise ReviewFailure("recovery_scope", "补审规则超出可验证上限，未调用模型")
    rule = json.loads(path.read_text() if path.exists() else global_rule or "{}")
    patterns = [literal_pattern(path) for path in sorted(selected - remaining)]
    if (not isinstance(rule, dict) or not isinstance(rule.get("exclude", []), list)
            or any(pattern is None for pattern in patterns)):
        raise ReviewFailure("recovery_scope", "补审规则或路径无法安全表达，未调用模型")
    # 2. 只追加排除已完成/豁免项，不能使用 shell、逗号参数或临时 commit 变更输入。
    rule["exclude"] = [*rule.get("exclude", []), *patterns]
    target = run_dir / "recovery-subset-rule.json"
    target.write_text(json.dumps(rule, ensure_ascii=False), encoding="utf-8")
    target.chmod(0o600)
    (run_dir / "recovery-source-preview.json").write_text(
        json.dumps(preview, ensure_ascii=False), encoding="utf-8")
    arguments.extend(["--rule", str(target)])
    filtered = run_preview(arguments, "recovery-preview")
    validate_filtered_preview(preview, filtered, remaining)
    return arguments, filtered
