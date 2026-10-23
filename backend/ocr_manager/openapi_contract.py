"""生成并校验 OpenAPI 契约快照及前端直接引用的 API 路径。"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet

from ocr_manager.api import create_app
from ocr_manager.config import Settings

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs" / "openapi.json"
FRONTEND = ROOT / "frontend" / "src"
PATH_PATTERN = re.compile(
    r"[`\"'](/api/(?:[A-Za-z0-9._~-]+|\$\{[A-Za-z_$][\w$]*\})"
    r"(?:/(?:[A-Za-z0-9._~-]+|\$\{[A-Za-z_$][\w$]*\}))*)"
)


def generated_schema() -> dict[str, Any]:
    """用临时 SQLite 和随机密钥生成 schema，不读取开发者本机配置。"""

    with tempfile.TemporaryDirectory(prefix="ocr-openapi-") as temporary:
        app = create_app(Settings(
            data_dir=Path(temporary), admin_token="", master_key=Fernet.generate_key().decode(),
            gitlab_api_token="", ocr_command="ocr", ocr_provider="", ocr_model="",
            ocr_api_key="", ocr_timeout_seconds=30, public_url="https://example.invalid",
            dev_mode=True,
        ))
        return app.openapi()


def frontend_paths() -> set[str]:
    """读取页面中直接写出的 API 路径，并将插值段映射为 OpenAPI 参数。"""

    paths: set[str] = set()
    for source in FRONTEND.rglob("*.ts*"):
        if "/test/" in source.as_posix():
            continue
        for match in PATH_PATTERN.finditer(source.read_text(encoding="utf-8")):
            path = match.group(1).split("?", 1)[0]
            path = re.sub(r"\$\{[^}]+\}", "{_}", path)
            paths.add(path)
    return paths


def matches_route(frontend_path: str, api_path: str) -> bool:
    """按 URL 段匹配路径变量，避免参数名称差异造成误报。"""

    expression = re.sub(r"\{[^/{}]+\}", r"[^/]+", api_path)
    return re.fullmatch(expression, frontend_path) is not None


def check_contract(schema: dict[str, Any]) -> list[str]:
    """检查契约快照未漂移且前端引用均有后端路由。"""

    content = json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    errors: list[str] = []
    if not CONTRACT.is_file() or CONTRACT.read_text(encoding="utf-8") != content:
        errors.append("docs/openapi.json 与当前 FastAPI 契约不一致；运行更新命令重新生成。")
    api_paths = set(schema.get("paths", {}))
    for path in sorted(frontend_paths()):
        if not any(matches_route(path, route) for route in api_paths):
            errors.append(f"前端引用的 API 路径不存在于 OpenAPI 契约：{path}")
    return errors


def main() -> int:
    """提供本地生成与 CI 只读校验入口。"""

    parser = argparse.ArgumentParser(description="校验前后端 OpenAPI 契约一致性")
    parser.add_argument("--update", action="store_true", help="更新提交的 OpenAPI schema")
    args = parser.parse_args()
    schema = generated_schema()
    content = json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.update:
        CONTRACT.write_text(content, encoding="utf-8")
        print(f"已更新 {CONTRACT.relative_to(ROOT)}")
        return 0
    errors = check_contract(schema)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("OpenAPI 快照和前端 API 路径校验通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
