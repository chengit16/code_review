"""保护模型目录查询的鉴权、端点校验和敏感信息边界。"""

from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from ocr_manager import model_catalog

ADMIN = {"X-Admin-Token": "test-admin-token"}


class FakeResponse:
    """提供合成模型目录响应。"""

    def raise_for_status(self) -> None:
        """模拟成功的 HTTP 响应。"""

    def json(self) -> dict[str, Any]:
        """返回合成模型 ID。"""

        return {"data": [{"id": "model-a"}, {"id": "model-b"}, {"id": "model-a"}]}


class FakeClient:
    """记录模型目录请求但不访问网络。"""

    def __init__(self, **_kwargs: Any) -> None:
        self.headers: dict[str, str] = {}
        self.url = ""

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, *_args: Any) -> None:
        return None

    def get(self, url: str, headers: dict[str, str]) -> FakeResponse:
        self.url = url
        self.headers = headers
        return FakeResponse()


def test_model_catalog_is_authenticated_and_does_not_echo_credentials(
    client: TestClient, monkeypatch: Any,
) -> None:
    """仅管理员可查询模型目录，响应只包含去重后的模型标识。"""

    fake = FakeClient()
    monkeypatch.setattr(model_catalog.httpx, "Client", lambda **kwargs: fake)
    payload = {"provider": "dashscope", "base_url": "", "api_key": "synthetic-secret"}
    assert client.post("/api/model-catalog", json=payload).status_code == 401
    response = client.post("/api/model-catalog", headers=ADMIN, json=payload)
    assert response.status_code == 200
    assert response.json() == {"models": ["model-a", "model-b"]}
    assert fake.url == "https://dashscope.aliyuncs.com/compatible-mode/v1/models"
    assert fake.headers["Authorization"] == "Bearer synthetic-secret"
    assert "synthetic-secret" not in response.text


def test_model_catalog_rejects_unsafe_custom_endpoint(client: TestClient) -> None:
    """自定义目录地址必须是无凭据、无查询参数的 HTTPS API 根地址。"""

    response = client.post("/api/model-catalog", headers=ADMIN, json={
        "provider": "openai", "base_url": "http://127.0.0.1:8080/v1",
        "api_key": "synthetic-secret",
    })
    assert response.status_code == 422
    assert "HTTPS" in response.json()["detail"]


def test_catalog_reuses_saved_key_only_for_original_endpoint(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """留空密钥可读取保存凭据，但不能借此将凭据发送到新的服务。"""

    fake = FakeClient()
    monkeypatch.setattr(model_catalog.httpx, "Client", lambda **kwargs: fake)
    profile = client.post("/api/model-profiles", headers=ADMIN, json={
        "name": "合成公司模型", "provider": "openai", "base_url": "https://model.test/v1",
        "api_key": "saved-synthetic-key",
    }).json()
    payload = {"profile_id": profile["id"], "provider": "openai",
               "base_url": "https://model.test/v1", "api_key": ""}
    response = client.post("/api/model-catalog", headers=ADMIN, json=payload)
    assert response.status_code == 200
    assert fake.headers["Authorization"] == "Bearer saved-synthetic-key"
    assert "saved-synthetic-key" not in response.text
    fake.url = ""
    response = client.post("/api/model-catalog", headers=ADMIN,
                           json=payload | {"base_url": "https://other.test/v1"})
    assert response.status_code == 422
    assert fake.url == ""
    response = client.post("/api/model-catalog", headers=ADMIN,
                           json=payload | {"provider": "anthropic"})
    assert response.status_code == 422
    assert fake.url == ""
    assert client.post("/api/model-catalog", headers=ADMIN,
                       json=payload | {"profile_id": 99999}).status_code == 404


@pytest.mark.parametrize(("status", "detail"), [
    (401, "鉴权失败"), (403, "无权访问"), (404, "未找到"), (405, "不支持 GET"),
    (429, "过于频繁"), (503, "异常状态"), (302, "异常状态"),
])
def test_catalog_reports_safe_http_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, status: int, detail: str,
) -> None:
    """上游状态可诊断，但错误正文与密钥绝不能进入管理响应。"""

    original_client = httpx.Client

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer synthetic-key"
        return httpx.Response(status, text="private-upstream-content")

    monkeypatch.setattr(model_catalog.httpx, "Client", lambda **kwargs: original_client(
        **kwargs, transport=httpx.MockTransport(respond)))
    response = client.post("/api/model-catalog", headers=ADMIN, json={
        "provider": "openai", "api_key": "  synthetic-key\n",
    })
    assert response.status_code == 502
    assert f"HTTP {status}" in response.json()["detail"]
    assert detail in response.json()["detail"]
    assert "private-upstream-content" not in response.text
    assert "synthetic-key" not in response.text


@pytest.mark.parametrize("failure", ["timeout", "network", "invalid_json"])
def test_catalog_reports_network_and_format_failures(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, failure: str,
) -> None:
    """网络与格式错误独立提示，异常中的敏感内容不返回给页面。"""

    original_client = httpx.Client

    def respond(request: httpx.Request) -> httpx.Response:
        if failure == "timeout":
            raise httpx.ReadTimeout("private-token", request=request)
        if failure == "network":
            raise httpx.ConnectError("private-token", request=request)
        return httpx.Response(200, text="private-token")

    monkeypatch.setattr(model_catalog.httpx, "Client", lambda **kwargs: original_client(
        **kwargs, transport=httpx.MockTransport(respond)))
    response = client.post("/api/model-catalog", headers=ADMIN, json={
        "api_key": "synthetic-key",
    })
    assert response.status_code == 502
    expected = {"timeout": "超时", "network": "DNS", "invalid_json": "JSON"}[failure]
    assert expected in response.json()["detail"]
    assert "private-token" not in response.text
