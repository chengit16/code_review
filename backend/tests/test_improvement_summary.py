"""验证复盘的独立口径、时区、权限、去重和只读快照；仅使用合成临时 SQLite。"""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime
from typing import get_args
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from ocr_manager import improvement_summary
from ocr_manager.config import Settings
from ocr_manager.improvement_contracts import (
    ImprovementCategory,
    ImprovementRecord,
    ImprovementStatus,
)
from ocr_manager.improvement_summary import summarize_improvements
from ocr_manager.improvement_summary_contracts import ImprovementDistribution
from ocr_manager.improvement_theme_contracts import ImprovementThemeRecord
from ocr_manager.storage import Store
from test_auth import create_user, enable_users, login
from test_task_operations import populate

ADMIN = {"X-Admin-Token": "test-admin-token"}
ENDPOINT = "/api/improvement-summary"


def _record(client: TestClient, **changes: object) -> ImprovementRecord:
    response = client.post(
        "/api/improvements",
        headers=ADMIN,
        json={
            "client_key": str(uuid4()),
            "title": "合成复盘问题",
            "description": "不返回的合成正文",
            "category": "stability",
            **changes,
        },
    )
    assert response.status_code == 201, response.text
    return ImprovementRecord.model_validate(response.json())


def _theme(client: TestClient, **changes: object) -> ImprovementThemeRecord:
    response = client.post(
        "/api/improvement-themes",
        headers=ADMIN,
        json={
            "client_key": str(uuid4()),
            "title": "合成复盘主题",
            "objective": "不返回的主题目标",
            "category": "stability",
            **changes,
        },
    )
    assert response.status_code == 201, response.text
    return ImprovementThemeRecord.model_validate(response.json())


def test_summary_empty_defaults_ignore_review_jobs(client: TestClient, settings: Settings) -> None:
    """无台账时枚举与自然日补零，OCR 任务不混入平台复盘。"""

    populate(client, settings, 1)
    response = client.get(ENDPOINT, headers=ADMIN)
    assert response.status_code == 200, response.text
    summary = response.json()
    assert summary["timezone"] == "Asia/Shanghai"
    assert (
        summary["end_date"]
        == datetime.now(UTC).astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat()
    )
    assert len(summary["activity"]) == 30
    assert summary["records"]["total"] == summary["themes"]["total"] == 0
    assert summary["records"]["by_status"] == dict.fromkeys(get_args(ImprovementStatus), 0)
    assert all(day["records_created"] == day["record_updates"] == 0 for day in summary["activity"])
    assert summary["unresolved"] == {"total": 0, "items": []}


def test_summary_independent_states_and_distinct_links(client: TestClient) -> None:
    """解决、验证和部署各自计数；多主题关联不能放大台账或阶段分母。"""

    resolved = _record(
        client,
        status="resolved",
        solution="添加检查",
        code_state="modified",
        verification_state="passed",
        validation_evidence="本地合成通过",
    )
    blocked = _record(
        client,
        status="deferred",
        verification_state="blocked",
        validation_evidence="等待隔离环境",
        deployment_state="unknown",
    )
    _record(
        client,
        status="planned",
        code_state="modified",
        deployment_state="confirmed",
        deployment_evidence="仅合成部署证据，未做本地验证",
    )
    _record(
        client,
        code_state="modified",
        verification_state="failed",
        validation_evidence="合成失败",
        deployment_state="not_applicable",
        deployment_evidence="不涉及部署",
    )
    _record(
        client,
        kind="improvement",
        status="resolved",
        solution="补充说明",
        code_state="not_applicable",
        verification_state="not_applicable",
        validation_evidence="纯文档",
        deployment_state="not_applicable",
        deployment_evidence="文档",
    )
    _record(client, category="security", deployment_state="unknown")
    completed_phase = {
        "title": "实现",
        "goal": "补充验证",
        "status": "completed",
        "solution": "边界检查",
        "verification_state": "passed",
        "validation_evidence": "合成测试",
    }
    _theme(
        client,
        improvement_ids=[resolved.id, blocked.id],
        phases=[completed_phase, {"title": "观察", "goal": "核对后续效果", "status": "active"}],
    )
    _theme(
        client,
        improvement_ids=[resolved.id],
        status="completed",
        outcome="本地完成",
        phases=[completed_phase],
    )
    _theme(client, category="security")
    summary = client.get(ENDPOINT + "?category=stability", headers=ADMIN).json()
    records = summary["records"]
    assert records["total"] == 5 and records["linked_records"] == 2
    assert records["by_kind"] == {"problem": 4, "improvement": 1}
    assert records["by_status"]["resolved"] == 2
    assert records["by_verification_state"]["passed"] == 1
    assert records["by_deployment_state"]["confirmed"] == 1
    assert summary["unresolved"]["total"] == 3
    assert summary["verification_attention"]["total"] == 3
    assert summary["deployment_pending"]["total"] == 1
    assert summary["deployment_pending"]["items"][0]["id"] == resolved.id
    assert summary["themes"]["total"] == 2
    assert summary["themes"]["phases"]["total"] == 3
    assert summary["themes"]["phases"]["by_status"]["completed"] == 2
    assert summary["unfinished_themes"]["total"] == 1
    assert "不返回的合成正文" not in str(summary) and "不返回的主题目标" not in str(summary)
    all_records = client.get(ENDPOINT, headers=ADMIN).json()["records"]
    assert all_records["total"] == 6
    assert sum(all_records["by_status"].values()) == sum(all_records["by_category"].values()) == 6


