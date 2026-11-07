"""只操作临时库与合成台账，保护自动归档证据、并发、来源防覆盖和失败回滚。"""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from ocr_manager import alerts, storage
from ocr_manager.config import Settings
from ocr_manager.improvement_archive_contracts import ArchiveChange
from ocr_manager.improvement_archives import change_archive
from ocr_manager.improvement_auto_archive import candidate_counts
from ocr_manager.improvement_contracts import ImprovementCreate, ImprovementUpdate
from ocr_manager.improvement_log_parser import entry_content, read_log
from ocr_manager.improvement_log_sync import sync_project_log
from ocr_manager.improvement_maintenance import (
    maintenance_status,
    monitor_maintenance,
    run_maintenance,
    set_maintenance_policy,
)
from ocr_manager.improvement_maintenance_contracts import MaintenancePolicy
from ocr_manager.improvement_theme_contracts import ImprovementThemeCreate
from ocr_manager.improvement_themes import create_theme, get_theme
from ocr_manager.improvements import create_improvement, get_improvement, improvement_history
from ocr_manager.storage import Store
from schema_fixtures import remove_improvement_maintenance_schema
from test_auth import create_user, enable_users, login

ADMIN = {"X-Admin-Token": "test-admin-token"}
CLOSED = {"status": "resolved", "solution": "合成解决方案", "verification_state": "passed",
          "validation_evidence": "合成验证通过", "deployment_state": "confirmed",
          "deployment_evidence": "合成环境已核对"}


def _store(settings: Settings) -> Store:
    result = Store(settings.data_dir / "app.db")
    result.migrate()
    return result


def _enable(store: Store) -> None:
    set_maintenance_policy(store, MaintenancePolicy(enabled=True, archive_after_days=30,
                                                   expected_version=1))


def _issue(store: Store, **overrides: object) -> int:
    values = {"client_key": uuid4(), "title": "合成归档对象", "description": "不含业务数据",
              **CLOSED, **overrides}
    return create_improvement(store, ImprovementCreate.model_validate(values), "测试用户").id


def _age(store: Store, days: int = 31) -> None:
    with store.connection() as db:
        for table in ["project_improvements", "improvement_themes"]:
            db.execute(f"UPDATE {table} SET updated_at=datetime('now',?)", (f"-{days} days",))


def _entry(source: str = "PI-20261106-001", solution: str = "当前处理", extra: str = "") -> str:
    return f"""### {source}｜合成事项

- 记录日期：2026-11-06
- 现象或目标：合成目标
- 处理与改进：{solution}
- 代码修改：已修改，但不隐含部署
- 本地验证：未运行
- 部署生效：尚未确认
{extra}
"""


def test_default_policy_preview_and_strict_admin_contract(client: TestClient) -> None:
    """新安装默认关闭，预览无写操作，权限和严格版本不能由前端代替。"""

    path = "/api/improvement-maintenance"
    assert client.get(path).status_code == 401
    before = client.get(path, headers=ADMIN).json()
    assert not before["enabled"] and not before["source_configured"]
    assert before["archive_after_days"] == 30 and before["last_checked_at"] is None
    assert client.get(path, headers=ADMIN).json() == before
    payload = {"enabled": True, "archive_after_days": 30, "expected_version": 1}
    for changes in [{"enabled": "true"}, {"archive_after_days": 0}, {"archive_after_days": 3651},
                    {"archive_after_days": True}, {"expected_version": True}, {"path": "/tmp"}]:
        assert client.put(path, headers=ADMIN, json={**payload, **changes}).status_code == 422
    saved = client.put(path, headers=ADMIN, json=payload)
    assert saved.status_code == 200 and saved.json()["version"] == 2
    assert saved.json()["last_checked_at"] is None
    assert client.put(path, headers=ADMIN, json=payload).status_code == 409
    audit = client.get("/api/audit-logs", headers=ADMIN).json()["items"]
    assert any(row["action"] == "PUT /api/improvement-maintenance" for row in audit)
    create_user(client, "admin", "admin")
    create_user(client, "reader", "reader")
    enable_users(client)
    headers = {"Authorization": f"Bearer {login(client, 'reader')['token']}"}
    assert client.get(path, headers=headers).status_code == 403
    assert client.put(path, headers=headers, json=payload).status_code == 403


