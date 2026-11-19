"""仓库订阅分支与固定执行分支；HTTP 只校验配置，Worker 按事件或任务冻结范围。"""

from __future__ import annotations

import json
import re
from typing import Any


def normalize_branches(values: list[str]) -> list[str]:
    """至少订阅一个、最多二十个真实分支；去重保持输入顺序，不支持通配符。"""

    if not values or len(values) > 20:
        raise ValueError("请选择 1 至 20 个目标分支")
    result: list[str] = []
    for value in values:
        if (
            not isinstance(value, str)
            or not re.fullmatch(r"[a-zA-Z0-9._/-]{1,200}", value)
            or value.startswith(("-", "/", "."))
            or value.endswith(("/", "."))
            or ".." in value
            or "//" in value
        ):
            raise ValueError("目标分支格式无效，不支持通配符")
        if value not in result:
            result.append(value)
    return result


def branches(repository: dict[str, Any]) -> list[str]:
    """旧内部调用仍可提供单分支；持久化 JSON 是多分支配置的事实来源。"""

    value = repository.get("target_branches")
    if isinstance(value, str):
        value = json.loads(value)
    return list(value) if value else [repository["target_branch"]]


def for_branch(repository: dict[str, Any], branch: str | None) -> dict[str, Any]:
    """选择已订阅的固定分支供 Git 使用；不得退回第一个分支审查其他分支事件。"""

    selected = branch or repository["target_branch"]
    if selected not in branches(repository):
        raise ValueError("事件或任务目标分支已取消订阅，请核对配置")
    return {**repository, "target_branch": selected}
