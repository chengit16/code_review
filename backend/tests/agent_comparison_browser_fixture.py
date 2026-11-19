"""提供可操作的双评审浏览器样例，Worker 仅连接环回脚本模型。"""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
from threading import Event, Thread

import uvicorn
from agent_comparison_fixture import seed_comparison, seed_task
from ocr_manager.agent_review_config import AgentReviewConfig
from ocr_manager.api import FrontendFiles, create_app
from ocr_manager.config import Settings
from ocr_manager.storage import Store
from ocr_manager.worker import worker_lock
from ocr_manager.worker_scheduler import WorkerScheduler
from test_agent_review_worker import AgentEndpoint


def serve(settings: Settings) -> None:
    """启动隔离示例，服务退出时停止模型端点和 Worker，不访问真实仓库或网关。"""

    endpoint = AgentEndpoint()
    endpoint.start()
    try:
        config = AgentReviewConfig(endpoint.url, "synthetic-agent", frozenset({1}), "",
                                   page_lines=40)
        settings = replace(settings, agent_review=config)
        app = create_app(settings)
        store = Store(settings.data_dir / "app.db")
        job = seed_task(store, settings.data_dir)
        seed_comparison(store, settings.data_dir, config, job)
        if frontend := os.environ.get("OCR_BROWSER_FRONTEND_DIST"):
            app.router.routes[:] = [route for route in app.router.routes
                                    if getattr(route, "name", None) != "frontend"]
            app.mount("/", FrontendFiles(directory=Path(frontend), html=True), name="frontend")
        with worker_lock(settings.data_dir), WorkerScheduler(store, settings) as scheduler:
            stop = Event()

            def pump() -> None:
                while not stop.wait(0.1):
                    scheduler.tick()

            worker = Thread(target=pump, daemon=True)
            worker.start()
            try:
                port = int(os.environ.get("OCR_BROWSER_AGENT_COMPARISON_PORT", "8791"))
                uvicorn.run(app, host="127.0.0.1", port=port)
            finally:
                stop.set()
                worker.join()
    finally:
        endpoint.close()
