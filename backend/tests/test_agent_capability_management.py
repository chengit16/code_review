"""贯通方案发布、固定提交取证、MCP 调用和双评审输出。"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from agent_comparison_fixture import seed_task
from fastapi.testclient import TestClient
from ocr_manager import agent_review_store as queue
from ocr_manager.agent_capability_checks import claim_check, execute_check
from ocr_manager.agent_mcp import _public_address
from ocr_manager.agent_review_worker import execute
from ocr_manager.api import create_app
from ocr_manager.config import Settings
from ocr_manager.secrets import SecretBox
from ocr_manager.storage import Store
from test_auth import ADMIN, create_user, enable_users, login

CAP = "/api/agent-capabilities"
PROJECT = "/api/repositories/1/agent-settings"
RUNS = "/api/jobs/1/agent-comparisons"


@pytest.fixture
def manager(settings: Settings) -> Iterator[tuple[TestClient, Store, int]]:
    """用真实 SQLite 和 Git，假模型仅替代服务响应。"""

    app = create_app(settings)
    store = Store(settings.data_dir / "app.db")
    seed_task(store, settings.data_dir)
    box = SecretBox(settings.master_key)
    baseline = store.add_model_profile(
        "项目模型", "openai", "baseline", "https://model.example.invalid/v1",
        box.encrypt("baseline-test"),
    )
    override = store.add_model_profile(
        "专用模型", "openai", "agent-only", "https://model.example.invalid/v1",
        box.encrypt("agent-test"),
    )
    with store.connection() as db:
        db.execute("INSERT INTO project_review_limits(repository_id,model_profile_id) VALUES(1,?)",
                   (baseline,))
    with TestClient(app, headers=ADMIN) as client:
        yield client, store, override


def _response(message: dict[str, Any]) -> httpx.Response:
    return httpx.Response(200, stream=httpx.ByteStream(json.dumps(message).encode()))


def _model_messages(request: httpx.Request, seen: list[dict[str, Any]]) -> httpx.Response:
    body = json.loads(request.content)
    page = json.loads(body["messages"][1]["content"])
    seen.append({"model": body["model"], **page})
    refs = page.get("review_context", {})
    skill = refs.get("skills", [])
    files = refs.get("related_files", [])
    doc = refs.get("reference_document")
    findings = []
    if skill or files or doc:
        line = next(line["head_line"] for line in page["lines"] if line["head_line"] is not None)
        findings.append({"title": "测试证据", "trigger": "读取差异", "impact": "测试",
                         "side": "head", "line": line, "capability_refs": [
                             item["ref"] for item in [*skill, *files, *([doc] if doc else [])]
                         ]})
    return _response({"model": body["model"], "choices": [{"finish_reason": "stop", "message": {
        "content": json.dumps({"findings": findings}),
    }}], "usage": {"prompt_tokens": 40, "completion_tokens": 10, "total_tokens": 50}})


def _enqueue(client: TestClient, key: str, previous: int | None = None, **options: Any) -> int:
    body = {"source_attempt": 1, "previous_id": previous, "request_key": key, **options}
    result = client.post(RUNS, json=body)
    assert result.status_code == 202, result.text
    assert client.post(RUNS, json=body).json() == result.json()
    return int(result.json()["id"])


def _run(store: Store, settings: Settings, ident: int) -> None:
    assert queue.claim(store) == {"id": ident, "repository_id": 1}
    execute(store, settings, ident)


def test_publish_preview_trial_and_frozen_model(
    manager: tuple[TestClient, Store, int], settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同任务各版本保留模型与方案；草稿、试跑及正式结果可区分。"""

    client, store, override = manager
    seen: list[dict[str, Any]] = []
    monkeypatch.setattr("ocr_manager.agent_review_worker.httpx.HTTPTransport",
                        lambda **_: httpx.MockTransport(lambda req: _model_messages(req, seen)))
    settings_body = {"version": 0, "enabled": True, "model_profile_id": override}
    assert client.put(PROJECT, json=settings_body).status_code == 200
    assert client.put(PROJECT, json=settings_body).status_code == 409
    assert store.get_model_profile(1)["model"] == "baseline"  # type: ignore[index]
    assert not seen and client.get(RUNS).json()["items"] == []

    skill = client.post(f"{CAP}/skills", json={
        "name": "订单评审", "pattern": "*.py", "body": "核对重复请求。",
    }).json()["id"]
    skipped = client.post(f"{CAP}/skills", json={
        "name": "前端评审", "pattern": "*.tsx", "body": "查看组件状态。",
    }).json()["id"]
    scheme = {"name": "补充评审", "skill_ids": [skill, skipped], "steps": ["read_file", "skills"],
              "files": [{"path": "orders.py", "pattern": "*.py"}]}
    assert client.post(f"{CAP}/schemes", json=scheme | {"steps": ["skills"]}).status_code == 422
    scheme_id = client.post(f"{CAP}/schemes", json=scheme | {"basis_id": 1}).json()["id"]
    assert client.get(CAP).json()["schemes"][0]["basis_id"] == 1
    assert client.put(PROJECT, json=settings_body | {
        "version": 1, "scheme_id": scheme_id,
    }).status_code == 409
    check_id = client.post(f"{CAP}/schemes/{scheme_id}/previews", json={"job_id": 1}).json()["id"]
    pending = claim_check(store)
    assert pending and pending["id"] == check_id
    execute_check(store, settings, pending)
    preview = client.get(f"{CAP}/checks/{check_id}").json()["result"]
    assert preview["rows"] == [{"path": "orders.py", "files": ["orders.py"], "mcp": None,
                                "skills": [f"订单评审 #{skill}"]}]
    assert not seen

    trial = _enqueue(client, "trial", trial_scheme_id=scheme_id)
    assert client.get(f"{RUNS}/{trial}").json()["trial"]
    assert client.post(RUNS, json={"source_attempt": 1, "previous_id": None,
                                  "request_key": "trial"}).status_code == 409
    assert client.put(PROJECT, json=settings_body | {
        "version": 1, "model_profile_id": None,
    }).status_code == 200
    _run(store, settings, trial)
    detail = client.get(f"{RUNS}/{trial}").json()
    assert detail["status"] == "complete"
    trials = client.get(f"{CAP}/schemes/{scheme_id}/trials").json()
    assert [(row["id"], row["status"]) for row in trials] == [(trial, "complete")]
    assert {item["model"] for item in seen} == {"agent-only"}
    assert detail["agent"]["capabilities"]["steps"] == ["read_file", "skills"]
    assert [item["status"] for item in detail["agent"]["capability_events"]] == [
        "complete", "matched", "skipped",
    ]
    events = detail["agent"]["capability_events"]
    assert events[0]["evidence"]["commit"] == detail["head_sha"]
    assert detail["agent"]["findings"][0]["capability_refs"] == [events[1]["id"], events[0]["id"]]
    assert detail["ocr"]["findings"][0]["path"] == "orders.py"

    assert client.put(f"{CAP}/schemes/{scheme_id}/publication", json={
        "enabled": True,
    }).status_code == 204
    assert client.put(PROJECT, json=settings_body | {
        "version": 2, "scheme_id": scheme_id, "model_profile_id": None,
    }).status_code == 200
    assert client.get(CAP).json()["project_bindings"] == {"1": scheme_id}
    old = _enqueue(client, "original", trial, config_mode="original")
    _run(store, settings, old)
    assert seen[-1]["model"] == "agent-only"
    new = _enqueue(client, "current", old, expected_scheme_id=scheme_id)
    _run(store, settings, new)
    assert seen[-1]["model"] == "baseline"
    assert not client.get(f"{RUNS}/{new}").json()["trial"]
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM notification_deliveries").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM gitlab_publications").fetchone()[0] == 0


