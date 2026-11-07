"""隔离验证预算前瞻、人工授权、历史证据及迁移；不调用 GitLab、模型或通知。"""

from __future__ import annotations

import json
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from ocr_manager import ocr, storage
from ocr_manager.config import Settings
from ocr_manager.newline_filter import VERIFIED_OCR_VERSION
from ocr_manager.recovery_budget import (
    OCR_1129_MINIMUM,
    BudgetAuthorization,
    authorize_budget,
    budget_gate,
)
from ocr_manager.recovery_budget_import import import_budget_evidence
from ocr_manager.review_failures import ReviewFailure
from ocr_manager.review_recovery_domain import RecoveryConflict
from ocr_manager.review_recovery_store import claim, eligibility, enqueue, finish
from ocr_manager.storage import Store
from schema_fixtures import remove_recovery_budget_schema
from test_auth import create_user, enable_users, login
from test_review_recovery import ADMIN, child_result, command, make_source


def blocked(raw: dict[str, Any]) -> dict[str, Any]:
    """合成与真实格式一致的 573+127524>1000 预算拒绝，不复用真实代码。"""

    child = child_result(raw)
    coverage = child["manifest"]["coverage"]
    coverage["failed"] = [item | {"classification": "budget"} for item in coverage["selected"]]
    coverage["completed"] = []
    child["manifest"]["terminal_state"] = "failed"
    child["summary"] = {"input_tokens": 420, "output_tokens": 153, "total_tokens": 573,
                        "budget_exceeded": True}
    child["warnings"] = [{"type": "token_budget_reached", "message":
        "stopped dispatch: used 573 tokens + group estimate 127524 = "
        "projected 128097 exceeds budget 1000"}]
    return child


def approval(**changes: Any) -> BudgetAuthorization:
    """必须显式给出版本、累计费用边界和原因；不产生评审命令。"""

    return BudgetAuthorization.model_validate({"expected_version": 0, "max_batches": 4,
        "max_total_tokens": 200000, "reason": "合成管理员批准", **changes})


def test_exact_gate_and_floor() -> None:
    """验证精确前瞻算式及上游常量，禁止误作实际账单。"""

    raw = blocked({"manifest": {"input": {}}})
    gate = budget_gate(raw)
    assert gate and gate.model_dump() == {"used_tokens": 573, "group_estimate_tokens": 127524,
                                         "projected_tokens": 128097, "budget_tokens": 1000}
    assert OCR_1129_MINIMUM == 2000 + 400 + 2000 * 7 + 700 * 7 == 21300
    assert "warnings" not in gate.model_dump()


@pytest.mark.parametrize("fault", ["arithmetic", "negative", "text", "boolean", "usage", "flag"])
def test_invalid_gate_not_inferred(fault: str) -> None:
    """异常格式、算术或用量矛盾不猜测预算缺口。"""

    raw = blocked({"manifest": {"input": {}}})
    if fault == "arithmetic":
        raw["warnings"][0]["message"] = raw["warnings"][0]["message"].replace("128097", "128098")
    elif fault == "negative":
        raw["warnings"][0]["message"] = raw["warnings"][0]["message"].replace("573", "-573")
    elif fault == "text":
        raw["warnings"][0]["message"] += " private-response"
    elif fault == "boolean":
        raw["summary"]["total_tokens"] = True
    elif fault == "usage":
        raw["summary"]["total_tokens"] = 572
    else:
        raw["summary"]["budget_exceeded"] = False
    assert budget_gate(raw) is None


def test_gate_prevents_repeat_and_authorization_does_not_enqueue(
    client: TestClient, settings: Settings,
) -> None:
    """验证失败诊断、零重复入队和人工授权后的显式补审。"""

    store, settings, raw = make_source(client, settings)
    enqueue(store, settings, 1, command())
    task = claim(store)
    assert task and finish(store, task, blocked(raw))
    state = eligibility(store, settings, 1)
    assert state.reason_code == "budget_insufficient"
    assert state.budget and state.budget.minimum_start_tokens == 128097
    history = client.get("/api/jobs/1/recoveries", headers=ADMIN).json()
    assert history[0]["error_code"] == "budget_unconfirmed"
    assert history[0]["budget_gate"]["group_estimate_tokens"] == 127524
    for tokens in (1000, 100000):
        with pytest.raises(RecoveryConflict):
            enqueue(store, settings, 1, command(token_budget=tokens))
    saved = client.put("/api/jobs/1/recovery-budget", headers=ADMIN, json=approval().model_dump())
    assert saved.status_code == 200
    assert claim(store) is None
    assert eligibility(store, settings, 1).eligible
    assert client.put("/api/jobs/1/recovery-budget", headers=ADMIN,
                      json=approval().model_dump()).status_code == 409
    with pytest.raises(RecoveryConflict, match="budget_insufficient"):
        enqueue(store, settings, 1, command(token_budget=128096))
    enqueue(store, settings, 1, command(token_budget=128097))
    with store.connection() as db:
        assert db.execute("SELECT count(*) FROM review_recoveries").fetchone()[0] == 2
        assert db.execute("SELECT actor FROM review_recovery_authorizations").fetchone()[0]


