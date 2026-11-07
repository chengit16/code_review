"""读取显式配置的中文项目台账；只解析来源，不抓取聊天，不凭自然语言推断验收状态。"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from ocr_manager.improvement_contracts import ImprovementContent

_HEADING = re.compile(r"^### (PI-\d{8}-\d{3})｜(.+)$")
_FIELD = re.compile(r"^- ([^：]+)：(.*)$")
_TEXT_FIELDS = {
    "现象或目标": "description", "原因或分析": "analysis", "处理与改进": "solution",
    "本地验证": "validation_evidence", "部署生效": "deployment_evidence",
    "遗留与下一步": "next_steps",
}


@dataclass(frozen=True)
class LogEntry:
    """一个来源编号的一次追加；原文摘要用于防止修改历史后静默覆盖页面。"""

    source_id: str
    title: str
    fields: dict[str, str]
    digest: str


def read_log(path: Path) -> dict[str, list[LogEntry]]:
    """最多读取 5 MiB 的稳定本地文件，忽略模板代码块；空、损坏或半写入来源拒绝。"""

    before = path.stat()
    if before.st_size > 5 * 1024 * 1024:
        raise ValueError("台账超过同步大小上限")
    with path.open("rb") as source:
        content = source.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024:
        raise ValueError("台账超过同步大小上限")
    text = content.decode("utf-8")
    after = path.stat()
    if (before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_ino, after.st_size, after.st_mtime_ns
    ):
        raise ValueError("台账正在写入，下轮再读取")
    groups: dict[str, list[LogEntry]] = {}
    current: tuple[str, str] | None = None
    lines: list[str] = []
    fence: str | None = None

    def finish() -> None:
        if current is None:
            return
        fields: dict[str, str] = {}
        key: str | None = None
        inside_code = False
        for line in lines:
            if line.startswith(("```", "~~~")):
                inside_code = not inside_code
            match = _FIELD.fullmatch(line) if not inside_code else None
            if match:
                key, value = match.groups()
                if key in fields:
                    raise ValueError("同一条台账字段重复")
                fields[key] = value.strip()
            elif line.strip() and key:
                fields[key] += "\n" + line
        required = {"记录日期", "现象或目标", "处理与改进", "代码修改", "本地验证", "部署生效"}
        if not required <= fields.keys():
            raise ValueError("台账缺少必要事实字段")
        source_id, title = current
        digest = hashlib.sha256((title + "\n" + "\n".join(lines).strip()).encode()).hexdigest()
        groups.setdefault(source_id, []).append(LogEntry(source_id, title, fields, digest))

    for line in text.splitlines():
        if line.startswith(("```", "~~~")):
            marker = line[:3]
            fence = None if fence == marker else marker if fence is None else fence
            if current:
                lines.append(line)
            continue
        match = _HEADING.fullmatch(line) if fence is None else None
        if match:
            finish()
            current = (match[1], match[2])
            lines = []
        elif current:
            lines.append(line)
    if fence is not None:
        raise ValueError("台账代码块未闭合")
    finish()
    if not groups:
        raise ValueError("没有可同步的台账记录")
    return groups


def entry_content(entry: LogEntry, previous: ImprovementContent | None) -> ImprovementContent:
    """追加只覆盖有明确来源的字段；状态默认未知，证据与正文全部保留在版本快照。"""

    values = previous.model_dump() if previous else {
        "title": f"{entry.source_id}｜{entry.title}", "description": entry.fields["现象或目标"],
        "kind": "improvement", "status": "investigating", "deployment_state": "unknown",
    }
    for source, target in _TEXT_FIELDS.items():
        if source in entry.fields:
            values[target] = entry.fields[source]
    if values.get("next_steps", "") in {"无", "无。"}:
        values["next_steps"] = ""
    values["analysis"] = (entry.fields.get("原因或分析", "") + "\n\n来源进展：" +
        entry.fields.get("类型与进展", "未标注") + "\n代码事实：" + entry.fields["代码修改"] +
        "\n记录日期：" + entry.fields["记录日期"] +
        ("\n排查与无效尝试：" + entry.fields["排查与无效尝试"]
         if entry.fields.get("排查与无效尝试") else ""))
    values["references"] = (f"来源编号：{entry.source_id}\n" +
        "来源：docs/problem-improvement-log.md\n" +
        "关联记录：" + entry.fields.get("关联记录", "无") + "\n" +
        entry.fields.get("关联文件或证据", ""))
    known = {*_TEXT_FIELDS, "类型与进展", "代码修改", "记录日期", "排查与无效尝试",
             "关联记录", "关联文件或证据", "同步状态"}
    for key, value in entry.fields.items():
        if key not in known:
            values["analysis"] += f"\n{key}：{value}"
    if "同步状态" in entry.fields:
        states = json.loads(entry.fields["同步状态"])
        allowed = {"kind", "category", "status", "code_state", "verification_state",
                   "deployment_state"}
        if not isinstance(states, dict) or not states.keys() <= allowed:
            raise ValueError("同步状态包含非状态字段")
        values.update(states)
    return ImprovementContent.model_validate(values)
