"""共用合成任务及固定 Git 证据，浏览器和接口验收均不读取业务数据。"""

from __future__ import annotations

import json
from pathlib import Path

from ocr_manager import agent_review_store as queue
from ocr_manager.agent_review_config import AgentReviewConfig
from ocr_manager.attempt_history import save_snapshot
from ocr_manager.review_prototype.demo import create_fixture
from ocr_manager.review_prototype.input import freeze_input
from ocr_manager.review_prototype.result import Evidence, Finding, HunkCoverage, ReviewResult
from ocr_manager.storage import Store


def seed_task(store: Store, data_dir: Path) -> int:
    """生成同文件两个可定位位置和一条 OCR 发现，同时保留不支持旧范围的任务。"""

    repository = store.add_repository({
        "name": "双评审合成示例", "gitlab_url": "https://gitlab.example.invalid", "project_id": 42,
        "remote_url": "https://gitlab.example.invalid/demo/orders.git", "target_branch": "main",
        "auth_kind": "secret", "webhook_secret": "", "feishu_webhook": "",
    })
    assert repository == 1
    (data_dir / "repositories").mkdir()
    fixture = create_fixture(data_dir / "repositories/1", "long_diff")
    assert store.add_event(repository, 1, None, fixture.head_sha, None)
    event = store.next_event()
    assert event is not None
    store.finish_event(event["id"], [fixture.head_sha], {fixture.head_sha: ("synthetic", "")},
                       None, base_sha=fixture.base_sha)
    job = store.next_job()
    assert job is not None
    job_id = int(job["id"])
    with store.connection() as db:
        db.execute("UPDATE review_jobs SET scope_json=? WHERE id=?", (json.dumps({
            "base_sha": fixture.base_sha, "head_sha": fixture.head_sha, "original_count": 1,
        }), job_id))
    save_snapshot(store, job_id, {"model": "synthetic-ocr", "command": {"name": "ocr"}})
    store.finish_job(job_id, "complete", None, {
        "comments": [{"path": "orders.py", "start_line": 24, "content": "重试可能重复登记订单。"}],
        "summary": {"input_tokens": 80, "output_tokens": 30, "total_tokens": 110},
        "manifest": {"terminal_state": "complete", "coverage": {
            "selected": [{"path": "orders.py"}], "completed": [{"path": "orders.py"}],
            "reused": [], "failed": [], "waived": [],
        }},
    }, None)
    delivery = store.next_delivery()
    assert delivery is not None
    store.finish_delivery(delivery["id"], None)
    legacy_sha = "b" * 40
    store.add_event(repository, 2, None, legacy_sha, None)
    legacy = store.next_event()
    assert legacy is not None
    store.finish_event(legacy["id"], [legacy_sha], {legacy_sha: ("legacy", "")}, None)
    old_job = store.next_job()
    assert old_job is not None
    store.finish_job(old_job["id"], "complete", None, {"comments": []}, None)
    assert store.next_delivery() is None
    return job_id


def finish_comparison(store: Store, data_dir: Path, run_id: int) -> None:
    """种入可重复的两条已验证证据；恢复运行仍使用同一固定范围。"""

    claim = queue.claim(store)
    assert claim and claim["id"] == run_id
    row = queue.load_run(store, run_id)
    assert row is not None
    frozen = freeze_input(data_dir / "repositories/1", "1", row["base_sha"], row["head_sha"],
                         rule_digest=row["ocr_config_hash"], context_digest=row["context_digest"])
    assert queue.pin_input(store, run_id, frozen)
    hunk, = frozen.hunks
    lines = {item.head_line: item.text.rstrip("\n") for item in hunk.lines}
    findings = (
        Finding("重试造成重复登记", "写入后响应丢失再次请求", "同一订单产生两条记录",
                Evidence(1, hunk.path, "head", 24, lines[24])),
        Finding("重试入口没有校验订单号", "收到空订单号", "无效记录进入登记流程",
                Evidence(1, hunk.path, "head", 1, lines[1])),
    )
    call_id = queue.reserve_call(store, run_id, 1, 0, 1000, 1, 1000, 1000)
    assert call_id is not None
    queue.record_usage(store, call_id, 40, 10, "synthetic-agent")
    size = len(hunk.lines)
    queue.finish(store, run_id, reason="covered", result=ReviewResult(
        "complete", "covered", (HunkCoverage(1, size, size, size),), findings,
        cost_minor_units=None,
    ))


def seed_comparison(store: Store, data_dir: Path, config: AgentReviewConfig, job_id: int) -> int:
    """为页面验收提供一个已有完整结果的比较版本。"""

    run_id = queue.enqueue(store, config, job_id, "browser-first")
    finish_comparison(store, data_dir, run_id)
    return run_id
