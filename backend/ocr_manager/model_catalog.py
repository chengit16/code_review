"""查询模型服务公开的模型目录，不保存请求中的端点或凭据。"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx


def _catalog_url(provider: str, base_url: str) -> tuple[str, bool]:
    """将支持的 Provider 转为模型目录地址，并标记是否使用 Anthropic 鉴权。"""

    endpoint = base_url.strip().rstrip("/")
    if endpoint:
        try:
            parsed = urlparse(endpoint)
        except ValueError:
            raise ValueError("Base URL 必须是无凭据的 HTTPS API 根地址") from None
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or
                parsed.password or parsed.query or parsed.fragment):
            raise ValueError("Base URL 必须是无凭据的 HTTPS API 根地址")
        return f"{endpoint}/models", False
    if provider == "dashscope":
        return "https://dashscope.aliyuncs.com/compatible-mode/v1/models", False
    if provider == "openai":
        return "https://api.openai.com/v1/models", False
    if provider == "anthropic":
        return "https://api.anthropic.com/v1/models", True
    raise ValueError("该 Provider 需要填写 Base URL 才能获取模型")


def fetch_model_catalog(provider: str, base_url: str, api_key: str) -> list[str]:
    """请求受支持的 HTTPS 模型目录；密钥仅用于请求头，不写日志或持久化。"""

    api_key = api_key.strip()
    if not api_key:
        raise ValueError("请先填写 API Key")
    if not api_key.isascii() or any(ord(char) < 33 or ord(char) == 127 for char in api_key):
        raise ValueError("API Key 包含空白或无效字符，请检查复制内容")
    url, anthropic = _catalog_url(provider, base_url)
    headers = ({"x-api-key": api_key, "anthropic-version": "2023-06-01"}
               if anthropic else {"Authorization": f"Bearer {api_key}"})
    try:
        with httpx.Client(timeout=10, follow_redirects=False) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            payload: Any = response.json()
    except httpx.HTTPStatusError as error:
        # 不回传上游正文、URL 或异常文本，避免网关错误携带请求凭据。
        status = error.response.status_code
        reason = {
            401: "API Key 鉴权失败，请确认密钥属于当前端点",
            403: "当前密钥无权访问模型目录",
            404: "未找到模型目录，请检查 Base URL 是否为 API 根地址",
            405: "网关不支持 GET 模型目录接口，可手动填写模型标识",
            429: "请求过于频繁，请稍后重试",
        }.get(status, "模型网关返回异常状态，请检查网关服务")
        raise RuntimeError(f"获取模型列表失败（HTTP {status}）：{reason}") from None
    except httpx.TimeoutException:
        raise RuntimeError("获取模型列表超时，请检查网络或稍后重试") from None
    except httpx.RequestError:
        raise RuntimeError("无法连接模型网关，请检查 DNS、代理、TLS 证书或网络") from None
    except ValueError:
        raise RuntimeError("模型目录未返回有效 JSON，请检查 Base URL 是否为 API 根地址") from None
    entries = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        raise RuntimeError("模型服务返回的数据格式不受支持")
    model_ids = sorted({entry["id"] for entry in entries
                        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
                        and entry["id"].strip()})
    if not model_ids:
        raise RuntimeError("模型服务未返回可选择的模型")
    return model_ids
