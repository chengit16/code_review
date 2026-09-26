"""为接口和队列测试提供隔离的 SQLite 与临时密钥。"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from ocr_manager.api import create_app
from ocr_manager.config import Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """生成不连接真实 GitLab、模型或飞书的测试配置。"""

    return Settings(
        data_dir=tmp_path,
        admin_token="test-admin-token",
        master_key=Fernet.generate_key().decode(),
        gitlab_api_token="test-gitlab-token",
        ocr_command="ocr",
        ocr_provider="dashscope",
        ocr_model="test-model",
        ocr_api_key="test-model-key",
        ocr_timeout_seconds=30,
        public_url="https://review.example.test",
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    """创建本地 ASGI 客户端，所有状态留在临时目录。"""

    with TestClient(create_app(settings)) as result:
        yield result
