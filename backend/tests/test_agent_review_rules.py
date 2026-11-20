"""验证初审规则从冻结版本进入模型请求、按文件留痕及不安全引用的终止。"""

from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from ocr_manager import agent_review_rules as rules
from ocr_manager import agent_review_store as queue
from ocr_manager.agent_review_worker import execute
from ocr_manager.api import create_app
from ocr_manager.config import Settings
from ocr_manager.ocr import command_fingerprint
from ocr_manager.review_prototype.input import git
from ocr_manager.storage import Store
from test_agent_review_worker import agent_state, config_for
from test_agent_review_worker import endpoint as endpoint
from test_agent_review_worker import pilot as pilot
from test_auth import ADMIN

STYLE = "仅允许动态内联样式。"
GLOBAL = STYLE + "检查动态高度是否正确传入。"


def test_agent_runs_with_frozen_file_rules(
    pilot: tuple[Store, Settings], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """固定值违规，动态值按全局回退规则通过，HTTP 只返回规则摘要。"""

    store, settings = pilot
    command = os.environ.get("OCR_TEST_RULES_COMMAND")
    settings = replace(settings, ocr_command=command or "/usr/bin/true")
    config = config_for(settings)
    root = settings.data_dir / "repositories" / "1"
    base = git(root, "rev-parse", "HEAD").strip()
    (root / "Static.tsx").write_text('<div style={{ height: 400 }} />\n')
    (root / "Dynamic.tsx").write_text('<div style={{ height: size }} />\n')
    git(root, "add", "--", "Static.tsx", "Dynamic.tsx")
    git(root, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
        "commit", "-qm", "synthetic styles")
    head = git(root, "rev-parse", "HEAD").strip()
    source = {
        "command": command_fingerprint(settings.ocr_command), "rule_digest": "",
        "global_rule": json.dumps({"rules": [{"path": "**/*", "rule": GLOBAL}]}),
        "project_rule": json.dumps({"rules": [{"path": "Static.tsx", "rule": STYLE}]}),
    }
    with store.connection() as db:
        scope = json.dumps({"base_sha": base, "head_sha": head, "original_count": 2})
        db.execute("UPDATE review_jobs SET commit_sha=?,base_sha=?,scope_json=? WHERE id=1",
                   (head, base, scope))
        db.execute("UPDATE review_attempts SET config_snapshot=? WHERE job_id=1",
                   (json.dumps(source),))

    # 未安装可选 CLI 的环境只替换命令输出，测试仍验证逐页传递和数据库留存。
    if not command:
        def delegate(args: list[str], env: dict[str, str],
                     cwd: Path, timeout: float) -> tuple[int, str, str]:
            assert "OCR_LLM_TOKEN" not in env
            if args[0] == "git":
                return 0, "", ""
            path = args[-1]
            managed = Path(args[args.index("--rule") + 1])
            project = json.loads(managed.read_text())["rules"][0]
            global_path = Path(env["HOME"]) / rules.RULE_PATH
            fallback = json.loads(global_path.read_text())["rules"][0]
            selected, source = (
                (project, "custom") if path == project["path"] else (fallback, "global")
            )
            return 0, json.dumps({"schema_version": "1", "groups": [{
                "source": source, "pattern": selected["path"], "files": [path],
                "rule": selected["rule"],
            }]}), ""

        monkeypatch.setattr(rules, "execute_ocr_command", delegate)

    reviewed: dict[str, str] = {}

    def respond(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        page = json.loads(payload["messages"][1]["content"])
        reviewed[page["path"]] = page["review_rule"]
        static = "height: 400" in page["lines"][0]["text"]
        findings = [{"title": "固定内联样式", "trigger": "该页加载", "impact": "规则违规",
                     "side": "head", "line": 1}] if static else []
        body = json.dumps({
            "choices": [{"finish_reason": "stop", "message": {
                "content": json.dumps({"findings": findings}),
            }}],
            "usage": {"prompt_tokens": 40, "completion_tokens": 10, "total_tokens": 50},
        })
        return httpx.Response(200, stream=httpx.ByteStream(body.encode()))

    monkeypatch.setattr("ocr_manager.agent_review_worker.httpx.HTTPTransport",
                        lambda **_kwargs: httpx.MockTransport(respond))
    run_id = queue.enqueue(store, config, 1, "frozen-rules")
    assert queue.claim(store)
    execute(store, settings, run_id)
    record = agent_state(store, run_id)
    assert reviewed == {"Static.tsx": STYLE, "Dynamic.tsx": GLOBAL}
    assert record["status"] == "complete"
    assert [f["evidence"]["path"] for f in record["result"]["findings"]] == ["Static.tsx"]
    assert len(record["config"]["ocr_rule_sha256"]) == 64

    with TestClient(create_app(settings)) as client:
        response = client.get(f"/api/jobs/1/agent-comparisons/{run_id}", headers=ADMIN)
    assert response.status_code == 200, response.text
    assert STYLE not in response.text and GLOBAL not in response.text
    versions = {row["path"]: row["rule"] for row in response.json()["agent"]["files"]}
    assert {path: data["source"] for path, data in versions.items()} == {
        "Static.tsx": "custom", "Dynamic.tsx": "global",
    }
    assert all(len(data["sha256"]) == 64 for data in versions.values())


@pytest.mark.parametrize("rules_key", ["rules", "Rules"])
def test_rule_resolution_refuses_unfrozen_file(
    pilot: tuple[Store, Settings], tmp_path: Path, rules_key: str,
) -> None:
    """管理规则的主机文件引用未固化，用量记录为空并明确失败原因。"""

    store, settings = pilot
    settings = replace(settings, ocr_command="/usr/bin/true")
    file = tmp_path / ".md"
    file.write_text("合成的本机私有文件")
    source = {
        "command": command_fingerprint(settings.ocr_command), "rule_digest": "",
        "global_rule": None,
        "project_rule": json.dumps({rules_key: [{"path": "**/*", "rule": str(file)}]}),
    }
    with store.connection() as db:
        db.execute("UPDATE review_attempts SET config_snapshot=? WHERE job_id=1",
                   (json.dumps(source),))
    run_id = queue.enqueue(store, config_for(settings), 1, "unsafe-rule")
    assert queue.claim(store)
    execute(store, settings, run_id)
    agent = agent_state(store, run_id)
    assert (agent["status"], agent["reason"], agent["calls"]) == (
        "failed", "ocr_rules_unavailable", [],
    )
