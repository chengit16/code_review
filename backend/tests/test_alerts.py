"""验证告警状态变化、独立重试和密钥边界；外部飞书使用替身。"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from ocr_manager.alerts import deliver_alert, reconcile_alerts
from ocr_manager.config import Settings
from ocr_manager.feishu import FeishuDeliveryError
from ocr_manager.secrets import SecretBox
from ocr_manager.storage import Store

ADMIN = {"X-Admin-Token": "test-admin-token"}


def test_alert_lifecycle_and_retry(client: TestClient, settings: Settings,
                                  monkeypatch: pytest.MonkeyPatch) -> None:
    """同一异常不重复建消息，恢复单独投递，失败不触发评审任务。"""

    store = Store(settings.data_dir / "app.db")
    target = store.add_notification_target("告警群", SecretBox(settings.master_key).encrypt(
        "https://open.feishu.cn/open-apis/bot/v2/hook/synthetic"), "")
    assert client.put("/api/alerts/config", json={"enabled": True},
                      headers=ADMIN).status_code == 422
    assert client.put("/api/alerts/config", json={"enabled": True, "target_id": target},
                      headers=ADMIN).status_code == 200
    for _ in range(3):
        reconcile_alerts(store, {"Worker 未运行": True})
    state = client.get("/api/alerts", headers=ADMIN).json()
    assert len(state["deliveries"]) == 1

    def fail(*_args: Any) -> None:
        raise FeishuDeliveryError("飞书网络连接失败", True)

    monkeypatch.setattr("ocr_manager.alerts.post_message", fail)
    assert deliver_alert(store, settings)
    assert client.get("/api/alerts", headers=ADMIN).json()["deliveries"][0]["status"] == "pending"
    with store.connection() as db:
        db.execute("UPDATE alert_deliveries SET next_run_at=CURRENT_TIMESTAMP")
    monkeypatch.setattr("ocr_manager.alerts.post_message", lambda *_args: None)
    assert deliver_alert(store, settings)
    reconcile_alerts(store, {"Worker 未运行": False})
    assert deliver_alert(store, settings)
    state = client.get("/api/alerts", headers=ADMIN).json()
    assert len(state["deliveries"]) == 2
    assert state["deliveries"][0]["recovered"] == 1
    assert store.list_jobs() == []
    assert "synthetic" not in str(state)
