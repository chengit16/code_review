"""验证评审配置快照会随着 OCR 安装、规则与执行参数变化。"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from ocr_manager.config import Settings
from ocr_manager.storage import Store
from ocr_manager.worker import config_hash


def test_config_hash_changes_for_rule_and_ocr_upgrade(settings: Settings, tmp_path: Path) -> None:
    """同一提交重新评审时，规则或命令变化须创建新的任务快照。"""

    command = tmp_path / "ocr-test"
    command.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    command.chmod(0o755)
    config = replace(settings, ocr_command=str(command))
    store = Store(tmp_path / "app.db")
    store.migrate()
    original = config_hash(store, config, "first-rule")
    assert original != config_hash(store, config, "second-rule")
    assert original != config_hash(store, replace(config, ocr_timeout_seconds=60), "first-rule")
    assert original != config_hash(
        store, replace(config, review_language="en-US"), "first-rule"
    )
    assert original != config_hash(
        store, replace(config, ocr_concurrency=2), "first-rule"
    )
    assert original != config_hash(
        store, replace(config, ocr_effort="medium"), "first-rule"
    )
    command.write_text("#!/bin/sh\nexit 11\n", encoding="utf-8")
    assert original != config_hash(store, config, "first-rule")
