"""验证飞书卡片结构与业务确认，避免把部分覆盖或密钥当作成功通知。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any

import pytest
from ocr_manager import feishu


def card_text(body: dict[str, Any]) -> str:
    """仅汇总用户可见的纯文本区块，按钮与密钥不参与结论断言。"""

    return "\n".join(
        element["text"]["content"]
        for element in body["card"]["elements"]
        if element["tag"] == "div"
    )


def test_review_card_keeps_coverage_and_no_thinking(monkeypatch: pytest.MonkeyPatch) -> None:
    """卡片呈现失败覆盖与重点发现，原始推理内容不进入飞书。"""

    sent: list[dict[str, Any]] = []

    class FakeResponse:
        """模拟飞书机器人确认成功。"""

        status_code = 200

        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict[str, int]:
            return {"code": 0}

    class FakeClient:
        """捕获请求体，测试期间不访问外部服务。"""

        def __init__(self, **_kwargs: Any) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *_args: Any) -> None:
            pass

        def post(self, _url: str, json: dict[str, Any]) -> FakeResponse:
            sent.append(json)
            return FakeResponse()

    monkeypatch.setattr(feishu.httpx, "Client", FakeClient)
    feishu.send_review(
        "https://open.feishu.cn/open-apis/bot/v2/hook/example",
        {
            "repository_name": "示例项目",
            "path_with_namespace": "team/example",
            "target_branch": "main",
            "mr_iid": 7,
            "commit_sha": "a" * 40,
            "commit_author": "张三",
            "job_id": 12,
            "review_status": "partial",
            "review_error": None,
            "detail_url": "https://review.example.test/jobs/12",
            "mr_url": "https://gitlab.example.test/team/repo/-/merge_requests/7",
            "commit_url": "https://gitlab.example.test/team/repo/-/commit/" + "a" * 40,
            "result_json": json.dumps(
                {
                    "thinking": "private-reasoning",
                    "comments": [
                        {
                            "path": "main.py",
                            "start_line": 42,
                            "content": "边界错误",
                            "severity": "high",
                        }
                    ],
                    "manifest": {
                        "coverage": {
                            "selected": [1, 2],
                            "completed": [1],
                            "reused": [],
                            "failed": [2],
                            "waived": [],
                        }
                    },
                }
            ),
        },
    )
    body = sent[0]
    assert body["msg_type"] == "interactive"
    assert body["card"]["header"]["template"] == "orange"
    assert body["card"]["header"]["title"]["content"].startswith("评审未完成")
    assert "team/example · main · SHA aaaaaaaaaa" in card_text(body)
    assert "MR !7 · 提交人：张三 · 任务 #12" in card_text(body)
    assert "已审查 1/2 个文件 · 失败 1" in card_text(body)
    assert "main.py:42" in card_text(body)
    actions = body["card"]["elements"][-1]["actions"]
    assert [action["text"]["content"] for action in actions] == [
        "查看完整评审",
        "查看 GitLab 提交",
        "查看 MR",
    ]
    assert actions[0]["url"].endswith("/jobs/12")
    assert "private-reasoning" not in json.dumps(body)
    assert all(
        element["text"]["tag"] == "plain_text"
        for element in body["card"]["elements"]
        if element["tag"] == "div"
    )


def test_card_highlights_prioritize_severity(monkeypatch: pytest.MonkeyPatch) -> None:
    """低级别发现不占用前三条摘要，高严重性发现优先展示。"""

    sent: list[dict[str, Any]] = []
    monkeypatch.setattr(feishu, "post_message", lambda _url, body: sent.append(body))
    feishu.send_review(
        "https://open.feishu.cn/open-apis/bot/v2/hook/example",
        {
            "repository_name": "示例项目",
            "target_branch": "main",
            "mr_iid": 7,
            "commit_sha": "a" * 40,
            "job_id": 12,
            "review_status": "complete",
            "result_json": json.dumps(
                {
                    "comments": [
                        {"path": "low.py", "content": "低级别", "severity": "low"},
                        {"path": "medium.py", "content": "中级别", "severity": "medium"},
                        {"path": "high.py", "content": "高级别", "severity": "high"},
                        {"path": "critical.py", "content": "紧急", "severity": "critical"},
                    ],
                    "manifest": {
                        "coverage": {
                            "selected": [1],
                            "completed": [1],
                            "reused": [],
                            "failed": [],
                            "waived": [],
                        }
                    },
                }
            ),
        },
    )
    body = sent[0]
    text = card_text(body)
    assert body["card"]["header"]["template"] == "red"
    assert text.index("critical.py") < text.index("high.py") < text.index("medium.py")
    assert "low.py" not in text
    assert "另有 1 条发现" in text
    assert "低危 1" in body["card"]["header"]["title"]["content"]


def test_card_keeps_low_severity_in_count_without_highlight() -> None:
    """只有低危发现时仍提示处理，但不在群消息中转发具体评论。"""

    body = feishu.build_review_card(
        {
            "repository_name": "示例项目",
            "target_branch": "main",
            "mr_iid": 7,
            "commit_sha": "a" * 40,
            "job_id": 12,
            "review_status": "complete",
            "result_json": {
                "comments": [{"path": "low.py", "content": "低危细节", "severity": "low"}],
                "manifest": {
                    "coverage": {
                        "selected": [1],
                        "completed": [1],
                        "reused": [],
                        "failed": [],
                        "waived": [],
                    }
                },
            },
        }
    )
    assert body["card"]["header"]["template"] == "orange"
    assert "低危 1" in body["card"]["header"]["title"]["content"]
    assert "低危细节" not in card_text(body)
    assert "查看完整评审并处理" in card_text(body)


@pytest.mark.parametrize(
    ("status", "comments", "coverage", "title", "color", "conclusion"),
    [
        (
            "complete",
            [],
            {"selected": [1], "completed": [1], "reused": [], "failed": [], "waived": []},
            "未发现问题",
            "green",
            "未发现问题",
        ),
        (
            "complete",
            [],
            {"selected": [1], "completed": [], "reused": [], "failed": [], "waived": [1]},
            "评审未完成",
            "orange",
            "覆盖不完整",
        ),
        (
            "partial",
            [],
            {"selected": [1], "completed": [], "reused": [], "failed": [1], "waived": []},
            "评审未完成",
            "orange",
            "覆盖不完整",
        ),
        ("failed", [], {}, "评审失败", "red", "不能作为无问题依据"),
        (
            "skipped",
            [],
            {"selected": [], "completed": [], "reused": [], "failed": [], "waived": []},
            "无可审查文件",
            "grey",
            "没有可审查文件",
        ),
    ],
)
def test_card_status_requires_complete_coverage(
    status: str,
    comments: list[dict[str, Any]],
    coverage: dict[str, Any],
    title: str,
    color: str,
    conclusion: str,
) -> None:
    """只有完整覆盖且零发现可显示绿色；失败与跳过不能冒充通过。"""

    body = feishu.build_review_card(
        {
            "repository_name": "示例项目",
            "target_branch": "main",
            "mr_iid": -1,
            "commit_sha": "a" * 40,
            "job_id": 12,
            "review_status": status,
            "result_json": {"comments": comments, "manifest": {"coverage": coverage}},
        }
    )
    assert body["card"]["header"]["title"]["content"].startswith(title)
    assert body["card"]["header"]["template"] == color
    assert conclusion in card_text(body)
    assert "默认分支 Push" in card_text(body)


def test_card_budget_exhaustion_cannot_be_green() -> None:
    """即使历史任务保存为完成，预算耗尽也不能生成绿色通过卡片。"""

    body = feishu.build_review_card(
        {
            "repository_name": "示例项目",
            "target_branch": "main",
            "mr_iid": 7,
            "commit_sha": "a" * 40,
            "job_id": 12,
            "review_status": "complete",
            "result_json": {
                "comments": [],
                "summary": {"budget_exceeded": True},
                "manifest": {
                    "coverage": {
                        "selected": [1],
                        "completed": [1],
                        "reused": [],
                        "failed": [],
                        "waived": [],
                    }
                },
            },
        }
    )
    assert body["card"]["header"]["template"] == "orange"
    assert "覆盖不完整" in card_text(body)


def test_feishu_business_failure_is_permanent(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTP 成功但业务码明确拒绝时不重复发送相同消息。"""

    class FakeResponse:
        """模拟业务层拒绝。"""

        status_code = 200

        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict[str, int]:
            return {"code": 19001}

    class FakeClient:
        """只返回固定响应。"""

        def __init__(self, **_kwargs: Any) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *_args: Any) -> None:
            pass

        def post(self, _url: str, **_kwargs: Any) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(feishu.httpx, "Client", FakeClient)
    with pytest.raises(feishu.FeishuDeliveryError, match="未确认") as error:
        feishu.send_review(
            "https://open.feishu.cn/open-apis/bot/v2/hook/example",
            {
                "repository_name": "示例",
                "target_branch": "main",
                "mr_iid": 1,
                "commit_sha": "a" * 40,
                "job_id": 1,
                "review_status": "failed",
            },
        )
    assert error.value.retryable is False