def test_optimistic_concurrent_authorization_and_committed_floor(
    client: TestClient, settings: Settings,
) -> None:
    """并发仅允许一个版本提交，历史批准不能被额度下调抹除。"""

    store, settings, _ = make_source(client, settings)
    payload = command()
    identity = enqueue(store, settings, 1, payload)

    def save(_: int) -> str:
        try:
            authorize_budget(store, 1, approval(), "synthetic-admin")
            return "saved"
        except RecoveryConflict as error:
            return str(error)

    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(save, range(4)))
    assert outcomes.count("saved") == 1
    assert outcomes.count("budget_authorization_changed") == 3
    with pytest.raises(RecoveryConflict, match="budget_below_committed"):
        authorize_budget(store, 1, approval(expected_version=1, max_total_tokens=999), "admin")
    authorize_budget(store, 1, approval(expected_version=1, max_batches=1,
                                      max_total_tokens=1000), "admin")
    assert enqueue(store, settings, 1, payload) == identity
    assert eligibility(store, settings, 1).budget.used_batches == 1  # type: ignore[union-attr]


def test_reader_cannot_authorize(client: TestClient, settings: Settings) -> None:
    """只读角色可查询但不能授予额度。"""

    store, _, _ = make_source(client, settings)
    create_user(client, "admin", "admin")
    create_user(client, "reader", "reader")
    enable_users(client)
    headers = {"Authorization": f"Bearer {login(client, 'reader')['token']}"}
    assert client.get("/api/jobs/1/recovery-eligibility", headers=headers).status_code == 200
    assert client.put("/api/jobs/1/recovery-budget", headers=headers,
                      json=approval().model_dump()).status_code == 403
    with store.connection() as db:
        assert db.execute("SELECT count(*) FROM review_recovery_authorizations").fetchone()[0] == 0


@pytest.mark.parametrize("fault", [None, "symlink", "usage", "sha", "budget"])
def test_historical_import_is_controlled_idempotent_and_preserves_rows(
    client: TestClient, settings: Settings, fault: str | None,
) -> None:
    """受控历史导入幂等追加，来源异常拒绝且旧行逐字段不变。"""

    store, settings, raw = make_source(client, settings)
    enqueue(store, settings, 1, command())
    task = claim(store)
    assert task
    result = blocked(raw)
    path = settings.data_dir / "runs/1/recoveries" / str(task["id"]) / "result.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(result))
    assert finish(store, task, result, str(path))
    # 模拟升级前只有安全投影，没有独立预算证据；历史状态不重新分类。
    with store.connection() as db:
        db.execute("DELETE FROM review_recovery_budget_evidence")
        old = json.loads(db.execute("SELECT result_json FROM review_recoveries").fetchone()[0])
        old.pop("budget_gate", None)
        db.execute("UPDATE review_recoveries SET result_json=?,error_code='child_not_usable'",
                   (json.dumps(old),))
        before = dict(db.execute("SELECT * FROM review_recoveries").fetchone())
    if fault == "symlink":
        alternate = path.with_suffix(".copy")
        path.rename(alternate)
        path.symlink_to(alternate)
    elif fault:
        if fault == "usage":
            result["summary"]["total_tokens"] = 574
        elif fault == "sha":
            result["manifest"]["input"]["resolved_head"] = "f" * 40
        else:
            result["warnings"][0]["message"] = result["warnings"][0]["message"].replace(
                "budget 1000", "budget 999")
        path.write_text(json.dumps(result))
    report = import_budget_evidence(settings.data_dir)
    assert report["eligible"] == (0 if fault else 1)
    assert report["inserted"] == 0
    report = import_budget_evidence(settings.data_dir, apply=True)
    assert report["inserted"] == (0 if fault else 1)
    again = import_budget_evidence(settings.data_dir, apply=True)
    assert again["unchanged"] == (0 if fault else 1)
    with store.connection() as db:
        assert dict(db.execute("SELECT * FROM review_recoveries").fetchone()) == before
        assert db.execute("SELECT count(*) FROM review_recovery_authorizations").fetchone()[0] == 0
    history = client.get("/api/jobs/1/recoveries", headers=ADMIN).json()
    assert bool(history[0]["budget_gate"]) == (fault is None)


