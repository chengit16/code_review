"""验证回调与管理地址隔离，避免只开放回调的隧道被用于报告链接。"""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from ocr_manager.api import create_app
from ocr_manager.config import Settings, load_settings, validate_service_url


def test_independent_addresses(settings: Settings) -> None:
    """接口和项目回调使用部署入口，管理地址独立保留。"""

    config = replace(settings, webhook_url="https://hooks.example.test",
                     management_url="https://internal.example.test")
    with TestClient(create_app(config)) as client:
        assert client.get("/api/service-addresses").status_code == 401
        response = client.get("/api/service-addresses",
                              headers={"X-Admin-Token": settings.admin_token})
        assert response.json() == {
            "webhook_url": "https://hooks.example.test/api/webhooks/gitlab",
            "management_url": "https://internal.example.test",
        }
    assert config.management_base_url != config.webhook_base_url


def test_legacy_public_url_does_not_change_default_management_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """旧部署变量只兼容回调入口，不把本机管理地址跟随隧道暴露。"""

    monkeypatch.delenv("OCR_APP_CONFIG_FILE", raising=False)
    monkeypatch.setenv("OCR_APP_MASTER_KEY", "synthetic-master")
    monkeypatch.setenv("OCR_APP_DEV_MODE", "1")
    monkeypatch.setenv("OCR_APP_PUBLIC_URL", "https://hooks.example.test")
    monkeypatch.delenv("OCR_APP_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("OCR_APP_MANAGEMENT_URL", raising=False)
    config = load_settings()
    assert config.webhook_base_url == "https://hooks.example.test"
    assert config.management_base_url == "http://127.0.0.1:8781"


@pytest.mark.parametrize("value", ["https://user:secret@example.test", "javascript:alert(1)",
                                   "http://example.test", "https://example.test/?token=secret"])
def test_service_url_rejects_credentials_and_unsafe_protocols(value: str) -> None:
    """入口配置不得把凭据嵌入生成的链接。"""

    with pytest.raises(RuntimeError):
        validate_service_url(value, "OCR_APP_MANAGEMENT_URL")


def test_public_http_requires_explicit_deployment_override() -> None:
    """公网明文入口只在部署者显式确认风险后接受。"""

    value = "http://tunnel.example.test/"
    assert validate_service_url(value, "OCR_APP_WEBHOOK_URL", True) == (
        "http://tunnel.example.test"
    )


def test_review_speed_defaults_and_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """默认使用低 effort 和四路并发，非法覆盖值在启动时失败。"""

    monkeypatch.delenv("OCR_APP_CONFIG_FILE", raising=False)
    monkeypatch.setenv("OCR_APP_MASTER_KEY", "synthetic-master")
    monkeypatch.setenv("OCR_APP_DEV_MODE", "1")
    monkeypatch.delenv("OCR_APP_OCR_CONCURRENCY", raising=False)
    monkeypatch.delenv("OCR_APP_OCR_EFFORT", raising=False)
    config = load_settings()
    assert config.ocr_concurrency == 4
    assert config.ocr_effort == "low"

    monkeypatch.setenv("OCR_APP_OCR_CONCURRENCY", "0")
    with pytest.raises(RuntimeError, match="1 到 32"):
        load_settings()
    monkeypatch.setenv("OCR_APP_OCR_CONCURRENCY", "4")
    monkeypatch.setenv("OCR_APP_OCR_EFFORT", "maximum")
    with pytest.raises(RuntimeError, match="low、medium 或 high"):
        load_settings()
