"""向飞书群自定义机器人投递可扫描的评审摘要。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

import httpx


class FeishuDeliveryError(RuntimeError):
    """只携带安全错误摘要及是否适合自动重试，不暴露机器人 URL。"""

    def __init__(self, message: str, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


def send_connection_test(webhook_url: str, signing_secret: str = "") -> None:
    """向目标群发送一条可辨识的测试消息；结果由独立诊断任务保存。"""

    post_message(
        webhook_url,
        {"msg_type": "text", "content": {"text": "Open Code Review 连接测试"}},
        signing_secret,
    )


def post_message(webhook_url: str, body: dict[str, Any], signing_secret: str = "") -> None:
    """统一检查 HTTP 与飞书业务状态码，调用方负责避免泄露 URL。"""

    if signing_secret:
        # 飞书机器人签名以每次发送的时间戳计算；重试不能复用过期签名。
        timestamp = str(int(time.time()))
        key = f"{timestamp}\n{signing_secret}".encode()
        body = body | {
            "timestamp": timestamp,
            "sign": base64.b64encode(hmac.new(key, b"", hashlib.sha256).digest()).decode(),
        }
    try:
        with httpx.Client(timeout=10) as client:
            response = client.post(webhook_url, json=body)
    except httpx.RequestError as error:
        raise FeishuDeliveryError("飞书网络连接失败", retryable=True) from error
    status = response.status_code
    if not 200 <= status < 300:
        # 限流与服务端故障可恢复；其他 HTTP 拒绝需要管理员修正配置。
        raise FeishuDeliveryError(
            f"飞书返回 HTTP {status}", retryable=status == 429 or status >= 500
        )
    try:
        data = response.json()
    except ValueError as error:
        raise FeishuDeliveryError("飞书响应格式无效", retryable=True) from error
    if not isinstance(data, dict) or data.get("code") != 0:
        # 自定义机器人已明确拒绝消息时，重复发送相同内容不会改变结论。
        raise FeishuDeliveryError("飞书未确认消息投递成功", retryable=False)


def _plain_section(content: str) -> dict[str, Any]:
    return {"tag": "div", "text": {"tag": "plain_text", "content": content}}


def _coverage_state(
    coverage: dict[str, Any], status: str, budget_exceeded: bool
) -> tuple[str, bool]:
    # OCR 成功状态不等于全量覆盖；豁免或预算耗尽时不能发绿色结论。
    fields = ("selected", "completed", "reused", "failed", "waived")
    has_coverage = all(isinstance(coverage.get(field), list) for field in fields)
    if not has_coverage:
        return "覆盖：结果记录不可用", False
    selected = coverage["selected"]
    reviewed = len(coverage["completed"]) + len(coverage["reused"])
    failed = len(coverage["failed"])
    waived = len(coverage["waived"])
    is_complete = (
        status == "complete"
        and not budget_exceeded
        and bool(selected)
        and reviewed == len(selected)
        and failed == 0
        and waived == 0
    )
    return (
        f"覆盖：已审查 {reviewed}/{len(selected)} 个文件 · 失败 {failed} · 豁免 {waived}",
        is_complete,
    )


def _review_status(
    status: str, finding_count: int, counts: dict[str, int], is_complete: bool
) -> tuple[str, str, str]:
    # 状态色表达评审结论；有发现的 complete 也不能使用绿色。
    if status == "failed":
        return "评审失败", "red", "结论：评审执行失败，本次结果不能作为无问题依据。"
    if status == "skipped":
        return "无可审查文件", "grey", "结论：本次提交没有可审查文件。"
    if not is_complete:
        return (
            "评审未完成",
            "orange",
            f"结论：评审覆盖不完整，已发现 {finding_count} 条问题；请查看任务详情。",
        )
    if finding_count:
        color = "red" if counts["critical"] or counts["high"] else "orange"
        return "需处理", color, f"结论：发现 {finding_count} 条问题，请查看完整评审并处理。"
    return "未发现问题", "green", "结论：已完成全部可审查文件，未发现问题。"


def _finding_sections(
    findings: list[dict[str, Any]], minimum_severity: str = "medium"
) -> list[dict[str, Any]]:
    # OCR 评论是不可信文本，只作为 plain_text 放入卡片，不解释 Markdown 或 HTML。
    priority = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    labels = {"critical": "严重", "high": "高危", "medium": "中危", "low": "低危"}

    def rank(item: dict[str, Any]) -> int:
        severity = item.get("severity")
        return priority.get(severity, 4) if isinstance(severity, str) else 4

    # 阈值只筛选群消息摘录，不改变评审结论、完整发现数量和严重级别计数。
    threshold = priority.get(minimum_severity, priority["medium"])
    highlights = sorted((item for item in findings if rank(item) <= threshold), key=rank)[:3]
    if not highlights:
        return []
    elements: list[dict[str, Any]] = [{"tag": "hr"}, _plain_section("重点发现")]
    for item in highlights:
        raw_severity = item.get("severity")
        severity = labels.get(raw_severity, "未分级") if isinstance(raw_severity, str) else "未分级"
        content = " ".join(str(item.get("content") or "查看完整评审了解详情").split())[:140]
        path = " ".join(str(item.get("path") or "文件").split())[:100]
        line = item.get("start_line")
        location = (
            f"{path}:{line}"
            if isinstance(line, int) and not isinstance(line, bool) and line > 0
            else path
        )
        elements.append(_plain_section(f"{severity} · {content}\n{location}"))
    if len(findings) > len(highlights):
        elements.append(
            _plain_section(f"另有 {len(findings) - len(highlights)} 条发现，请查看完整评审。")
        )
    return elements


def build_review_card(job: dict[str, Any]) -> dict[str, Any]:
    """从已保存的 OCR 事实构造卡片；未完整覆盖时绝不输出绿色无问题结论。"""

    # 1. 只提取可展示的评审字段，不把原始推理或代码片段转发到群聊。
    result = job.get("result_json")
    if isinstance(result, str):
        result = json.loads(result)
    comments = result.get("comments", []) if isinstance(result, dict) else []
    findings = (
        [item for item in comments if isinstance(item, dict)] if isinstance(comments, list) else []
    )
    manifest = result.get("manifest", {}) if isinstance(result, dict) else {}
    coverage = manifest.get("coverage", {}) if isinstance(manifest, dict) else {}
    if not isinstance(coverage, dict):
        coverage = {}
    summary = result.get("summary", {}) if isinstance(result, dict) else {}
    budget_exceeded = isinstance(summary, dict) and summary.get("budget_exceeded") is True
    counts = {
        severity: sum(item.get("severity") == severity for item in findings)
        for severity in ("critical", "high", "medium", "low")
    }

    # 2. 覆盖与严重性共同决定顶部状态，不能只看 Worker 的终态。
    coverage_text, is_complete = _coverage_state(coverage, job["review_status"], budget_exceeded)
    title, color, conclusion = _review_status(
        job["review_status"], len(findings), counts, is_complete
    )

    severity_labels = ("critical", "high", "medium", "low")
    severity_names = {"critical": "严重", "high": "高危", "medium": "中危", "low": "低危"}
    severity_counts = [
        f"{severity_names[severity]} {counts[severity]}"
        for severity in severity_labels
        if counts[severity]
    ]
    other_count = len(findings) - sum(counts.values())
    if other_count:
        severity_counts.append(f"未分级 {other_count}")
    header = " · ".join((title, *severity_counts))
    repository = str(job.get("path_with_namespace") or job["repository_name"])
    source = f"MR !{job['mr_iid']}" if job["mr_iid"] > 0 else "默认分支 Push"
    metadata = (
        f"{repository[:100]} · {job['target_branch']} · SHA {str(job['commit_sha'])[:10]}\n"
        f"{source} · 任务 #{job['job_id']}"
    )
    elements: list[dict[str, Any]] = [
        _plain_section(metadata),
        _plain_section(coverage_text),
        _plain_section(conclusion),
    ]
    if findings:
        minimum_severity = str(job.get("notification_min_severity") or "medium")
        elements.extend(_finding_sections(findings, minimum_severity))

    # 3. 外部链接仅来自已有的受控任务与 GitLab URL，不从 OCR 评论中生成操作。
    actions = [
        ("查看完整评审", job.get("detail_url")),
        ("查看 GitLab 提交", job.get("commit_url")),
        ("查看 MR", job.get("mr_url")),
    ]
    if any(url for _label, url in actions):
        elements.append(
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": label},
                        "url": url,
                        "type": "default",
                    }
                    for label, url in actions
                    if url
                ],
            }
        )
    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": color,
                "title": {"tag": "plain_text", "content": header},
            },
            "elements": elements,
        },
    }


def send_review(webhook_url: str, job: dict[str, Any], signing_secret: str = "") -> None:
    """发送结构化卡片并校验飞书业务响应，失败由独立投递队列重试。"""

    body = build_review_card(job)
    if signing_secret:
        post_message(webhook_url, body, signing_secret)
    else:
        post_message(webhook_url, body)
