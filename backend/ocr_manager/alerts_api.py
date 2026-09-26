"""告警配置与人工重试接口；外部投递由独立监控进程执行。"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ocr_manager.storage import Store


class AlertConfig(BaseModel):
    """默认关闭主动投递；启用时必须引用已保存的飞书通道。"""

    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    target_id: int | None = Field(None, gt=0)
    queue_minutes: int = Field(30, ge=1, le=1440)


def register_alerts(app: FastAPI, store: Store, admin: Any) -> None:
    """告警历史不包含群机器人地址，所有命令继承管理鉴权。"""

    @app.get("/api/alerts", dependencies=[admin])
    def alerts() -> dict[str, Any]:
        """返回配置、当前状态和最近投递。"""

        with store.connection() as db:
            return {"config": dict(db.execute("SELECT * FROM alert_config WHERE id=1").fetchone()),
                    "states": [dict(row) for row in db.execute("SELECT * FROM alert_states")],
                    "deliveries": [dict(row) for row in db.execute(
                        "SELECT * FROM alert_deliveries ORDER BY id DESC LIMIT 100")]}

    @app.put("/api/alerts/config", dependencies=[admin])
    def save(payload: AlertConfig) -> dict[str, str]:
        """通道更换后重新检测，旧投递继续保留其原目标。"""

        if payload.enabled and payload.target_id is None:
            raise HTTPException(422, "启用告警前请选择飞书通道")
        if payload.target_id and not store.get_notification_target(payload.target_id):
            raise HTTPException(409, "飞书通道不存在")
        with store.connection() as db:
            old = db.execute("SELECT * FROM alert_config WHERE id=1").fetchone()
            if old["target_id"] != payload.target_id or bool(old["enabled"]) != payload.enabled:
                # 保留轮次，避免更换通道后与历史唯一键冲突，重新触发当前异常。
                db.execute("UPDATE alert_states SET active=0")
            db.execute("UPDATE alert_config SET enabled=?,target_id=?,queue_minutes=? WHERE id=1",
                       (payload.enabled, payload.target_id, payload.queue_minutes))
        return {"status": "saved"}

    @app.post("/api/alerts/{delivery_id}/retry", dependencies=[admin])
    def retry(delivery_id: int) -> dict[str, str]:
        """人工重试只接受已失败消息；已删除的目标须先修复配置。"""

        with store.connection() as db:
            config = db.execute("SELECT * FROM alert_config WHERE id=1").fetchone()
            if not config["enabled"] or config["target_id"] is None:
                raise HTTPException(409, "请先启用可用的告警通道")
            changed = db.execute("""UPDATE alert_deliveries SET status='pending',attempts=0,
                                error=NULL,next_run_at=CURRENT_TIMESTAMP,target_id=?
                                WHERE id=? AND status='failed'""",
                                (config["target_id"], delivery_id)).rowcount
            if not changed:
                raise HTTPException(409, "消息当前无法重试")
        return {"status": "pending"}