@pytest.mark.parametrize("override", [
    {"status": "investigating"}, {"verification_state": "blocked", "status": "verifying"},
    {"verification_state": "not_run", "status": "verifying"},
    {"deployment_state": "not_deployed"}, {"deployment_state": "unknown"},
    {"next_steps": "待确认"},
])
def test_incomplete_evidence_never_auto_archives(
    settings: Settings, override: dict[str, str],
) -> None:
    """老旧但未闭环的对象不能因超过天数自动收起。"""

    store = _store(settings)
    _enable(store)
    identifier = _issue(store, **override)
    _age(store, 90)
    assert run_maintenance(store, settings).archived_records == 0
    assert get_improvement(store, identifier).archived_at is None


def test_exact_age_boundary_replay_and_restore_reset(settings: Settings) -> None:
    """30 天含边界，重复执行只生成一次归档历史；恢复会重新开始计时。"""

    store = _store(settings)
    identifier = _issue(store)
    now = datetime(2026, 11, 6, tzinfo=UTC)
    with store.connection() as db:
        db.execute("UPDATE project_improvements SET updated_at=?", ((now-timedelta(days=30,
            milliseconds=-1)).isoformat(),))
        assert candidate_counts(db, 30, now.isoformat()) == (0, 0)
        db.execute("UPDATE project_improvements SET updated_at=?",
                   ((now-timedelta(days=30)).isoformat(),))
        assert candidate_counts(db, 30, now.isoformat()) == (1, 0)
    _age(store)
    assert run_maintenance(store, settings).archived_records == 0
    _enable(store)
    assert run_maintenance(store, settings).archived_records == 1
    assert run_maintenance(store, settings).archived_records == 0
    history = improvement_history(store, identifier, 1, 25)
    assert history.total == 2 and history.items[0].action == "archive"
    assert history.items[0].snapshot.deployment_state == "confirmed"
    change_archive(store, "record", identifier, ArchiveChange(
        expected_version=2, archived=False, reason="合成恢复"), "测试用户")
    assert run_maintenance(store, settings).archived_records == 0
    assert get_improvement(store, identifier).version == 3


def test_theme_requires_all_phases_and_links_closed(settings: Settings) -> None:
    """主题阶段和关联问题分别校验，归档不更改关联或阶段验收状态。"""

    store = _store(settings)
    _enable(store)
    pending = _issue(store, deployment_state="unknown")
    closed = _issue(store)
    phase = {"title": "合成阶段", "goal": "保护部署边界", **CLOSED, "status": "completed"}
    eligible = create_theme(store, ImprovementThemeCreate.model_validate({
        "client_key": uuid4(), "title": "闭环主题", "objective": "目标", "status": "completed",
        "outcome": "已完成", "phases": [phase], "improvement_ids": [closed]}), "测试用户")
    for overrides in [{"improvement_ids": [pending]}, {"next_steps": "继续观察"},
                      {"phases": [{**phase, "deployment_state": "not_deployed"}]},
                      {"phases": [{**phase, "next_steps": "等待确认"}]}]:
        create_theme(store, ImprovementThemeCreate.model_validate({
            "client_key": uuid4(), "title": "不能归档", "objective": "目标", "status": "completed",
            "outcome": "阶段本地完成", "phases": [phase], **overrides}), "测试用户")
    _age(store)
    result = run_maintenance(store, settings)
    assert result.archived_records == result.archived_themes == 1
    current = get_theme(store, eligible.id)
    assert current.archived_at and current.improvement_ids == [closed]
    assert current.phases[0].deployment_state == "confirmed"


def test_concurrent_cycles_and_archive_rollback(settings: Settings) -> None:
    """多个维护调用也不能重复归档，任一历史失败整批回滚且成功时间不前进。"""

    store = _store(settings)
    _enable(store)
    first, second = _issue(store), _issue(store)
    _age(store)
    with store.connection() as db:
        db.execute(f"""CREATE TRIGGER reject_maintenance BEFORE INSERT
            ON project_improvement_revisions WHEN NEW.improvement_id={second}
            BEGIN SELECT RAISE(ABORT,'合成历史失败'); END""")
    assert run_maintenance(store, settings).archived_records == 0
    status = maintenance_status(store, settings)
    assert status.last_error_code == "archive_failed" and status.last_success_at is None
    assert get_improvement(store, first).version == 1
    with store.connection() as db:
        db.execute("DROP TRIGGER reject_maintenance")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: run_maintenance(store, settings), range(2)))
    assert sum(result.archived_records for result in results) == 2
    assert get_improvement(store, first).version == get_improvement(store, second).version == 2
    assert not maintenance_status(store, settings).last_error_code