def test_known_engine_floor_and_source_cap_not_overridden(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """首次补审也拦截明显过小预算；人工累计额度不能覆盖原始快照的单批上限。"""

    from ocr_manager import review_recovery_store

    store, settings, _ = make_source(client, settings)
    with store.connection() as db:
        snapshot = json.loads(db.execute("SELECT config_snapshot FROM review_jobs").fetchone()[0])
        snapshot["command"]["package_version"] = "1.12.9"
        snapshot["max_tokens_budget"] = 22000
        db.execute("UPDATE review_jobs SET config_snapshot=?", (json.dumps(snapshot),))
    monkeypatch.setattr(review_recovery_store, "current_hash", lambda *args: store.get_job(1)[
        "config_hash"])
    assert eligibility(store, settings, 1).budget.minimum_start_tokens == 21300
    with pytest.raises(RecoveryConflict, match="budget_insufficient"):
        enqueue(store, settings, 1, command())
    authorize_budget(store, 1, approval(), "synthetic-admin")
    with pytest.raises(RecoveryConflict, match="budget_exceeds_source"):
        enqueue(store, settings, 1, command(token_budget=23000))
    assert claim(store) is None


def test_different_source_cannot_inherit_old_gate_but_history_still_counts(
    client: TestClient, settings: Settings,
) -> None:
    """新来源不沿用旧门槛，但累计批准不能清零。"""

    store, settings, raw = make_source(client, settings)
    enqueue(store, settings, 1, command())
    task = claim(store)
    assert task and finish(store, task, blocked(raw))
    with store.connection() as db:
        source = json.loads(db.execute("SELECT result_json FROM review_jobs").fetchone()[0])
        source["comments"] = []
        db.execute("UPDATE review_jobs SET result_json=?", (json.dumps(source),))
    state = eligibility(store, settings, 1)
    assert state.budget and state.budget.minimum_start_tokens == 0
    assert state.budget.previous_gate is None
    assert state.budget.used_batches == 1 and state.budget.committed_tokens == 1000


def test_gate_from_different_approved_budget_not_persisted(
    client: TestClient, settings: Settings,
) -> None:
    """工件批准预算与数据库不一致时不记录精确数字。"""

    store, settings, raw = make_source(client, settings)
    enqueue(store, settings, 1, command(token_budget=2000))
    task = claim(store)
    assert task and finish(store, task, blocked(raw))
    history = client.get("/api/jobs/1/recoveries", headers=ADMIN).json()
    assert history[0]["budget_gate"] is None
    with store.connection() as db:
        assert db.execute("SELECT count(*) FROM review_recovery_budget_evidence").fetchone()[0] == 0


def test_import_does_not_create_missing_database(tmp_path: Path) -> None:
    """错误实例路径不能悄悄创建空业务库。"""

    with pytest.raises(FileNotFoundError):
        import_budget_evidence(tmp_path, apply=True)
    assert not (tmp_path / "app.db").exists()


def test_migration_rolls_back_without_grant(
    settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """迁移失败整体回滚，成功只建结构不自动授权。"""

    store = Store(settings.data_dir / "app.db")
    store.migrate()
    with store.connection() as db:
        remove_recovery_budget_schema(db)
        db.execute("PRAGMA user_version=47")
    migration = storage.RECOVERY_BUDGET_MIGRATION
    monkeypatch.setattr(storage, "RECOVERY_BUDGET_MIGRATION", migration + "INVALID SQL;")
    with pytest.raises(sqlite3.OperationalError):
        store.migrate()
    with store.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 47
        assert not db.execute("SELECT 1 FROM sqlite_master WHERE name="
                              "'review_recovery_authorizations'").fetchone()
    monkeypatch.setattr(storage, "RECOVERY_BUDGET_MIGRATION", migration)
    store.migrate()
    with store.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 48
        assert db.execute("SELECT count(*) FROM review_recovery_authorizations").fetchone()[0] == 0


def test_worker_low_budget_fails_before_paid_command(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """低预算在任何正式审核命令前失败，不调用付费模型。"""

    calls: list[list[str]] = []

    def execute(command: list[str], env: dict[str, str], cwd: Path,
                timeout: float) -> tuple[int, str]:
        calls.append(command)
        if "--version" in command:
            code, _, stderr = ocr._execute_ocr_command(
                [sys.executable, "-c", f"print({VERIFIED_OCR_VERSION!r})"], env, cwd, timeout)
            return code, stderr
        return 0, ""

    monkeypatch.setattr(ocr, "run_ocr_command", execute)
    # 版本由真实解析路径验证；所有 review 命令（包括预览）都不应到达。
    with pytest.raises(ReviewFailure) as error:
        ocr.run_review(replace(settings, ocr_max_tokens_budget=1000), tmp_path, tmp_path / "run",
                       "a" * 40, recovery_selection=({"x.py"}, {"x.py"}))
    assert error.value.category == "budget_insufficient"
    assert not any("review" in call for call in calls)
