"""本地提取用户意图和有界脱敏摘要；附件、工具和助手文本均不能作为操作授权。"""

from __future__ import annotations

import re

_PROBLEM = re.compile(r"报错|故障|失败|不能|无法|不生效|不显示|遗漏|漏记|丢失|卡住|点击不了|不正常")
_PROGRESS = re.compile(
    r"^(继续|继续下一步|下一步|好的|是的|开始执行|按.{0,40}执行|按照.{0,80}实施)[吧。！!\s]*$"
)


def safe_excerpt(text: str) -> str:
    """只保留最后显式请求，删除引用、代码、系统块、凭据、URL 和绝对路径；最多 800 字。"""

    text = text[-100000:]
    if "## My request:" in text:
        text = text.rsplit("## My request:", 1)[1]
    text = re.sub(
        r"<(system-reminder|environment_context|INSTRUCTIONS)\b[^>]*>.*?</\1>",
        "",
        text,
        flags=re.S | re.I,
    )
    text = re.sub(r"```.*?(?:```|$)|~~~.*?(?:~~~|$)", "[代码已省略]", text, flags=re.S)
    text = re.sub(
        r"-----BEGIN .*?PRIVATE KEY-----.*?(?:-----END .*?PRIVATE KEY-----|$)",
        "[私钥已省略]",
        text,
        flags=re.S,
    )
    text = re.sub(r"(?im)^\s*>.*$", "[引用已省略]", text)
    text = re.sub(r"(?i)\b(?:Bearer\s+|sk-|glpat-)[A-Za-z0-9._~+/=-]+", "[凭据已省略]", text)
    text = re.sub(
        r"(?i)(api[_ -]?key|password|passwd|secret|token|密码|令牌|密钥)"
        r"[\"']?\s*[=:：]\s*[\"']?[^\s,，;；\"']+",
        r"\1=[已脱敏]",
        text,
    )
    text = re.sub(r"https?://[^\s)）<>\]]+", "[地址已省略]", text)
    text = re.sub(
        r"(?:[A-Za-z]:\\|/(?:Users|home|var|private|tmp|etc)/)[^\s)）<>\]]+", "[路径已省略]", text
    )
    text = re.sub(r"[A-Za-z0-9_+/=-]{32,}", "[长标识已省略]", text)
    return re.sub(r"\s+", " ", text).strip()[:800] or "[仅附件或无可显示文本，待核实]"


def classify_excerpt(text: str) -> str:
    """规则仅决定保守受理，不判定真假、修复或上线；其余内容保留待核实而不丢弃。"""

    if _PROGRESS.fullmatch(text):
        return "progress"
    return "issue" if _PROBLEM.search(text) else "pending"