def test_activity_timezone_boundaries_and_updates_not_resolutions(
    client: TestClient,
    settings: Settings,
) -> None:
    """活动使用北京时间半开 UTC 窗口，初始版本、冲突和重复创建不增加追加次数。"""

    record = _record(client)
    later = _record(client)
    theme = _theme(client)
    content = record.model_dump(exclude={"id", "version", "created_at", "updated_at",
                   "archived_at", "archived_by", "archive_reason"})
    update = {**content, "expected_version": 1, "progress_note": "尚未解决，追加排查"}
    path = f"/api/improvements/{record.id}"
    assert client.put(path, headers=ADMIN, json=update).status_code == 200
    assert client.put(path, headers=ADMIN, json=update).status_code == 409
    store = Store(settings.data_dir / "app.db")
    with store.connection() as db:
        db.execute(
            "UPDATE project_improvements SET created_at='2026-11-01T15:59:59.999Z' WHERE id=?",
            (record.id,),
        )
        db.execute(
            "UPDATE project_improvements SET created_at='2026-11-02T16:00:00.000Z' WHERE id=?",
            (later.id,),
        )
        db.execute("UPDATE project_improvement_revisions SET created_at='2026-11-01T16:00:00Z'")
        db.execute("UPDATE improvement_themes SET created_at='2026-11-02T15:59:59.999Z'")
        db.execute("UPDATE improvement_theme_revisions SET created_at='2026-11-02T15:59:59.999Z'")
    summary = client.get(
        ENDPOINT + "?start_date=2026-11-02&end_date=2026-11-02", headers=ADMIN
    ).json()
    assert summary["activity"] == [
        {
            "date": "2026-11-02",
            "records_created": 0,
            "record_updates": 1,
            "themes_created": 1,
            "theme_updates": 0,
        }
    ]
    assert summary["records"]["total"] == 2 and summary["unresolved"]["total"] == 2
    assert summary["themes"]["total"] == 1
    assert client.get(f"/api/improvement-themes/{theme.id}", headers=ADMIN).json()["version"] == 1


def test_activity_category_uses_current_ownership_and_preserves_zero_days(
    client: TestClient,
    settings: Settings,
) -> None:
    """旧记录本期更新不变为本期新增；历史分类不回放，零活动日仍连续。"""

    record = _record(client, category="security")
    content = record.model_dump(exclude={"id", "version", "created_at", "updated_at",
                   "archived_at", "archived_by", "archive_reason"})
    client.put(
        f"/api/improvements/{record.id}",
        headers=ADMIN,
        json={
            **content,
            "category": "stability",
            "expected_version": 1,
            "progress_note": "重新分类并排查",
        },
    )
    store = Store(settings.data_dir / "app.db")
    with store.connection() as db:
        db.execute("UPDATE project_improvements SET created_at='2026-10-01T00:00:00Z'")
        db.execute("UPDATE project_improvement_revisions SET created_at='2026-11-02T00:00:00Z'")
    query = "?start_date=2026-11-01&end_date=2026-11-03&category="
    stability = client.get(ENDPOINT + query + "stability", headers=ADMIN).json()
    assert [day["record_updates"] for day in stability["activity"]] == [0, 1, 0]
    assert all(day["records_created"] == 0 for day in stability["activity"])
    security = client.get(ENDPOINT + query + "security", headers=ADMIN).json()
    assert security["records"]["total"] == 0
    assert all(day["record_updates"] == 0 for day in security["activity"])


def test_theme_activity_idempotent_replay_and_replaced_phases(client: TestClient) -> None:
    """重复创建与冲突不重复计活动，阶段替换只计当前版本而历史活动保留。"""

    payload = {"client_key": str(uuid4()), "title": "主题活动验收", "objective": "当前阶段分母",
               "category": "performance", "phases": [{"title": "旧阶段", "goal": "初始"}]}
    first = client.post("/api/improvement-themes", headers=ADMIN, json=payload)
    assert first.status_code == 201
    created = first.json()
    assert client.post("/api/improvement-themes", headers=ADMIN, json=payload).status_code == 201
    update = {key: value for key, value in payload.items() if key != "client_key"}
    update.update({"expected_version": 1, "progress_note": "替换阶段", "phases": []})
    endpoint = f"/api/improvement-themes/{created['id']}"
    assert client.put(endpoint, headers=ADMIN, json=update).status_code == 200
    assert client.put(endpoint, headers=ADMIN, json=update).status_code == 409
    replay = client.post("/api/improvement-themes", headers=ADMIN, json=payload)
    assert replay.json()["version"] == 2
    summary = client.get(ENDPOINT + "?category=performance", headers=ADMIN).json()
    assert summary["themes"]["total"] == 1 and summary["themes"]["phases"]["total"] == 0
    assert sum(day["themes_created"] for day in summary["activity"]) == 1
    assert sum(day["theme_updates"] for day in summary["activity"]) == 1
    assert client.get(endpoint + "/history", headers=ADMIN).json()["total"] == 2


