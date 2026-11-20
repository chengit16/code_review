"""提供可操作的双评审浏览器样例，Worker 仅连接环回脚本模型。"""

from __future__ import annotations

import json
import os
from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
from threading import Event, Thread
from unittest.mock import patch

import httpx
import uvicorn
from agent_comparison_fixture import seed_comparison, seed_task
from ocr_manager.agent_review_config import AgentReviewConfig
from ocr_manager.api import FrontendFiles, create_app
from ocr_manager.config import Settings
from ocr_manager.secrets import SecretBox
from ocr_manager.storage import Store
from ocr_manager.worker import worker_lock
from ocr_manager.worker_scheduler import WorkerScheduler
from test_agent_review_worker import AgentEndpoint


def serve(settings: Settings) -> None:
    """启动隔离示例，服务退出时停止模型端点和 Worker，不访问真实仓库或网关。"""

    endpoint = AgentEndpoint()
    endpoint.start()
    try:
        managed = os.environ.get("OCR_BROWSER_AGENT_PILOT") == "1"
        config = AgentReviewConfig(endpoint.url, "synthetic-agent", frozenset({1}), "",
                                   page_lines=40)
        if not managed:
            settings = replace(settings, agent_review=config)
        app = create_app(settings)
        store = Store(settings.data_dir / "app.db")
        job = seed_task(store, settings.data_dir)
        capabilities = os.environ.get("OCR_BROWSER_AGENT_CAPABILITIES") == "1"
        if managed:
            profile = store.add_model_profile("合成项目模型", "openai", "synthetic-agent",
                "https://models.example.invalid/v1",
                SecretBox(settings.master_key).encrypt("synthetic-model-key"))
            assert store.activate_model_profile(profile)
        else:
            seed_comparison(store, settings.data_dir, config, job)
        if frontend := os.environ.get("OCR_BROWSER_FRONTEND_DIST"):
            app.router.routes[:] = [route for route in app.router.routes
                                    if getattr(route, "name", None) != "frontend"]
            app.mount("/", FrontendFiles(directory=Path(frontend), html=True), name="frontend")
        port = int(os.environ.get("OCR_BROWSER_AGENT_COMPARISON_PORT", "8791"))
        if managed and not capabilities:
            # 页面授权测试只观察入队前状态，不启动消费模型任务的进程。
            uvicorn.run(app, host="127.0.0.1", port=port)
            return
        def model_response(request: httpx.Request) -> httpx.Response:
            status, body = endpoint.reply(json.loads(request.content))
            return httpx.Response(status, stream=httpx.ByteStream(json.dumps(body).encode()))

        model_transport = (patch("ocr_manager.agent_review_worker.httpx.HTTPTransport",
                                 side_effect=lambda **_: httpx.MockTransport(model_response))
                           if capabilities else nullcontext())
        with (model_transport, worker_lock(settings.data_dir),
              WorkerScheduler(store, settings) as scheduler):
            stop = Event()

            def pump() -> None:
                while not stop.wait(0.1):
                    scheduler.tick()

            worker = Thread(target=pump, daemon=True)
            worker.start()
            try:
                uvicorn.run(app, host="127.0.0.1", port=port)
            finally:
                stop.set()
                worker.join()
    finally:
        endpoint.close()
