"""生成不含密钥的 macOS launchd 服务定义，交由部署用户审核后安装。"""

from __future__ import annotations

import argparse
import os
import plistlib
from pathlib import Path
from typing import Any


def generate_plists(
    project_dir: Path, config_file: Path, data_dir: Path, output_dir: Path,
    port: int = 8781, no_proxy: str = "", node_bin_dir: Path | None = None,
) -> tuple[Path, Path]:
    """分别生成 API 与单 Worker 清单，显式传递直连域名和 Node 路径。"""

    root = project_dir.resolve(strict=True)
    python = root / ".venv" / "bin" / "python"
    if not python.is_file():
        raise FileNotFoundError("项目虚拟环境 Python 不存在")
    if not 1 <= port <= 65535:
        raise ValueError("监听端口无效")
    if len(no_proxy) > 4096 or any(ord(character) < 32 for character in no_proxy):
        raise ValueError("NO_PROXY 设置无效")
    node_path = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
    if node_bin_dir is not None:
        node_dir = node_bin_dir.resolve(strict=True)
        node = node_dir / "node"
        if not node.is_file() or not os.access(node, os.X_OK):
            raise ValueError("Node 目录中没有可执行的 node")
        # launchd 不加载用户 shell 初始化文件，nvm 安装的 Node 必须显式加入 PATH。
        node_path = f"{node_dir}:{node_path}"
    config = config_file.resolve(strict=True)
    data = data_dir.resolve()
    logs = data / "logs"
    logs.mkdir(parents=True, exist_ok=True, mode=0o700)
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    common: dict[str, Any] = {
        "RunAtLoad": True,
        "KeepAlive": True,
        "WorkingDirectory": str(root),
        "EnvironmentVariables": {
            "OCR_APP_CONFIG_FILE": str(config),
            "OCR_NO_UPDATE": "1",
            "PATH": node_path,
        },
        "ProcessType": "Background",
    }
    if no_proxy:
        # launchd 不继承终端环境；内网 GitLab 若误经系统代理可能在 TLS 握手时断开。
        common["EnvironmentVariables"]["NO_PROXY"] = no_proxy
        common["EnvironmentVariables"]["no_proxy"] = no_proxy
    definitions = (
        (
            "api",
            [
                str(python),
                "-m",
                "uvicorn",
                "ocr_manager.asgi:app",
                "--app-dir",
                "backend",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
        ),
        ("worker", [str(python), "-m", "ocr_manager.worker"]),
    )
    paths: list[Path] = []
    for name, command in definitions:
        path = output_dir / f"ai.open-code-review.{name}.plist"
        payload = common | {
            "Label": f"ai.open-code-review.{name}",
            "ProgramArguments": command,
            "StandardOutPath": str(logs / f"{name}.stdout.log"),
            "StandardErrorPath": str(logs / f"{name}.stderr.log"),
        }
        with path.open("wb") as target:
            plistlib.dump(payload, target)
        os.chmod(path, 0o600)
        paths.append(path)
    return paths[0], paths[1]


def generate_backup_plist(
    project_dir: Path,
    data_dir: Path,
    backup_dir: Path,
    output_dir: Path,
    hour: int = 3,
    minute: int = 0,
    config_file: Path | None = None,
) -> Path:
    """生成每日数据库及私有配置备份清单，不把备份作业设为常驻服务。"""

    root = project_dir.resolve(strict=True)
    python = root / ".venv" / "bin" / "python"
    if not python.is_file():
        raise FileNotFoundError("项目虚拟环境 Python 不存在")
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("备份时间无效")
    data = data_dir.resolve()
    destination = backup_dir.resolve()
    if destination == data or data in destination.parents:
        raise ValueError("备份目录不能位于业务数据目录内")
    logs = data / "logs"
    logs.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = output_dir / "ai.open-code-review.backup.plist"
    command = [
        str(python), "-m", "ocr_manager.backup", "--data-dir", str(data),
    ]
    if config_file is not None:
        command.extend(["--config-file", str(config_file.resolve(strict=True))])
    command.extend(["--output-dir", str(destination)])
    payload: dict[str, Any] = {
        "Label": "ai.open-code-review.backup",
        "ProgramArguments": command,
        "WorkingDirectory": str(root),
        "RunAtLoad": True,
        "StartCalendarInterval": {"Hour": hour, "Minute": minute},
        "StandardOutPath": str(logs / "backup.stdout.log"),
        "StandardErrorPath": str(logs / "backup.stderr.log"),
    }
    with path.open("wb") as target:
        plistlib.dump(payload, target)
    os.chmod(path, 0o600)
    return path


def main() -> None:
    """只生成清单文件，系统服务安装与启用由部署者执行。"""

    parser = argparse.ArgumentParser(description="生成 Open Code Review 的 launchd 清单")
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument("--config-file", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8781)
    parser.add_argument("--no-proxy", default="")
    parser.add_argument("--node-bin-dir", type=Path)
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--backup-hour", type=int, default=3)
    parser.add_argument("--backup-minute", type=int, default=0)
    args = parser.parse_args()
    for path in generate_plists(
        args.project_dir, args.config_file, args.data_dir, args.output_dir,
        args.port, args.no_proxy, args.node_bin_dir,
    ):
        print(path)
    if args.backup_dir:
        print(
            generate_backup_plist(
                args.project_dir,
                args.data_dir,
                args.backup_dir,
                args.output_dir,
                args.backup_hour,
                args.backup_minute,
                args.config_file,
            )
        )


if __name__ == "__main__":
    main()