def test_log_history_append_replay_unknown_states_and_extra_fields(settings: Settings) -> None:
    """模板不入库，追加保留原版证据，未知状态不凭措辞升级，额外字段也不丢失。"""

    store = _store(settings)
    path = settings.data_dir / "log.md"
    path.write_text("```markdown\n" + _entry("PI-20261106-999") + "```\n" + _entry(
        extra="- 最终复核补充：保留此事实"))
    assert sync_project_log(store, path).created == 1
    record = get_improvement(store, 1)
    assert record.deployment_state == "unknown" and record.verification_state == "not_run"
    assert "保留此事实" in record.analysis
    with path.open("a") as output:
        output.write(_entry(solution="后续处理", extra='- 同步状态：{"code_state":"modified"}'))
    assert sync_project_log(store, path).updated == 1
    assert sync_project_log(store, path).unchanged == 1
    history = improvement_history(store, 1, 1, 25)
    assert history.total == 2 and history.items[0].snapshot.solution == "后续处理"
    assert history.items[1].snapshot.solution == "当前处理"
    assert all("PI-20261106-001" in item.note for item in history.items)


@pytest.mark.parametrize("change", ["history", "delete", "manual", "archive"])
def test_source_changes_and_page_edits_are_conflicts(settings: Settings, change: str) -> None:
    """旧来源修改、缺失、页面人工修改或收纳均不得被同步静默覆盖。"""

    store = _store(settings)
    path = settings.data_dir / "log.md"
    text = _entry() + _entry("PI-20261106-002")
    path.write_text(text)
    sync_project_log(store, path)
    if change == "history":
        path.write_text(text.replace("当前处理", "改写历史", 1))
    elif change == "delete":
        path.write_text(_entry("PI-20261106-002"))
    else:
        if change == "manual":
            record = get_improvement(store, 1)
            payload = {name: getattr(record, name) for name in ImprovementCreate.model_fields
                       if name != "client_key"}
            from ocr_manager.improvements import update_improvement
            update_improvement(store, 1, ImprovementUpdate.model_validate({**payload,
                "title": "人工修改", "expected_version": 1,
                "progress_note": "保留人工事实"}), "用户")
        else:
            change_archive(store, "record", 1, ArchiveChange(expected_version=1, archived=True,
                reason="人工收纳"), "用户")
        path.write_text(text + _entry(solution="不能覆盖"))
    before = get_improvement(store, 1)
    assert sync_project_log(store, path).conflicts == ["PI-20261106-001"]
    assert get_improvement(store, 1) == before


@pytest.mark.parametrize("bad", [
    "", "### PI-20261106-001｜缺少字段\n", _entry(extra="- 代码修改：重复字段"),
    _entry(extra="- 同步状态：{错误}"), _entry(extra='- 同步状态：{"title":"不允许"}'),
    _entry(extra='- 同步状态：{"status":"resolved"}'), _entry() + "```\n未闭合",
])
def test_invalid_source_no_partial_import(settings: Settings, bad: str) -> None:
    """非法来源不能留下不完整摘要、历史或同步游标。"""

    store = _store(settings)
    path = settings.data_dir / "invalid.md"
    path.write_text(bad)
    try:
        result = sync_project_log(store, path)
        assert result.conflicts
    except ValueError:
        pass
    with store.connection() as db:
        for table in ["project_improvements", "project_improvement_revisions",
                      "improvement_log_imports"]:
            assert db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0