def test_attention_bounded_oldest_first_and_read_only(
    client: TestClient, settings: Settings
) -> None:
    """待办样本最多十条，完整数量不截断，重复读取不改变版本、历史或数据库结构。"""

    records = [_record(client, title=f"合成待办 {index}") for index in range(27)]
    store = Store(settings.data_dir / "app.db")
    with store.connection() as db:
        db.execute("UPDATE project_improvements SET updated_at='2026-10-01T00:00:00Z'")
        before = (
            db.execute("SELECT COUNT(*) FROM project_improvement_revisions").fetchone()[0],
            db.execute("SELECT SUM(version) FROM project_improvements").fetchone()[0],
            db.execute("PRAGMA user_version").fetchone()[0],
        )
    for _ in range(2):
        summary = client.get(ENDPOINT, headers=ADMIN).json()
        assert summary["unresolved"]["total"] == summary["records"]["total"] == 27
        assert [item["id"] for item in summary["unresolved"]["items"]] == [
            r.id for r in records[:10]
        ]
    with store.connection() as db:
        after = (
            db.execute("SELECT COUNT(*) FROM project_improvement_revisions").fetchone()[0],
            db.execute("SELECT SUM(version) FROM project_improvements").fetchone()[0],
            db.execute("PRAGMA user_version").fetchone()[0],
        )
    assert before == after


@pytest.mark.parametrize(
    "query",
    [
        "category=unknown",
        "start_date=invalid",
        "end_date=9999-12-31",
        "end_date=0001-01-01",
        "start_date=2026-11-03&end_date=2026-11-02",
        "start_date=1969-01-01",
        "start_date=2024-01-01&end_date=2025-01-01",
    ],
)
def test_summary_rejects_invalid_windows(client: TestClient, query: str) -> None:
    """错误日期、过大窗口和不可信枚举明确拒绝，不返回假零统计。"""

    assert client.get(f"{ENDPOINT}?{query}", headers=ADMIN).status_code == 422


def test_activity_historical_timezone_matches_window(
    client: TestClient, settings: Settings,
) -> None:
    """北京时间历史夏令时仍按同一时区分桶，不能把窗口内首小时丢到前一天。"""

    _record(client)
    store = Store(settings.data_dir / "app.db")
    with store.connection() as db:
        db.execute("UPDATE project_improvements SET created_at='1990-07-01T15:30:00Z'")
    response = client.get(ENDPOINT + "?start_date=1990-07-02&end_date=1990-07-02", headers=ADMIN)
    assert response.status_code == 200, response.text
    assert response.json()["activity"][0]["records_created"] == 1


def test_summary_accepts_366_days_and_admin_only(client: TestClient) -> None:
    """闰年窗口上限可用；管理员专用读接口不能被只读会话绕过。"""

    result = client.get(ENDPOINT + "?start_date=2024-01-01&end_date=2024-12-31", headers=ADMIN)
    assert result.status_code == 200 and len(result.json()["activity"]) == 366
    assert client.get(ENDPOINT).status_code == 401
    create_user(client, "admin", "admin")
    create_user(client, "reader", "reader")
    enable_users(client)
    session = login(client, "reader")
    assert (
        client.get(ENDPOINT, headers={"Authorization": f"Bearer {session['token']}"}).status_code
        == 403
    )


def test_summary_read_snapshot_survives_concurrent_write(
    client: TestClient,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """聚合期间另一连接保存成功，当前统计仍保持同一读取快照，下一次读取才可见。"""

    record = _record(client)
    original = improvement_summary._distribution
    updated = False

    def distribution(
        db: sqlite3.Connection,
        source: str,
        statuses: tuple[str, ...],
        category: ImprovementCategory | None,
    ) -> ImprovementDistribution:
        nonlocal updated
        # 替身只制造真实写入时序，不实现或复制统计查询。
        result = original(db, source, statuses, category)
        if not updated:
            updated = True
            content = record.model_dump(exclude={"id", "version", "created_at", "updated_at",
                   "archived_at", "archived_by", "archive_reason"})
            response = client.put(
                f"/api/improvements/{record.id}",
                headers=ADMIN,
                json={
                    **content,
                    "expected_version": 1,
                    "progress_note": "并发进展",
                    "status": "resolved",
                    "solution": "已修正",
                    "verification_state": "passed",
                    "validation_evidence": "合成",
                },
            )
            assert response.status_code == 200
        return result

    monkeypatch.setattr(improvement_summary, "_distribution", distribution)
    store = Store(settings.data_dir / "app.db")
    first = summarize_improvements(store, date(2026, 11, 1), date(2026, 11, 3), None)
    assert first.records.by_status["open"] == first.unresolved.total == 1
    second = summarize_improvements(store, date(2026, 11, 1), date(2026, 11, 3), None)
    assert second.records.by_status["resolved"] == 1 and second.unresolved.total == 0
