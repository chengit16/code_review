"""集中读取运行配置，避免业务模块各自解释环境变量。"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


@dataclass(frozen=True)
class Settings:
    """保存进程级配置；项目密钥由数据库中的加密引用管理。"""

    data_dir: Path
    admin_token: str
    master_key: str
    gitlab_api_token: str
    ocr_command: str
    ocr_provider: str
    ocr_model: str
    ocr_api_key: str
    ocr_timeout_seconds: int
    public_url: str
    dev_mode: bool = False
    ocr_base_url: str = ""
    webhook_url: str = ""
    management_url: str = ""
    ocr_max_files: int = 0
    ocr_max_tokens_budget: int = 0
    ocr_concurrency: int = 4
    ocr_effort: str = "low"
    review_language: str = "zh-CN"

    @property
    def webhook_base_url(self) -> str:
        """旧调用方仍可用 public_url，新部署可独立指定回调入口。"""

        return self.webhook_url or self.public_url

    @property
    def management_base_url(self) -> str:
        """卡片详情使用管理入口；兼容直接构造 Settings 的旧调用方。"""

        return self.management_url or self.public_url


def validate_service_url(value: str, name: str, allow_insecure_http: bool = False) -> str:
    """进程级地址只接受无凭据、无查询参数的 HTTPS 或本机 HTTP 地址。"""

    parsed = urlparse(value)
    if (
        not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment
        or parsed.scheme not in {"http", "https"}
        or (
            parsed.scheme == "http"
            and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            and not allow_insecure_http
        )
    ):
        raise RuntimeError(f"{name} 必须是无凭据的 HTTPS 或本机 HTTP 地址")
    return value.rstrip("/")


def load_settings() -> Settings:
    """读取服务进程配置；开发模式只放宽管理台鉴权，不改变密钥边界。"""

    config_file = os.environ.get("OCR_APP_CONFIG_FILE")
    file_values: dict[str, str] = {}
    if config_file:
        path = Path(config_file)
        metadata = path.stat()
        # launchd plist 不存放密钥，配置文件须仅当前运行用户可读。
        if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) & 0o077:
            raise RuntimeError("配置文件必须由当前用户持有且权限不超过 0600")
        content = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(content, dict) or any(
            not isinstance(key, str) or not isinstance(value, str) for key, value in content.items()
        ):
            raise RuntimeError("配置文件必须是字符串键值对象")
        file_values = content

    def setting(name: str, default: str = "") -> str:
        """环境变量可临时覆盖私有配置文件中的同名设置。"""

        return os.environ.get(name, file_values.get(name, default))

    dev_mode_value = setting("OCR_APP_DEV_MODE", "0").strip().lower()
    if dev_mode_value not in {"0", "1", "false", "true", "no", "yes"}:
        raise RuntimeError("OCR_APP_DEV_MODE 必须是 0/1、true/false 或 yes/no")
    dev_mode = dev_mode_value in {"1", "true", "yes"}
    allow_insecure_http_value = setting("OCR_APP_ALLOW_INSECURE_HTTP", "0").strip().lower()
    if allow_insecure_http_value not in {"0", "1", "false", "true", "no", "yes"}:
        raise RuntimeError("OCR_APP_ALLOW_INSECURE_HTTP 必须是 0/1、true/false 或 yes/no")
    allow_insecure_http = allow_insecure_http_value in {"1", "true", "yes"}
    admin_token = setting("OCR_APP_ADMIN_TOKEN")
    master_key = setting("OCR_APP_MASTER_KEY")
    if not master_key:
        raise RuntimeError("OCR_APP_MASTER_KEY 必须配置")
    if not dev_mode and not admin_token:
        raise RuntimeError("非开发模式必须配置 OCR_APP_ADMIN_TOKEN")
    legacy_url = setting("OCR_APP_PUBLIC_URL", "http://127.0.0.1:8781")
    webhook_url = validate_service_url(
        setting("OCR_APP_WEBHOOK_URL", legacy_url),
        "OCR_APP_WEBHOOK_URL",
        allow_insecure_http,
    )
    management_url = validate_service_url(
        setting("OCR_APP_MANAGEMENT_URL", "http://127.0.0.1:8781"),
        "OCR_APP_MANAGEMENT_URL",
        allow_insecure_http,
    )
    review_language = setting("OCR_APP_REVIEW_LANGUAGE", "zh-CN").strip()
    if (
        not review_language
        or len(review_language) > 50
        or any(ord(character) < 32 for character in review_language)
    ):
        raise RuntimeError("OCR_APP_REVIEW_LANGUAGE 必须是有效的语言名称或区域代码")
    try:
        ocr_concurrency = int(setting("OCR_APP_OCR_CONCURRENCY", "4"))
    except ValueError as error:
        raise RuntimeError("OCR_APP_OCR_CONCURRENCY 必须是整数") from error
    if not 1 <= ocr_concurrency <= 32:
        raise RuntimeError("OCR_APP_OCR_CONCURRENCY 必须在 1 到 32 之间")
    ocr_effort = setting("OCR_APP_OCR_EFFORT", "low").strip().lower()
    if ocr_effort not in {"low", "medium", "high"}:
        raise RuntimeError("OCR_APP_OCR_EFFORT 必须是 low、medium 或 high")
    return Settings(
        data_dir=Path(setting("OCR_APP_DATA_DIR", ".local-data")).resolve(),
        admin_token=admin_token,
        master_key=master_key,
        gitlab_api_token="",
        ocr_command=setting("OCR_APP_OCR_COMMAND", "ocr"),
        # 模型和项目凭据仅由管理台保存；进程配置不再覆盖这些业务事实。
        ocr_provider="",
        ocr_model="",
        ocr_api_key="",
        ocr_timeout_seconds=int(setting("OCR_APP_OCR_TIMEOUT_SECONDS", "3600")),
        public_url=setting("OCR_APP_PUBLIC_URL", "http://127.0.0.1:8781").rstrip("/"),
        dev_mode=dev_mode,
        ocr_base_url="",
        webhook_url=webhook_url,
        management_url=management_url,
        ocr_concurrency=ocr_concurrency,
        ocr_effort=ocr_effort,
        review_language=review_language,
    )
