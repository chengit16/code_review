"""验证私有配置文件与 launchd 清单不会把密钥泄漏到服务定义。"""

from __future__ import annotations

import json
import os
import plistlib
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from ocr_manager.api import create_app
from ocr_manager.config import Settings, load_settings
from ocr_manager.launchd import generate_backup_plist, generate_plists
from ocr_manager.worker import worker_lock


def test_health_distinguishes_api_from_worker(client: TestClient, settings: Settings) -> None:
    """Worker 持锁处理长任务时显示运行中，退出后显示未运行。"""

    assert client.get("/api/health").json() == {
        "status": "ok",
        "auth_mode": "admin",
        "worker": "stopped",
    }
    with worker_lock(settings.data_dir):
        assert client.get("/api/health").json() == {
            "status": "ok",
            "auth_mode": "admin",
            "worker": "running",
        }
    assert client.get("/api/health").json() == {
        "status": "ok",
        "auth_mode": "admin",
        "worker": "stopped",
    }


def test_dev_mode_allows_management_without_admin_token(settings: Settings) -> None:
    """本地开发模式不要求管理口令，但仍保留主密钥用于加密业务凭据。"""

    dev_settings = replace(settings, admin_token="", dev_mode=True)
    with TestClient(create_app(dev_settings)) as client:
        assert client.get("/api/health").json() == {
            "status": "ok",
            "auth_mode": "dev",
            "worker": "stopped",
        }
        assert client.get("/api/repositories").status_code == 200


def test_admin_mode_rejects_management_without_token(client: TestClient) -> None:
    """默认管理模式继续拒绝缺少口令的管理请求。"""

    assert client.get("/api/repositories").status_code == 401


def test_private_config_file_loads_without_environment_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """守护进程只需配置文件路径，密钥保留在受限文件中。"""

    config = tmp_path / "private.json"
    config.write_text(
        json.dumps(
            {
                "OCR_APP_ADMIN_TOKEN": "admin-secret",
                "OCR_APP_MASTER_KEY": "master-secret",
                "OCR_APP_DATA_DIR": str(tmp_path / "data"),
            }
        ),
        encoding="utf-8",
    )
    os.chmod(config, 0o600)
    monkeypatch.setenv("OCR_APP_CONFIG_FILE", str(config))
    monkeypatch.delenv("OCR_APP_ADMIN_TOKEN", raising=False)
    monkeypatch.delenv("OCR_APP_MASTER_KEY", raising=False)
    monkeypatch.delenv("OCR_APP_PUBLIC_URL", raising=False)
    settings = load_settings()
    assert settings.admin_token == "admin-secret"
    assert settings.data_dir == tmp_path / "data"
    assert settings.public_url == "http://127.0.0.1:8781"
    assert settings.review_language == "zh-CN"
    os.chmod(config, 0o644)
    with pytest.raises(RuntimeError, match="0600"):
        load_settings()


def test_dev_mode_config_does_not_require_admin_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """开发配置可省略管理口令，但不能省略 Fernet 主密钥。"""

    config = tmp_path / "dev.json"
    config.write_text(
        json.dumps(
            {
                "OCR_APP_DEV_MODE": "1",
                "OCR_APP_MASTER_KEY": "master-secret",
                "OCR_APP_DATA_DIR": str(tmp_path / "data"),
            }
        ),
        encoding="utf-8",
    )
    os.chmod(config, 0o600)
    monkeypatch.setenv("OCR_APP_CONFIG_FILE", str(config))
    monkeypatch.delenv("OCR_APP_ADMIN_TOKEN", raising=False)
    monkeypatch.delenv("OCR_APP_MASTER_KEY", raising=False)
    settings = load_settings()
    assert settings.dev_mode is True
    assert settings.admin_token == ""


def test_launchd_plists_reference_config_without_embedding_secrets(tmp_path: Path) -> None:
    """API 与 Worker 清单只持有配置路径和固定运行命令。"""

    project = tmp_path / "project"
    python = project / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.touch()
    config = tmp_path / "private.json"
    config.write_text("private-secret-value", encoding="utf-8")
    node_dir = tmp_path / "node-bin"
    node_dir.mkdir()
    node = node_dir / "node"
    node.touch(mode=0o755)
    api, worker, monitor = generate_plists(
        project, config, tmp_path / "data", tmp_path / "launchd", 8777,
        "gitlab.example.test,127.0.0.1", node_dir,
    )
    api_bytes = api.read_bytes()
    worker_bytes = worker.read_bytes()
    assert b"private-secret-value" not in api_bytes + worker_bytes
    assert api.stat().st_mode & 0o777 == 0o600
    assert worker.stat().st_mode & 0o777 == 0o600
    api_payload = plistlib.loads(api_bytes)
    worker_payload = plistlib.loads(worker_bytes)
    assert api_payload["ProgramArguments"][-1] == "8777"
    assert worker_payload["ProgramArguments"][-1] == "ocr_manager.worker"
    assert api_payload["EnvironmentVariables"]["OCR_APP_CONFIG_FILE"] == str(config)
    assert api_payload["EnvironmentVariables"]["NO_PROXY"] == "gitlab.example.test,127.0.0.1"
    assert worker_payload["EnvironmentVariables"]["no_proxy"] == "gitlab.example.test,127.0.0.1"
    assert worker_payload["EnvironmentVariables"]["PATH"].startswith(f"{node_dir}:")
    with pytest.raises(ValueError, match="NO_PROXY"):
        generate_plists(project, config, tmp_path / "data", tmp_path / "launchd", 8781, "x\n")
    node.chmod(0o644)
    with pytest.raises(ValueError, match="Node"):
        generate_plists(
            project, config, tmp_path / "data", tmp_path / "launchd",
            node_bin_dir=node_dir,
        )


def test_launchd_defaults_to_local_fixed_port(tmp_path: Path) -> None:
    """未显式指定端口时，API 清单固定监听本机的 8781。"""

    project = tmp_path / "project"
    python = project / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.touch()
    config = tmp_path / "private.json"
    config.touch()
    api, _, _ = generate_plists(project, config, tmp_path / "data", tmp_path / "launchd")
    arguments = plistlib.loads(api.read_bytes())["ProgramArguments"]
    assert arguments[-4:] == ["--host", "127.0.0.1", "--port", "8781"]


def test_backup_plist_schedules_one_shot_outside_data_directory(tmp_path: Path) -> None:
    """备份任务每日启动一次且不常驻，副本位于业务数据目录之外。"""

    project = tmp_path / "project"
    python = project / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.touch()
    data = tmp_path / "data"
    backup = tmp_path / "backups"
    config = tmp_path / "private.json"
    config.touch()
    path = generate_backup_plist(
        project, data, backup, tmp_path / "launchd", 2, 30, config
    )
    payload = plistlib.loads(path.read_bytes())
    assert payload["StartCalendarInterval"] == {"Hour": 2, "Minute": 30}
    assert "KeepAlive" not in payload
    assert payload["ProgramArguments"][-1] == str(backup)
    arguments = payload["ProgramArguments"]
    assert arguments[arguments.index("--config-file") + 1] == str(config)
    assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(ValueError, match="业务数据目录"):
        generate_backup_plist(project, data, data / "backups", tmp_path / "launchd")
    with pytest.raises(ValueError, match="时间"):
        generate_backup_plist(project, data, backup, tmp_path / "launchd", 24, 0)
