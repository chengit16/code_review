"""在隔离 SQLite 验证交付核验拒绝漏记、缺进展、未同步及冲突；不读取真实聊天。"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from ocr_manager.improvement_log_check import check_log
from ocr_manager.improvement_log_sync import sync_project_log
from ocr_manager.storage import Store

SOURCE_ID = "PI-20261107-099"
NOW = datetime(2026, 11, 7, 3, tzinfo=UTC)


def _entry(title: str = "合成受理") -> str:
    states = {"kind": "problem", "category": "stability", "status": "investigating",
              "code_state": "unchanged", "verification_state": "not_run",
              "deployment_state": "not_deployed"}
    return (f"\n### {SOURCE_ID}｜{title}\n\n- 记录日期：2026-11-07\n"
            "- 现象或目标：合成故障\n- 处理与改进：仅排查\n- 代码修改：未修改\n"
            "- 本地验证：未运行\n- 部署生效：未部署\n"
            f"- 同步状态：{json.dumps(states, ensure_ascii=False)}\n")


@pytest.fixture
def scenario(tmp_path: Path) -> tuple[Store, Path, Path]:
    """创建仅供本模块使用的合成来源、数据库及近期 monitor 状态。"""

    database = tmp_path / "fixture.db"
    store = Store(database)
    store.migrate()
    source = tmp_path / "log.md"
    source.write_text(_entry(), encoding="utf-8")
    sync_project_log(store, source)
    with store.connection() as db:
        db.execute("UPDATE improvement_maintenance SET last_checked_at=?", (NOW.isoformat(),))
    return store, database, source


def test_synced_check_is_readonly(scenario: tuple[Store, Path, Path]) -> None:
    """来源和状态一致才通过；核验不追加进展、迁移或改变数据库内容。"""

    _, database, source = scenario
    with closing(sqlite3.connect(database)) as db:
        before = list(db.iterdump())
    result = check_log(database, source, [SOURCE_ID], now=NOW)
    assert result == [{"source_id": SOURCE_ID, "entries": 1, "page_id": 1,
                       "page_version": 1, "passed": True, "errors": []}]
    with closing(sqlite3.connect(database)) as db:
        assert list(db.iterdump()) == before


def test_missing_issue_and_missing_progress(scenario: tuple[Store, Path, Path]) -> None:
    """显式要求本次编号和条数，不能用其他已同步事项掩盖漏记。"""

    _, database, source = scenario
    missing = check_log(database, source, ["PI-20261107-098"], now=NOW)[0]
    assert missing["passed"] is False
    assert missing["errors"] == ["source_missing_or_progress_incomplete", "not_imported"]
    result = check_log(database, source, [SOURCE_ID], 2, now=NOW)[0]
    assert result["errors"] == ["source_missing_or_progress_incomplete"]


def test_append_waits_for_monitor(scenario: tuple[Store, Path, Path]) -> None:
    """已追加但未导入须报告等待；同步后才允许作为收尾核验通过。"""

    store, database, source = scenario
    source.write_text(source.read_text() + _entry("合成收尾"), encoding="utf-8")
    assert "sync_pending" in check_log(database, source, [SOURCE_ID], 2, now=NOW)[0]["errors"]
    sync_project_log(store, source)
    assert check_log(database, source, [SOURCE_ID], 2, now=NOW)[0]["passed"] is True


@pytest.mark.parametrize("action,error", [
    ("rewrite", "source_history_conflict"),
    ("version", "page_changed_or_archived"),
    ("archive", "page_changed_or_archived"),
    ("state", "state_mismatch"),
    ("page_missing", "page_missing"),
])
def test_conflicts_are_not_silently_repaired(
    scenario: tuple[Store, Path, Path], action: str, error: str,
) -> None:
    """历史改写和页面变化只报告，不更新游标或覆盖人工事实。"""

    store, database, source = scenario
    if action == "rewrite":
        source.write_text(_entry("改写历史"), encoding="utf-8")
    elif action == "page_missing":
        # 仅在隔离夹具构造外部破坏后的孤立游标；生产核验不会关闭外键或修复数据库。
        with closing(sqlite3.connect(database)) as db:
            db.execute("DELETE FROM project_improvements")
            db.commit()
    else:
        statements = {
            "version": "UPDATE project_improvements SET version=version+1",
            "archive": "UPDATE project_improvements SET archived_at='2026-11-07'",
            "state": "UPDATE project_improvements SET status='planned'",
        }
        with store.connection() as db:
            db.execute(statements[action])
    assert error in check_log(database, source, [SOURCE_ID], now=NOW)[0]["errors"]


@pytest.mark.parametrize("offset,error", [(121, ""), (0, "source_conflict"), (-30, "")])
def test_monitor_stale_error_or_future_is_not_healthy(
    scenario: tuple[Store, Path, Path], offset: int, error: str,
) -> None:
    """来源即使已同步，也不把过期、失败或未来时间的维护状态当作当前健康。"""

    store, database, source = scenario
    with store.connection() as db:
        db.execute("UPDATE improvement_maintenance SET last_checked_at=?,last_error_code=?",
                   ((NOW - timedelta(seconds=offset)).isoformat(), error))
    assert check_log(database, source, [SOURCE_ID], now=NOW)[0]["errors"] == [
        "monitor_not_recent_or_error"]


def test_missing_database_is_not_created(tmp_path: Path) -> None:
    """路径写错不能像普通 sqlite connect 那样静默创建空库。"""

    source = tmp_path / "log.md"
    source.write_text(_entry(), encoding="utf-8")
    missing = tmp_path / "missing.db"
    with pytest.raises(FileNotFoundError):
        check_log(missing, source, [SOURCE_ID], now=NOW)
    assert not missing.exists()