def test_source_failure_conflict_and_monitor_failure_isolation(
    settings: Settings, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """来源失败或冲突跳过归档；维护异常不能终止 monitor，日志不带路径或正文。"""

    store = _store(settings)
    _enable(store)
    _issue(store)
    _age(store)
    path = settings.data_dir / "private-source.md"
    configured = replace(settings, improvement_log_path=str(path))
    run_maintenance(store, configured)
    assert maintenance_status(store, settings).last_error_code == "source_unavailable"
    assert "private-source" not in caplog.text
    path.write_text(_entry())
    sync_project_log(store, path)
    path.write_text(_entry(solution="历史改写"))
    result = run_maintenance(store, configured)
    assert result.archived_records == 0 and result.sync.conflicts
    assert maintenance_status(store, settings).last_error_code == "source_conflict"
    import ocr_manager.improvement_maintenance as maintenance
    monkeypatch.setattr(maintenance, "run_maintenance", lambda *_: (_ for _ in ()).throw(
        RuntimeError("禁止输出此私有正文")))
    monitor_maintenance(store, settings)
    assert "maintenance_failed" in caplog.text and "禁止输出此私有正文" not in caplog.text
    assert alerts.monitor_maintenance is monitor_maintenance


def test_large_source_and_stable_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """大文件和读取期间变化均拒绝，不能导入半写入来源。"""

    path = tmp_path / "log.md"
    path.write_bytes(b"x" * (5 * 1024 * 1024 + 1))
    with pytest.raises(ValueError, match="大小上限"):
        read_log(path)
    path.write_text(_entry())
    original = Path.stat
    times = 0

    def changing(target: Path, **kwargs: object) -> object:
        nonlocal times
        times += 1
        if times == 2:
            with target.open("a") as output:
                output.write("\n追加")
        return original(target, **kwargs)

    monkeypatch.setattr(Path, "stat", changing)
    with pytest.raises(ValueError, match="正在写入"):
        read_log(path)


def test_sync_history_failure_rolls_back_source(settings: Settings) -> None:
    """同步游标、当前内容和历史同事务，失败重试不丢任何版本。"""

    store = _store(settings)
    path = settings.data_dir / "log.md"
    path.write_text(_entry() + _entry(solution="追加进展"))
    with store.connection() as db:
        db.execute("""CREATE TRIGGER fail_import BEFORE INSERT ON project_improvement_revisions
            WHEN NEW.version=2 BEGIN SELECT RAISE(ABORT,'合成失败'); END""")
    assert sync_project_log(store, path).conflicts
    with store.connection() as db:
        assert db.execute("SELECT count(*) FROM project_improvements").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM improvement_log_imports").fetchone()[0] == 0
        db.execute("DROP TRIGGER fail_import")
    assert sync_project_log(store, path).created == 1
    assert improvement_history(store, 1, 1, 25).total == 2


def test_migration_41_preserves_history_and_rollback(
    settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """旧库升级42保留原记录；注入迁移错误后仍完整停留41，不启用策略。"""

    store = _store(settings)
    identifier = _issue(store)
    with store.connection() as db:
        remove_improvement_maintenance_schema(db)
        db.execute("PRAGMA user_version=41")
    script = storage.IMPROVEMENT_MAINTENANCE_MIGRATION
    monkeypatch.setattr(storage, "IMPROVEMENT_MAINTENANCE_MIGRATION", script + "INVALID SQL;")
    with pytest.raises(sqlite3.OperationalError):
        store.migrate()
    with store.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 41
        assert db.execute("SELECT count(*) FROM sqlite_master WHERE name='improvement_maintenance'"
                          ).fetchone()[0] == 0
    monkeypatch.setattr(storage, "IMPROVEMENT_MAINTENANCE_MIGRATION", script)
    store.migrate()
    store.migrate()
    assert get_improvement(store, identifier).version == 1
    assert improvement_history(store, identifier, 1, 25).total == 1
    assert not maintenance_status(store, settings).enabled


def test_real_log_schema_can_be_projected_without_writes() -> None:
    """当前仓库台账可校验为完整快照，但测试绝不访问业务库或导入真实页面。"""

    path = Path(__file__).resolve().parents[2] / "docs/problem-improvement-log.md"
    for entries in read_log(path).values():
        previous = None
        for entry in entries:
            previous = entry_content(entry, previous)
        assert previous


def test_monitor_runs_maintenance_when_alerts_disabled(
    settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """飞书告警关闭也执行台账维护，不产生任何真实投递或外部调用。"""

    _store(settings)
    calls: list[str] = []
    monkeypatch.setattr(alerts, "load_settings", lambda: settings)
    monkeypatch.setattr(alerts, "monitor_maintenance", lambda *_: calls.append("maintenance"))
    monkeypatch.setattr(alerts, "prune_orphan_artifacts", lambda *_: None)
    monkeypatch.setattr(alerts, "deliver_alert", lambda *_: pytest.fail("不应投递告警"))

    class EndCycle(Exception):
        """仅在测试中结束无限监控循环。"""

    def end_cycle(_: int) -> None:
        raise EndCycle

    monkeypatch.setattr(alerts.time, "sleep", end_cycle)
    with pytest.raises(EndCycle):
        alerts.main()
    assert calls == ["maintenance"]


def test_no_applicable_and_clean_whitespace_are_eligible(settings: Settings) -> None:
    """有明确不适用证据的文档事项可以收纳，不能因非业务代码永远留在待办。"""

    store = _store(settings)
    _enable(store)
    identifier = _issue(store, code_state="not_applicable", verification_state="not_applicable",
                        deployment_state="not_applicable", next_steps=" \n\t")
    _age(store)
    assert run_maintenance(store, settings).archived_records == 1
    assert get_improvement(store, identifier).deployment_state == "not_applicable"
