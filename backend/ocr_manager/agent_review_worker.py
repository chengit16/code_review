"""运行独立影子评审；复核固定 Git/MR 版本，将结果写回已领取的 SQLite 尝试。"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import time
from dataclasses import replace

import httpx
from cryptography.fernet import InvalidToken
from pydantic import TypeAdapter
from unidiff.errors import UnidiffParseError

from ocr_manager import agent_review_store as queue
from ocr_manager.agent_capability_contracts import CapabilityRun
from ocr_manager.agent_capability_runtime import CapabilityRuntime
from ocr_manager.agent_pilot import repository_agent_config
from ocr_manager.agent_review_config import source_rule_fingerprint
from ocr_manager.agent_review_model import ChatPageModel
from ocr_manager.agent_review_profile import resolve_model
from ocr_manager.agent_review_rules import resolve_file_rules
from ocr_manager.cancellation import ReviewCancelled, cancellation_scope, check_cancellation
from ocr_manager.config import Settings
from ocr_manager.gitlab import GitLabClient
from ocr_manager.premerge import description_digest
from ocr_manager.review_prototype.graph import AgentProgress, run_agent
from ocr_manager.review_prototype.input import freeze_input
from ocr_manager.secrets import SecretBox
from ocr_manager.storage import Store

PROGRESS = TypeAdapter(AgentProgress)


def _mr_matches(settings: Settings, row: sqlite3.Row) -> bool:
    if row["source"] != "premerge":
        return True
    cipher = row["gitlab_token_ciphertext"]
    token = SecretBox(settings.master_key).decrypt(cipher) if cipher else ""
    client = GitLabClient(row["gitlab_url"], token)
    mr = client.get_merge_request(row["project_id"], row["mr_iid"])
    refs = mr.get("diff_refs")
    return (
        isinstance(refs, dict) and refs.get("head_sha") == row["head_sha"]
        and mr.get("sha") == row["head_sha"] and refs.get("base_sha") == row["base_sha"]
        and mr.get("state") in {"opened", "merged"}
        and mr.get("target_branch") == row["target_branch"]
        and mr.get("target_project_id") == row["project_id"]
        and (row["context_hint"] is None
             or row["context_hint"] == description_digest(mr.get("description")))
    )


def _cancelled(store: Store, run_id: int) -> bool:
    row = queue.load_run(store, run_id)
    return row is None or row["status"] != "running" or bool(row["cancel_requested"])


def execute(store: Store, settings: Settings, run_id: int) -> None:
    """验证授权和当前任务，读取固定 Git 对象，再执行有界模型调用并保存独立终态。"""

    # 1. 消费时重新确认试点授权和快照；Git 缓存缺失时明确失败，不换成当前分支。
    run = queue.load_run(store, run_id)
    if run is None or run["status"] != "running":
        return
    with store.connection() as db:
        config = repository_agent_config(db, settings, run["repository_id"])
    if config is None:
        queue.finish(
            store, run_id, reason="model_config_invalid" if settings.agent_review_error
            else "not_enabled",
        )
        return
    configured = config
    try:
        frozen = (CapabilityRun.model_validate_json(run["capability_snapshot"])
                  if run["capability_snapshot"] else None)
        config = resolve_model(
            store, config, run["repository_id"], master_key=settings.master_key,
            profile_id=frozen.model_profile_id if frozen else None,
        )
    except (InvalidToken, ValueError):
        queue.finish(store, run_id, reason="model_config_invalid")
        return
    rule_fingerprint = json.loads(run["model_snapshot"]).get("ocr_rule_sha256")
    if (rule_fingerprint is not None
            and rule_fingerprint != source_rule_fingerprint(run["ocr_snapshot"])):
        queue.finish(store, run_id, reason="ocr_rules_unavailable")
        return
    if run["model_snapshot"] != config.snapshot(rule_fingerprint):
        # 历史快照沿用原 HTTP 等待、页数、总时限和 Token 策略。
        original_io = replace(config, read_timeout_seconds=None)
        previous = replace(original_io, max_reads=configured.max_reads,
                           timeout_seconds=configured.timeout_seconds)
        original = replace(previous, enforce_token_budget=True)
        for candidate in (original_io, previous, original):
            if run["model_snapshot"] == candidate.snapshot(rule_fingerprint):
                config = candidate
                break
        else:
            queue.finish(store, run_id, reason="model_config_changed")
            return
    if not queue.source_is_current(run):
        queue.finish(store, run_id, reason="source_changed")
        return
    deadline = (time.monotonic() + config.timeout_seconds - float(run["elapsed_seconds"])
                if config.timeout_seconds is not None else None)

    def save(progress: AgentProgress) -> None:
        if not queue.checkpoint(store, run_id, progress):
            check_cancellation()
            raise RuntimeError("Agent 页进度提交冲突")

    try:
        with cancellation_scope(lambda: _cancelled(store, run_id)):
            # 2. 合并前 MR 使用只读 API 复核。读取 Git 对象不触发 fetch，也不创建工作树。
            if not _mr_matches(settings, run):
                queue.finish(store, run_id, reason="mr_version_changed")
                return
            try:
                snapshot = freeze_input(
                    settings.data_dir / "repositories" / str(run["repository_id"]),
                    str(run["repository_id"]), run["base_sha"], run["head_sha"],
                    rule_digest=run["ocr_config_hash"], context_digest=run["context_digest"],
                )
            except (OSError, ValueError, UnidiffParseError, TimeoutError):
                queue.finish(store, run_id, reason="input_unavailable")
                return
            rules = None
            if rule_fingerprint is not None:
                try:
                    rules = resolve_file_rules(
                        settings, settings.data_dir / "repositories" / str(run["repository_id"]),
                        ocr_snapshot=run["ocr_snapshot"], head_sha=run["head_sha"],
                        checkout_sha=(run["base_sha"] if run["source"] == "premerge"
                                      else run["head_sha"]),
                        paths=tuple(dict.fromkeys(hunk.path for hunk in snapshot.hunks)),
                    )
                except (ValueError, OSError, TimeoutError, subprocess.TimeoutExpired):
                    queue.finish(store, run_id, reason="ocr_rules_unavailable")
                    return
            versions = ({path: rule.evidence() for path, rule in rules.items()}
                        if rules is not None else None)
            if not queue.pin_input(store, run_id, snapshot, versions):
                queue.finish(store, run_id, reason="input_changed")
                return

            # 3. 无环境代理和重定向，单页在发送前登记调用；结论提交前再次复核 MR。
            progress = (
                PROGRESS.validate_json(run["progress_json"]) if run["progress_json"] is not None
                else None
            )
            capabilities = None
            if frozen:
                try:
                    capabilities = CapabilityRuntime(store, settings, run, frozen, deadline)
                except (LookupError, ValueError):
                    queue.finish(store, run_id, reason="capability_unavailable")
                    return
            with httpx.Client(trust_env=False, transport=httpx.HTTPTransport(retries=0)) as client:
                result = run_agent(
                    snapshot, ChatPageModel(store, run_id, config, client,
                                            deadline=deadline, rules=rules,
                                            capabilities=capabilities),
                    page_lines=config.page_lines, max_reads=config.max_reads, resume=progress,
                    checkpoint=save,
                    prepare=(capabilities.prepare if capabilities and frozen and frozen.steps
                             else None),
                )
            check_cancellation()
            if not _mr_matches(settings, run):
                queue.finish(store, run_id, reason="mr_version_changed")
                return
            queue.finish(
                store, run_id, reason=result.reason, result=replace(result, cost_minor_units=None),
            )
    except ReviewCancelled:
        queue.finish(store, run_id, reason="cancelled")
    except (httpx.HTTPError, InvalidToken, RuntimeError, ValueError):
        # 远端错误正文和凭据不进入 SQLite；已登记的模型调用仍然可核对。
        queue.finish(store, run_id, reason="verification_unavailable")