def test_signed_webhook_uses_fresh_feishu_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    """签名密钥只参与 HMAC，出站消息不包含密钥明文。"""

    sent: list[dict[str, Any]] = []

    class FakeResponse:
        status_code = 200

        def json(self) -> dict[str, int]:
            return {"code": 0}

    class FakeClient:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *_args: Any) -> None:
            pass

        def post(self, _url: str, json: dict[str, Any]) -> FakeResponse:
            sent.append(json)
            return FakeResponse()

    monkeypatch.setattr(feishu.httpx, "Client", FakeClient)
    monkeypatch.setattr(feishu.time, "time", lambda: 1234567890)
    feishu.send_connection_test(
        "https://open.feishu.cn/open-apis/bot/v2/hook/example", "private-key"
    )
    body = sent[0]
    assert body["timestamp"] == "1234567890"
    expected = hmac.new(b"1234567890\nprivate-key", b"", hashlib.sha256).digest()
    assert body["sign"] == base64.b64encode(expected).decode()
    assert "private-key" not in json.dumps(body)


@pytest.mark.parametrize(("status", "retryable"), [(401, False), (429, True), (503, True)])
def test_feishu_http_error_classification(
    status: int, retryable: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """永久拒绝直接停发；限流与服务端故障允许退避重试。"""

    class FakeResponse:
        """只暴露 HTTP 状态，避免测试依赖外部响应内容。"""

        status_code = status

    class FakeClient:
        """模拟带有敏感 URL 的机器人请求。"""

        def __init__(self, **_kwargs: Any) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *_args: Any) -> None:
            pass

        def post(self, _url: str, **_kwargs: Any) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(feishu.httpx, "Client", FakeClient)
    with pytest.raises(feishu.FeishuDeliveryError, match=f"HTTP {status}") as error:
        feishu.send_connection_test(
            "https://open.feishu.cn/open-apis/bot/v2/hook/private-test-token"
        )
    assert error.value.retryable is retryable
    assert "private-test-token" not in str(error.value)
