"""供 Uvicorn 加载的生产 ASGI 入口。"""

from ocr_manager.api import create_app

app = create_app()
