"""项目级模型与执行限制；缺省继承当前全局配置。"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from ocr_manager.config import Settings

if TYPE_CHECKING:
    from ocr_manager.storage import Store

LIMITS_MIGRATION = """
CREATE TABLE project_review_limits (
 repository_id INTEGER PRIMARY KEY REFERENCES repositories(id) ON DELETE CASCADE,
 model_profile_id INTEGER REFERENCES model_profiles(id) ON DELETE SET NULL,
 timeout_seconds INTEGER CHECK(timeout_seconds BETWEEN 60 AND 14400),
 max_files INTEGER CHECK(max_files BETWEEN 1 AND 5000),
 max_tokens_budget INTEGER CHECK(max_tokens_budget BETWEEN 1000 AND 100000000)
);
ALTER TABLE review_jobs ADD COLUMN usage_json TEXT;
"""


def get_limits(store: Store, repository_id: int | None) -> dict[str, int | None]:
    """未指定项目时返回无限制配置，连接检查不会继承任意项目。"""

    keys = ("model_profile_id", "timeout_seconds", "max_files", "max_tokens_budget")
    if repository_id is None:
        return dict.fromkeys(keys)
    with store.connection() as db:
        row = db.execute("SELECT * FROM project_review_limits WHERE repository_id=?",
                         (repository_id,)).fetchone()
        return {key: row[key] if row else None for key in keys}


def apply_limits(settings: Settings, limits: dict[str, int | None]) -> Settings:
    """只改变本次 OCR 的运行参数，不改变全局进程配置。"""

    return replace(settings, ocr_timeout_seconds=limits["timeout_seconds"] or
                   settings.ocr_timeout_seconds,
                   ocr_max_files=limits["max_files"] or 0,
                   ocr_max_tokens_budget=limits["max_tokens_budget"] or 0)
