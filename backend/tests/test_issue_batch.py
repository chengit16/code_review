"""验证批量问题处理的原子性、乐观并发、权限与幂等；不调用外部系统。"""

from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient
from ocr_manager.config import Settings
from ocr_manager.storage import Store
from test_auth import create_user, enable_users, login
from test_review_issues import ADMIN, create_repository, finish_with_finding

URL = "/api/review-issues/batch-update"


@pytest.fixture
def issue_ids(client: TestClient, settings: Settings) -> list[int]:
    """建立三条互不关联的合成问题，未勾选项用于保护批量操作范围。"""

    repository_id = create_repository(client)
    store = Store(settings.data_dir / "app.db")
    for index in range(3):
        finish_with_finding(store, repository_id, 7 + index, f"{index + 1:040x}",
                            content=f"合成问题 {index}")
    return [item["id"] for item in client.get("/api/review-issues", headers=ADMIN).json()["items"]]


@pytest.mark.parametrize("status", ["fixed", "ignored", "open"])
def test_batch_changes_only_selected_and_records_actor(
    client: TestClient, issue_ids: list[int], status: str,
) -> None:
    """批量关闭及恢复逐条记录真实操作者，未选中项和反馈统计保持不变。"""

    for issue_id in issue_ids[:2]:
        assert client.patch(f"/api/review-issues/{issue_id}", headers=ADMIN,
                            json={"status": "ignored"}).status_code == 200
    payload = {"targets": [{"id": i, "expected_status": "ignored"} for i in issue_ids[:2]],
               "status": status, "note": "批量核查完成"}
    response = client.post(URL, headers=ADMIN, json=payload)
    assert response.status_code == 200
    updated = 0 if status == "ignored" else 2
    assert response.json() == {"status": status, "updated": updated, "unchanged": 2 - updated}
    for issue_id in issue_ids[:2]:
        detail = client.get(f"/api/review-issues/{issue_id}", headers=ADMIN).json()
        assert detail["status"] == status
        assert (detail["closed_at"] is None) == (status == "open")
        assert detail["events"][0]["actor"] == "共享管理员"
        if updated:
            assert detail["events"][0]["note"] == "批量核查完成"
    untouched = client.get(f"/api/review-issues/{issue_ids[2]}", headers=ADMIN).json()
    assert untouched["status"] == "open" and len(untouched["events"]) == 1
    assert client.get("/api/review-feedback/summary", headers=ADMIN).json()[0]["total"] == 0
    repeated = client.post(URL, headers=ADMIN, json=payload)
    assert repeated.json() == {"status": status, "updated": 0, "unchanged": 2}
    assert len(client.get(f"/api/review-issues/{issue_ids[0]}", headers=ADMIN).json()[
        "events"]) == (2 if status == "ignored" else 3)


def test_batch_conflict_or_missing_target_never_partially_updates(
    client: TestClient, issue_ids: list[int],
) -> None:
    """发现他人修改、目标缺失或已合并项时整批拒绝，不能先成功一部分。"""

    targets = [{"id": i, "expected_status": "open"} for i in issue_ids[:2]]
    assert client.patch(f"/api/review-issues/{issue_ids[1]}", headers=ADMIN,
                        json={"status": "fixed"}).status_code == 200
    response = client.post(URL, headers=ADMIN, json={"targets": targets, "status": "ignored"})
    assert response.status_code == 409 and "状态已变化" in response.json()["detail"]
    detail = client.get(f"/api/review-issues/{issue_ids[0]}", headers=ADMIN).json()
    assert detail["status"] == "open"
    missing = client.post(URL, headers=ADMIN, json={
        "targets": [targets[0], {"id": 999999, "expected_status": "open"}], "status": "ignored"})
    assert missing.status_code == 404
    assert client.post(f"/api/review-issues/{issue_ids[2]}/merge", headers=ADMIN,
                       json={"target_id": issue_ids[0]}).status_code == 200
    merged = client.post(URL, headers=ADMIN, json={
        "targets": [targets[0], {"id": issue_ids[2], "expected_status": "open"}],
        "status": "ignored"})
    assert merged.status_code == 409
    detail = client.get(f"/api/review-issues/{issue_ids[0]}", headers=ADMIN).json()
    assert detail["status"] == "open"


@pytest.mark.parametrize("targets", [[], [{"id": 1, "expected_status": "open"}] * 2,
    [{"id": i + 1, "expected_status": "open"} for i in range(101)],
    [{"id": True, "expected_status": "open"}], [{"id": -1, "expected_status": "open"}],
    [{"id": 1, "expected_status": "merged"}], [{"id": 1}]])
def test_batch_validates_explicit_bounded_unique_targets(
    client: TestClient, targets: list[dict[str, object]],
) -> None:
    """拒绝空集、重复、超量、隐式类型转换和缺少并发快照的请求。"""

    assert client.post(URL, headers=ADMIN,
                       json={"targets": targets, "status": "ignored"}).status_code == 422


def test_batch_requires_admin_and_uses_session_actor(
    client: TestClient, issue_ids: list[int],
) -> None:
    """只读账号不可通过批量接口修改，操作者不能从请求体伪造。"""

    payload = {"targets": [{"id": issue_ids[0], "expected_status": "open"}], "status": "ignored"}
    assert client.post(URL, json=payload).status_code == 401
    create_user(client, "alice", "admin")
    create_user(client, "bob", "reader")
    enable_users(client)
    reader = {"Authorization": f"Bearer {login(client, 'bob')['token']}"}
    admin = {"Authorization": f"Bearer {login(client, 'alice')['token']}"}
    assert client.post(URL, headers=reader, json=payload).status_code == 403
    assert client.post(URL, headers=admin, json={**payload, "actor": "别人"}).status_code == 422
    assert client.post(URL, headers=admin, json=payload).status_code == 200
    detail = client.get(f"/api/review-issues/{issue_ids[0]}", headers=reader).json()
    assert detail["events"][0]["actor"] == "alice"


def test_batch_audit_failure_rolls_back_every_issue(
    client: TestClient, settings: Settings, issue_ids: list[int],
) -> None:
    """第二条审计失败时第一条变更也必须回滚，不留下半批处理结果。"""

    store = Store(settings.data_dir / "app.db")
    with store.connection() as db:
        db.execute(f"""CREATE TRIGGER reject_batch_event BEFORE INSERT ON review_issue_events
            WHEN NEW.issue_id={issue_ids[1]} BEGIN SELECT RAISE(ABORT,'合成审计故障'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="合成审计故障"):
        client.post(URL, headers=ADMIN, json={
            "targets": [{"id": i, "expected_status": "open"} for i in issue_ids[:2]],
            "status": "ignored"})
    for issue_id in issue_ids:
        detail = client.get(f"/api/review-issues/{issue_id}", headers=ADMIN).json()
        assert detail["status"] == "open" and len(detail["events"]) == 1
