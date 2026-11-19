"""用临时 Git/SQLite 和本机合成模型验证影子任务的持久化、调度和付费隔离。"""

from __future__ import annotations

import json
import sys
import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from ocr_manager import agent_review_store as queue
from ocr_manager import worker
from ocr_manager.agent_review_cli import main as agent_cli
from ocr_manager.agent_review_config import AgentReviewConfig, load_agent_config
from ocr_manager.agent_review_worker import execute
from ocr_manager.config import Settings, load_settings
from ocr_manager.gitlab import GitLabClient
from ocr_manager.ocr_probe_endpoint import SyntheticEndpoint
from ocr_manager.review_prototype.demo import create_fixture
from ocr_manager.review_prototype.graph import AgentProgress
from ocr_manager.review_prototype.result import HunkCoverage
from ocr_manager.secrets import SecretBox
from ocr_manager.storage import SCHEMA_VERSION, Store
from ocr_manager.worker import worker_lock
from ocr_manager.worker_scheduler import WorkerScheduler
from test_task_operations import populate
from test_worker_scheduler import pump


class AgentEndpoint(SyntheticEndpoint):
    """脚本模型读取合成差异，按测试需要返回故障或阻塞；无外部流量。"""

    def __init__(self) -> None:
        super().__init__(("orders.py", "orders.py"))
        self.fail = False
        self.invalid_evidence = False
        self.omit_usage = False
        self.blocked = False

    def reply(self, request: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        """返回页内行号与计费夹具，只记录页位置和请求形状。"""

        page = json.loads(request["messages"][1]["content"])
        self.calls.append({"offset": page["start"], "path": page["path"],
                           "max_completion_tokens": request["max_completion_tokens"]})
        if self.blocked:
            self.beta_reached.set()
            self.release_beta.wait(4)
        if self.fail:
            return 503, {"error": {"message": "合成端点拒绝响应"}}
        findings = [
            {"title": "重试可能重复登记订单", "trigger": "响应丢失后再次请求",
             "impact": "重复登记", "side": "head",
             "line": line["head_line"] if not self.invalid_evidence else 999_999}
            for line in page["lines"] if line["text"].strip() == "record_order(order_id)"
        ]
        value: dict[str, Any] = {
            "model": "synthetic-version-1",
            "choices": [{"finish_reason": "stop", "message": {
                "content": json.dumps({"findings": findings}, ensure_ascii=False),
            }}],
        }
        if not self.omit_usage:
            value["usage"] = {"prompt_tokens": 40, "completion_tokens": 10, "total_tokens": 50}
        return 200, value


@pytest.fixture
def endpoint() -> Iterator[AgentEndpoint]:
    """固定为环回随机端口，清理时解除测试中的阻塞。"""

    server = AgentEndpoint()
    server.start()
    try:
        yield server
    finally:
        server.close()


@pytest.fixture
def pilot(
    client: TestClient, settings: Settings, endpoint: AgentEndpoint,
) -> tuple[Store, Settings]:
    """复用正式任务写入方法，种入与临时 Git 范围相符的合成 OCR 初审。"""

    store, repository_id = populate(client, settings, 1)
    root = settings.data_dir / "repositories"
    root.mkdir()
    fixture = create_fixture(root / str(repository_id), "long_diff")
    job = store.next_job()
    assert job
    with store.connection() as db:
        db.execute("""UPDATE review_jobs SET commit_sha=?,base_sha=?,scope_json=? WHERE id=?""",
                   (fixture.head_sha, fixture.base_sha, json.dumps({
                       "base_sha": fixture.base_sha, "head_sha": fixture.head_sha,
                       "original_count": 1,
                   }), job["id"]))
    store.finish_job(job["id"], "complete", None, {
        "comments": [], "manifest": {"terminal_state": "complete"},
    }, None)
    delivery = store.next_delivery()
    assert delivery
    store.finish_delivery(delivery["id"], None)
    config = AgentReviewConfig(endpoint.url, "synthetic", frozenset({repository_id}),
                               "test-agent-key", page_lines=5)
    return store, replace(settings, agent_review=config)


def config_for(settings: Settings) -> AgentReviewConfig:
    """测试只允许使用本机夹具启用的配置。"""

    assert settings.agent_review
    return settings.agent_review


def agent_state(store: Store, run_id: int) -> dict[str, Any]:
    """使用公开报告检查终态与细节，模拟打开上次运行。"""

    value = queue.report(store, run_id)["agent"]
    assert isinstance(value, dict)
    return value


def test_scheduler_timeout_partial_and_single_side_rerun(
    pilot: tuple[Store, Settings], endpoint: AgentEndpoint, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """真实调度经过环回 HTTP，三版共享一次 OCR，CLI 可重读旧版本。"""

    store, settings = pilot
    config = config_for(settings)
    endpoint.blocked = True
    timeout_config = replace(config, timeout_seconds=1)
    original = queue.enqueue(store, timeout_config, 1, "timeout")
    assert queue.enqueue(store, timeout_config, 1, "timeout") == original
    with worker_lock(settings.data_dir), WorkerScheduler(
        store, replace(settings, agent_review=timeout_config),
    ) as scheduler:
        pump(scheduler, lambda: agent_state(store, original)["status"] == "failed")
    first = queue.report(store, original)
    assert first["agent"]["reason"] == "model_timeout"
    assert first["agent"]["calls"][0]["status"] == "unknown"
    assert first["agent"]["cost_minor_units"] is None
    endpoint.release_beta.set()
    endpoint.blocked = False

    limited = replace(config, max_reads=1)
    partial = queue.enqueue(store, limited, 1, "partial", original)
    with worker_lock(settings.data_dir), WorkerScheduler(
        store, replace(settings, agent_review=limited),
    ) as scheduler:
        pump(scheduler, lambda: agent_state(store, partial)["status"] == "partial")
    second = queue.report(store, partial)
    assert second["agent"]["result"]["coverage"][0]["reviewed_end"] == 5

    complete = queue.enqueue(store, config, 1, "complete", partial)
    with worker_lock(settings.data_dir), WorkerScheduler(store, settings) as scheduler:
        pump(scheduler, lambda: agent_state(store, complete)["status"] == "complete")
    third = queue.report(store, complete)
    assert first["ocr"] == second["ocr"] == third["ocr"]
    assert first == queue.report(store, original)
    assert (first["comparison"]["input_key"] == second["comparison"]["input_key"]
            == third["comparison"]["input_key"])
    assert third["comparison"]["previous_id"] == partial
    assert third["agent"]["result"]["coverage"][0]["reviewed_end"] == 25
    assert third["agent"]["result"]["findings"][0]["evidence"]["line"] == 24
    assert [call["page_offset"] for call in third["agent"]["calls"]] == [0, 5, 10, 15, 20]
    assert third["agent"]["calls"][0]["provider_model"] == "synthetic-version-1"
    with store.connection() as db:
        assert db.execute("SELECT count(*) FROM review_attempts").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM notification_deliveries").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM gitlab_publications").fetchone()[0] == 0

    monkeypatch.setattr("ocr_manager.agent_review_cli.load_settings", lambda: settings)
    monkeypatch.setattr(sys, "argv", ["agent_review_cli", "report", "--id", str(complete)])
    agent_cli()
    cli_report = capsys.readouterr().out
    assert json.loads(cli_report) == third
    assert config.api_key not in cli_report
    report_path = settings.data_dir / "agent-comparisons.json"
    report_path.write_text(json.dumps([first, second, third], ensure_ascii=False, indent=2))
    print(f"双路合成报告：{report_path}")


@pytest.mark.parametrize(("failure", "reason", "usage_status"), [
    ("invalid_evidence", "model_response", "recorded"),
    ("omit_usage", "model_response", "unknown"),
    ("fail", "model_unavailable", "unknown"),
])
def test_provider_errors_stop_before_next_page(
    pilot: tuple[Store, Settings], endpoint: AgentEndpoint,
    failure: str, reason: str, usage_status: str,
) -> None:
    """已知用量和证据有效性各自裁决，缺用量或响应失败不会继续调用。"""

    setattr(endpoint, failure, True)
    store, settings = pilot
    config = replace(config_for(settings), page_lines=40)
    identifier = queue.enqueue(store, config, 1, "invalid")
    assert queue.claim(store)
    execute(store, replace(settings, agent_review=config), identifier)
    agent = agent_state(store, identifier)
    assert (agent["status"], agent["reason"]) == ("failed", reason)
    assert agent["result"]["findings"] == []
    assert agent["result"]["coverage"][0]["reviewed_end"] == 0
    assert [call["status"] for call in agent["calls"]] == [usage_status]
    assert len(endpoint.calls) == 1


def test_resume_checkpoint_only_when_previous_calls_are_confirmed(
    pilot: tuple[Store, Settings], endpoint: AgentEndpoint,
) -> None:
    """重启跳过已核对的页，未确认调用保留费用未知且不会自动重发。"""

    store, settings = pilot
    config = config_for(settings)
    first = queue.enqueue(store, config, 1, "safe-resume")
    assert queue.claim(store)
    reserved = queue.reserve_call(store, first, 1, 0, 512, 8, 64_000, 128_000)
    assert reserved
    queue.record_usage(store, reserved, 40, 10)
    assert queue.checkpoint(store, first, AgentProgress((HunkCoverage(1, 25, 5, 5),), (), (), 1, 0))
    store.recover()
    assert agent_state(store, first)["status"] == "queued"
    assert queue.claim(store)
    execute(store, settings, first)
    final = agent_state(store, first)
    assert final["status"] == "complete"
    assert final["result"]["steps"][0]["stage"] == "resume"
    assert [call["offset"] for call in endpoint.calls] == [5, 10, 15, 20]

    second = queue.enqueue(store, config, 1, "uncertain", first)
    assert queue.claim(store)
    assert queue.reserve_call(store, second, 1, 0, 512, 8, 64_000, 128_000)
    store.recover()
    interrupted = agent_state(store, second)
    assert (interrupted["status"], interrupted["reason"]) == ("failed", "worker_interrupted")
    assert interrupted["calls"][0]["status"] == "unknown"
    assert queue.claim(store) is None
    limited = replace(config, max_source_tokens=515)
    third = queue.enqueue(store, limited, 1, "limit-after-unknown", second)
    assert queue.claim(store)
    execute(store, replace(settings, agent_review=limited), third)
    assert agent_state(store, third)["calls"] == []
    assert agent_state(store, third)["reason"] == "model_budget"


def test_formal_review_claimed_before_agent(
    pilot: tuple[Store, Settings], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同一个模型槽优先领取正式初审，同仓库 Agent 在空闲后才会运行。"""

    store, settings = pilot
    agent = queue.enqueue(store, config_for(settings), 1, "shadow")
    assert store.add_event(1, 2, None, None, None)
    event = store.next_event()
    assert event is not None
    sha = "3" * 40
    store.finish_event(event["id"], [sha], {sha: ("synthetic", "")}, None)
    formal_ran = threading.Event()

    def finish_formal(_store: Store, _settings: Settings, task: dict[str, Any]) -> None:
        _store.finish_job(task["id"], "cancelled", None, None, "合成任务结束")
        formal_ran.set()

    monkeypatch.setattr(worker, "review_job", finish_formal)
    with worker_lock(settings.data_dir), WorkerScheduler(store, settings) as scheduler:
        assert scheduler.tick()
        assert agent_state(store, agent)["status"] == "queued"
        pump(scheduler, formal_ran.is_set)
        pump(scheduler, lambda: agent_state(store, agent)["status"] == "complete")


def test_cancel_in_flight_preserves_independent_history(
    pilot: tuple[Store, Settings], endpoint: AgentEndpoint,
) -> None:
    """取消在模型到达前落库，仅本侧取消，已发请求保留账目。"""

    store, settings = pilot
    run_id = queue.enqueue(store, config_for(settings), 1, "cancel")
    ocr = queue.report(store, run_id)["ocr"]
    endpoint.blocked = True
    with worker_lock(settings.data_dir), WorkerScheduler(store, settings) as scheduler:
        try:
            pump(scheduler, endpoint.beta_reached.is_set)
            assert queue.cancel(store, run_id)
            assert queue.claim(store) is None
        finally:
            endpoint.release_beta.set()
        pump(scheduler, lambda: agent_state(store, run_id)["status"] == "cancelled")
    assert queue.report(store, run_id)["ocr"] == ocr
    assert len(agent_state(store, run_id)["calls"]) == 1


def test_token_budget_and_concurrent_enqueue(pilot: tuple[Store, Settings]) -> None:
    """并发重复点击只生成一条，预算不足时没有远端调用。"""

    store, settings = pilot
    config = replace(config_for(settings), max_total_tokens=1)
    barrier = threading.Barrier(2)

    def submit() -> int:
        barrier.wait(3)
        return queue.enqueue(store, config, 1, "same")

    with ThreadPoolExecutor(2) as executor:
        one, two = executor.submit(submit), executor.submit(submit)
        identifier = one.result()
        assert identifier == two.result()
    with pytest.raises(ValueError, match="请求键已绑定"):
        queue.enqueue(store, config_for(settings), 1, "same")
    assert queue.claim(store)
    execute(store, replace(settings, agent_review=config), identifier)
    agent = agent_state(store, identifier)
    assert agent["reason"] == "model_budget" and agent["calls"] == []
    assert agent["result"]["coverage"][0]["reviewed_end"] == 0


def test_premerge_changed_after_call_discards_result(
    pilot: tuple[Store, Settings], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GitLab 的 MR 变化不发布迟到结论，仍保留已发送的调用及 OCR 结果。"""

    store, settings = pilot
    with store.connection() as db:
        db.execute("UPDATE repositories SET gitlab_token_ciphertext=? WHERE id=1",
                   (SecretBox(settings.master_key).encrypt("synthetic-gitlab-key"),))
        db.execute("UPDATE review_jobs SET source='premerge' WHERE id=1")
        job = db.execute("SELECT base_sha,commit_sha,target_branch FROM review_jobs").fetchone()
    responses = iter([
        {"sha": job["commit_sha"], "state": "opened", "target_project_id": 42,
         "target_branch": job["target_branch"], "diff_refs": {
             "base_sha": job["base_sha"], "head_sha": job["commit_sha"]}},
        {"state": "closed"},
    ])
    monkeypatch.setattr(GitLabClient, "get_merge_request", lambda *_args: next(responses))
    run_id = queue.enqueue(store, config_for(settings), 1, "premerge")
    assert queue.claim(store)
    execute(store, settings, run_id)
    result = agent_state(store, run_id)
    assert result["reason"] == "mr_version_changed" and result["result"] is None
    assert len(result["calls"]) == 5
    assert queue.report(store, run_id)["ocr"]["status"] == "complete"


def test_migration_retains_ocr_and_requires_explicit_scope(pilot: tuple[Store, Settings]) -> None:
    """重建第 54 版库形状并迁移，只创建新表，旧任务不会自动触发 Agent。"""

    store, settings = pilot
    with store.connection() as db:
        initial_ocr = tuple(db.execute("SELECT * FROM review_attempts").fetchone())
        db.execute("DROP TABLE agent_review_calls")
        db.execute("DROP TABLE agent_reviews")
        db.execute("PRAGMA user_version=54")
    store.migrate()
    with store.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION == 55
        assert tuple(db.execute("SELECT * FROM review_attempts").fetchone()) == initial_ocr
        assert not db.execute("PRAGMA foreign_key_check").fetchall()
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        db.execute("UPDATE review_jobs SET scope_json=NULL")
    assert queue.claim(store) is None
    with pytest.raises(ValueError, match="缺少可核对"):
        queue.enqueue(store, config_for(settings), 1, "old")


def test_config_requires_explicit_egress(pilot: tuple[Store, Settings]) -> None:
    """错误端点、未经许可的仓库和跑前授权撤回均拒绝发送差异。"""

    store, settings = pilot
    config = config_for(settings)
    with pytest.raises(ValueError, match="仓库未获准"):
        queue.enqueue(store, replace(config, repositories=frozenset({2})), 1, "denied")
    with pytest.raises(ValueError, match="Agent 端点"):
        load_agent_config(lambda key, default: {
            "OCR_APP_AGENT_ENDPOINT": "http://example.test/v1/chat/completions",
        }.get(key, default))
    run_id = queue.enqueue(store, config, 1, "revoked")
    assert queue.claim(store)
    execute(store, replace(settings, agent_review=None), run_id)
    agent = agent_state(store, run_id)
    assert (agent["status"], agent["reason"], agent["calls"]) == ("failed", "not_enabled", [])


def test_invalid_agent_settings_leave_ocr_settings_available(
    monkeypatch: pytest.MonkeyPatch, settings: Settings,
) -> None:
    """Agent 地址错误只禁用影子运行，进程仍可读取基础服务配置。"""

    monkeypatch.delenv("OCR_APP_CONFIG_FILE", raising=False)
    monkeypatch.setenv("OCR_APP_MASTER_KEY", settings.master_key)
    monkeypatch.setenv("OCR_APP_ADMIN_TOKEN", settings.admin_token)
    monkeypatch.setenv("OCR_APP_AGENT_ENDPOINT", "https://example.test:wrong/v1/chat/completions")
    loaded = load_settings()
    assert loaded.admin_token == settings.admin_token
    assert loaded.agent_review is None and loaded.agent_review_error
