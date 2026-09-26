"""只从已核实的 MR 和固定提交读取合并前审查背景，不信任 Webhook 正文。"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from ocr_manager.git_repo import GitRepository

PATH = re.compile(r"[A-Za-z0-9._/-]{1,160}\Z")


def validate_context_paths(paths: list[str]) -> list[str]:
    """限制管理员指定的仓库文档范围，避免目录跳转及超大模型输入。"""

    if len(paths) > 3:
        raise ValueError("最多指定 3 份业务文档")
    normalized = [path.strip() for path in paths]
    for path in normalized:
        if (not PATH.fullmatch(path) or path.startswith("/") or
            any(part in {"", ".", ".."} for part in path.split("/")) or
            not path.lower().endswith((".md", ".txt"))):
            raise ValueError("业务文档路径须为仓库内的 .md 或 .txt 文件")
    if len(set(normalized)) != len(normalized):
        raise ValueError("业务文档路径不能重复")
    return normalized


def build_premerge_context(
    git: GitRepository, head_sha: str, mr: dict[str, Any],
    include_description: bool, paths: list[str],
) -> tuple[str | None, dict[str, Any] | None]:
    """背景在 Worker 已验证 MR 与 Git 对象后冻结，详情只保存来源和摘要。"""

    sections: list[str] = []
    sources: list[dict[str, Any]] = []
    description = mr.get("description")
    if include_description and isinstance(description, str) and description.strip():
        # OCR 清洗后的背景上限是 8000 字符，先给 MR 描述留固定预算。
        text = description.strip()[:2000]
        sections.append(f"MR 描述:\n{text}")
        sources.append({"kind": "mr_description", "label": "MR 描述",
                        "characters": len(text),
                        "digest": hashlib.sha256(description.encode()).hexdigest()[:12]})
    for path in paths:
        text = git.read_context_file(head_sha, path, 1600)
        sections.append(f"仓库文档 {path}:\n{text}")
        sources.append({"kind": "repository_document", "label": path,
                        "characters": len(text),
                        "digest": hashlib.sha256(text.encode()).hexdigest()[:12]})
    if not sections:
        return None, None
    background = "\n\n".join(sections)
    if len(background) > 7500:
        raise ValueError("合并前业务上下文超过 OCR 输入上限")
    return background, {"sources": sources,
                        "digest": hashlib.sha256(background.encode()).hexdigest()[:12]}
