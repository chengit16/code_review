"""向飞书群自定义机器人投递可扫描的评审摘要。"""

from __future__ import annotations

import base64
import hashlib
import hmac
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


def send_review(webhook_url: str, job: dict[str, Any], signing_secret: str = "") -> None:
    """检查 HTTP 与飞书业务返回码；异常交给投递队列重试。"""

    result = job.get("result_json")
    if isinstance(result, str):
        import json

        result = json.loads(result)
    comments = result.get("comments", []) if isinstance(result, dict) else []
    if not isinstance(comments, list):
        comments = []
    manifest = result.get("manifest", {}) if isinstance(result, dict) else {}
    coverage = manifest.get("coverage", {}) if isinstance(manifest, dict) else {}
    counts = {
        severity: sum(
            isinstance(item, dict) and item.get("severity") == severity for item in comments
        )
        for severity in ("critical", "high", "medium", "low")
    }
    selected = coverage.get("selected", []) if isinstance(coverage, dict) else []
    completed = coverage.get("completed", []) if isinstance(coverage, dict) else []
    reused = coverage.get("reused", []) if isinstance(coverage, dict) else []
    failed = coverage.get("failed", []) if isinstance(coverage, dict) else []
    waived = coverage.get("waived", []) if isinstance(coverage, dict) else []
    lines = [
        f"仓库：{job['repository_name']} · {job['target_branch']}",
        f"MR !{job['mr_iid']} · 提交 {str(job['commit_sha'])[:10]} · 任务 #{job['job_id']}",
        f"状态：{job['review_status']} · 发现 {len(comments)} 条",
        f"覆盖：{len(completed) + len(reused)}/{len(selected)} 完成，"
        f"{len(failed)} 失败，{len(waived)} 豁免",
        "严重性：" + " · ".join(f"{name} {count}" for name, count in counts.items()),
    ]
    if job.get("review_error"):
        lines.append("执行失败，请在管理台查看诊断")
    # 卡片空间有限，优先放入高严重性发现；低级别与未分级评论仍保留在管理页。
    priority = {"critical": 0, "high": 1, "medium": 2}
    highlights = sorted(
        (item for item in comments if isinstance(item, dict) and item.get("severity") in priority),
        key=lambda item: priority[item["severity"]],
    )[:3]
    for item in highlights:
        path = str(item.get("path", "文件"))[:100]
        content = str(item.get("content", ""))[:180].replace("\n", " ")
        lines.append(f"• {path}：{content}")
    # 外部评审内容按纯文本呈现，避免评论里的 Markdown 被解释成卡片指令。
    elements: list[dict[str, Any]] = [
        {"tag": "div", "text": {"tag": "plain_text", "content": "\n".join(lines)[:3500]}}
    ]
    actions = [
        ("查看 MR", job.get("mr_url")),
        ("查看提交", job.get("commit_url")),
        ("查看任务", job.get("detail_url")),
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
    color = {"complete": "green", "partial": "orange", "failed": "red", "skipped": "grey"}.get(
        job["review_status"], "blue"
    )
    body = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": color,
                "title": {"tag": "plain_text", "content": "Open Code Review 评审结果"},
            },
            "elements": elements,
        },
    }
    if signing_secret:
        post_message(webhook_url, body, signing_secret)
    else:
        post_message(webhook_url, body)