def test_mcp_discovery_authorization_only_and_failure_policy(
    manager: tuple[TestClient, Store, int], settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """通过协议夹具核对发现、只读调用、撤权、超时与凭据脱敏。"""

    client, store, _ = manager
    real_client = httpx.Client
    calls: list[str] = []
    seen: list[dict[str, Any]] = []
    timeout = False
    tool = {"name": "search_docs", "inputSchema": {"type": "object", "required": ["query"],
            "properties": {"query": {"type": "string"}}}, "annotations": {"readOnlyHint": True}}

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer mcp-test-token"
        assert request.headers["host"] == "docs.example.invalid"
        assert request.url.host == "93.184.215.14"
        assert request.extensions["sni_hostname"] == "docs.example.invalid"
        if request.method == "DELETE":
            calls.append("close")
            return httpx.Response(204)
        body = json.loads(request.content)
        method = body["method"]
        calls.append(method)
        if method == "notifications/initialized":
            return httpx.Response(202)
        if method == "initialize":
            return httpx.Response(200, headers={"MCP-Session-Id": "fixture-session"},
                stream=httpx.ByteStream(json.dumps({"jsonrpc": "2.0", "id": body["id"], "result": {
                    "protocolVersion": "2025-06-18", "capabilities": {"tools": {}},
                }}).encode()))
        assert request.headers["mcp-session-id"] == "fixture-session"
        assert request.headers["mcp-protocol-version"] == "2025-06-18"
        if method == "tools/list":
            result = {"tools": [tool, tool | {"name": "write_docs", "annotations": {}}]}
        else:
            assert body["params"] == {"name": "search_docs", "arguments": {"query": "订单规范"}}
            if timeout:
                raise httpx.ReadTimeout("合成超时")
            result = {"content": [{"type": "text", "text": "订单写入需要去重。"}],
                      "structuredContent": {"document_id": "orders-policy", "version": "v2"}}
        return _response({"jsonrpc": "2.0", "id": body["id"], "result": result})

    monkeypatch.setattr("ocr_manager.agent_mcp._public_address", lambda _: "93.184.215.14")
    monkeypatch.setattr("ocr_manager.agent_capability_checks.httpx.Client",
                        lambda **kwargs: real_client(transport=kwargs.get(
                            "transport", httpx.MockTransport(respond)), trust_env=False))
    monkeypatch.setattr("ocr_manager.agent_review_worker.httpx.HTTPTransport",
                        lambda **_: httpx.MockTransport(lambda req: _model_messages(req, seen)))
    assert client.put(PROJECT, json={"version": 0, "enabled": True}).status_code == 200
    registration = {"name": "团队规范", "endpoint": "https://docs.example.invalid/mcp",
                    "token": "mcp-test-token"}
    assert client.post(f"{CAP}/services", json=registration | {
        "endpoint": "http://127.0.0.1/mcp",
    }).status_code == 409
    service = client.post(f"{CAP}/services", json=registration).json()["id"]
    check_id = client.post(f"{CAP}/services/{service}/checks").json()["id"]
    assert not calls
    pending = claim_check(store)
    assert pending and pending["id"] == check_id
    execute_check(store, settings, pending)
    assert list(client.get(f"{CAP}/checks/{check_id}").json()["result"]["tools"]) == ["search_docs"]
    assert "mcp-test-token" not in client.get(CAP).text
    assert client.put(f"{CAP}/services/{service}/grants", json={
        "repository_id": 1, "tool": "write_docs",
    }).status_code == 409
    lookup = {"service_id": service, "tool": "search_docs", "query": "订单规范", "pattern": "*.py"}
    scheme_id = client.post(f"{CAP}/schemes", json={
        "name": "规范", "steps": ["mcp"], "mcp": lookup,
    }).json()["id"]
    invalid = client.post(RUNS, json={"source_attempt": 1, "previous_id": None,
                                    "request_key": "unauthorized", "trial_scheme_id": scheme_id})
    assert invalid.status_code == 409 and "授权" in invalid.text
    assert client.put(f"{CAP}/services/{service}/grants", json={
        "repository_id": 1, "tool": "search_docs",
    }).status_code == 204
    success = _enqueue(client, "mcp", trial_scheme_id=scheme_id)
    _run(store, settings, success)
    detail = client.get(f"{RUNS}/{success}").json()
    assert detail["status"] == "complete"
    evidence = detail["agent"]["capability_events"][-1]["evidence"]
    assert evidence["document"] == "orders-policy" and evidence["version"] == "v2"
    assert calls.count("tools/call") == 1

    pending_id = _enqueue(client, "mcp-revoke", success, trial_scheme_id=scheme_id)
    assert client.delete(f"{CAP}/services/{service}/grants/1/search_docs").status_code == 204
    _run(store, settings, pending_id)
    revoked = client.get(f"{RUNS}/{pending_id}").json()
    assert revoked["status"] == "complete"
    assert revoked["agent"]["capability_events"][-1]["status"] == "failed"
    assert calls.count("tools/call") == 1

    assert client.put(f"{CAP}/services/{service}/grants", json={
        "repository_id": 1, "tool": "search_docs",
    }).status_code == 204
    stop = client.post(f"{CAP}/schemes", json={"name": "必须查询规范", "steps": ["mcp"],
                      "mcp": lookup | {"failure": "stop"}}).json()["id"]
    stop_id = _enqueue(client, "mcp-timeout", pending_id, trial_scheme_id=stop)
    timeout = True
    _run(store, settings, stop_id)
    detail = client.get(f"{RUNS}/{stop_id}").json()
    assert detail["agent"]["reason"] == "capability_unavailable"
    assert calls.count("tools/call") == 2


def test_capability_admin_and_public_address(
    manager: tuple[TestClient, Store, int], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """普通读者仍可看双评审，管理目录与私网目标受限。"""

    client, _, _ = manager
    create_user(client, "admin", "admin")
    create_user(client, "reader", "reader")
    enable_users(client)
    reader = {"Authorization": f"Bearer {login(client, 'reader')['token']}"}
    assert client.get(CAP, headers=reader).status_code == 403
    assert client.get(PROJECT, headers=reader).status_code == 403
    assert client.get(RUNS, headers=reader).status_code == 200
    monkeypatch.setattr("ocr_manager.agent_mcp.socket.getaddrinfo",
                        lambda *args, **kwargs: [(0, 0, 0, "", ("127.0.0.1", 443))])
    with pytest.raises(ValueError, match="公共 IPv4"):
        _public_address("docs.example.invalid")
