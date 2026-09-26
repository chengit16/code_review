"""验证飞书卡片结构与业务确认，避免把部分覆盖或密钥当作成功通知。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any

import pytest
from ocr_manager import feishu


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
            "target_branch": "main",
            "mr_iid": 7,
            "commit_sha": "a" * 40,
            "job_id": 12,
            "review_status": "partial",
            "review_error": None,
            "detail_url": "https://review.example.test/jobs/12",
            "mr_url": "https://gitlab.example.test/team/repo/-/merge_requests/7",
            "commit_url": "https://gitlab.example.test/team/repo/-/commit/" + "a" * 40,
            "result_json": json.dumps(
                {
                    "thinking": "private-reasoning",
                    "comments": [{"path": "main.py", "content": "边界错误", "severity": "high"}],
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
    assert "1/2 完成" in body["card"]["elements"][0]["text"]["content"]
    actions = body["card"]["elements"][1]["actions"]
    assert [action["text"]["content"] for action in actions] == ["查看 MR", "查看提交", "查看任务"]
    assert actions[2]["url"].endswith("/jobs/12")
    assert "private-reasoning" not in json.dumps(body)


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
                    ]
                }
            ),
        },
    )
    text = sent[0]["card"]["elements"][0]["text"]["content"]
    assert text.index("critical.py") < text.index("high.py") < text.index("medium.py")
    assert "low.py" not in text
    assert "low 1" in text


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
