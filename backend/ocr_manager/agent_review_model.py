"""适配单一 Chat Completions 端点；每页先记账后调用，限制内容、用量和时间。"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict
from typing import Annotated, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field

from ocr_manager.agent_review_config import POLICY, AgentReviewConfig
from ocr_manager.agent_review_store import record_usage, reserve_call
from ocr_manager.cancellation import check_cancellation
from ocr_manager.review_prototype.graph import ModelPageFailure, ReadRequest
from ocr_manager.review_prototype.input import DiffPage
from ocr_manager.review_prototype.result import Evidence, Finding
from ocr_manager.storage import Store

MAX_REQUEST_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = 128 * 1024


class ModelCandidate(BaseModel):
    """模型只选择页内行号；摘录与文件定位由 Worker 计算。"""

    model_config = ConfigDict(strict=True, extra="forbid")
    title: Annotated[str, Field(min_length=1, max_length=300)]
    trigger: Annotated[str, Field(min_length=1, max_length=1500)]
    impact: Annotated[str, Field(min_length=1, max_length=1500)]
    side: Literal["base", "head"]
    line: Annotated[int, Field(gt=0)]


class ModelPage(BaseModel):
    """外部候选页只接受明确的 JSON 结果；缺字段不能表述为零发现。"""

    model_config = ConfigDict(strict=True, extra="forbid")
    findings: Annotated[list[ModelCandidate], Field(max_length=10)]


class ModelUsage(BaseModel):
    """采用供应商实际返回的计数；拒绝字符串、负数以及不合理的计数。"""

    model_config = ConfigDict(strict=True)
    prompt_tokens: Annotated[int, Field(gt=0, le=10_000_000)]
    completion_tokens: Annotated[int, Field(ge=0, le=10_000_000)]
    total_tokens: Annotated[int, Field(gt=0, le=20_000_000)]


def _findings(page: DiffPage, content: str) -> tuple[Finding, ...]:
    values = ModelPage.model_validate_json(content)
    findings = []
    for item in values.findings:
        excerpt = next((line.text.rstrip("\n") for line in page.lines
                        if line.number(item.side) == item.line), None)
        if excerpt is None:
            raise ModelPageFailure("model_response")
        findings.append(Finding(item.title, item.trigger, item.impact,
                                Evidence(page.hunk_id, page.path, item.side, item.line, excerpt)))
    return tuple(dict.fromkeys(findings))


class ChatPageModel:
    """差异工具在本地顺序读取；模型只对已交付页推理，不获得任意工具执行权。"""

    def __init__(
        self, store: Store, run_id: int, config: AgentReviewConfig, client: httpx.Client,
        *, deadline: float,
    ) -> None:
        self.store, self.run_id, self.config, self.client = store, run_id, config, client
        self.deadline = deadline

    def request_diff(self, available: ReadRequest) -> ReadRequest:
        """将本地图允许的下一页交给受限工具，继续前检查取消和截止时间。"""

        check_cancellation()
        self._remaining()
        return available

    def _remaining(self) -> float:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError()
        return remaining

    def _response(self, payload: bytes, call_id: str) -> object:
        headers = {"Content-Type": "application/json", "Accept-Encoding": "identity",
                   "X-Client-Request-Id": call_id}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        data = bytearray()
        try:
            with self.client.stream(
                "POST", self.config.endpoint, content=payload, headers=headers,
                timeout=httpx.Timeout(min(20.0, self._remaining())),
                follow_redirects=False,
            ) as response:
                response.raise_for_status()
                for chunk in response.iter_raw():
                    check_cancellation()
                    self._remaining()
                    if len(data) + len(chunk) > MAX_RESPONSE_BYTES:
                        raise ModelPageFailure("model_response")
                    data.extend(chunk)
        except httpx.TimeoutException:
            raise TimeoutError() from None
        except httpx.HTTPError:
            raise ModelPageFailure("model_unavailable") from None
        return json.loads(data)

    def inspect(self, page: DiffPage) -> tuple[Finding, ...]:
        """把受限差异作为数据发送；无账目、无有效候选或中断时停止当前尝试。"""

        # 1. Tokenizer 因端点而异，以请求字节数加封装余量保守预留。
        config = self.config
        payload = json.dumps({
            "model": config.model,
            "messages": [
                {"role": "system", "content": POLICY},
                {"role": "user", "content": json.dumps(asdict(page), ensure_ascii=False)},
            ],
            "response_format": {"type": "json_object"},
            "max_completion_tokens": config.max_output_tokens,
        }, ensure_ascii=False, separators=(",", ":")).encode()
        reserved = len(payload) + 128 + config.max_output_tokens
        check_cancellation()
        self._remaining()
        if len(payload) > MAX_REQUEST_BYTES:
            raise ModelPageFailure("model_budget")
        call_id = reserve_call(
            self.store, self.run_id, page.hunk_id, page.start,
            reserved, config.max_reads, config.max_total_tokens, config.max_source_tokens,
        )
        if call_id is None:
            check_cancellation()
            raise ModelPageFailure("model_budget")

        # 2. 默认调用状态为费用未知；中断和响应未到不自动补发。
        try:
            envelope = self._response(payload, call_id)
            if not isinstance(envelope, dict):
                raise ModelPageFailure("model_response")
            usage = ModelUsage.model_validate(envelope.get("usage"))
            if usage.total_tokens != usage.prompt_tokens + usage.completion_tokens:
                raise ModelPageFailure("model_response")
            raw_model = envelope.get("model")
            provider_model = (
                raw_model if isinstance(raw_model, str)
                and re.fullmatch(r"[a-zA-Z0-9_.:/-]{1,160}", raw_model)
                and (not config.api_key or config.api_key not in raw_model) else None
            )
            record_usage(
                self.store, call_id, usage.prompt_tokens, usage.completion_tokens, provider_model,
            )
            if usage.total_tokens > reserved or usage.completion_tokens > config.max_output_tokens:
                raise ModelPageFailure("model_budget")

            # 3. 用量和质量独立。即使响应被截断，也保留返回的计费计数。
            choice, = envelope["choices"]
            if choice["finish_reason"] != "stop":
                raise ModelPageFailure("model_response")
            content = choice["message"]["content"]
            if not isinstance(content, str):
                raise ModelPageFailure("model_response")
            findings = _findings(page, content)
            if config.api_key and any(
                config.api_key in value for finding in findings
                for value in (finding.title, finding.trigger, finding.impact)
            ):
                raise ModelPageFailure("model_response")
            return findings
        except (KeyError, TypeError, ValueError):
            raise ModelPageFailure("model_response") from None
