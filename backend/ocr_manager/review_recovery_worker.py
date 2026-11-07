"""在唯一模型槽执行独立失败子集；工件锁保护清理，候选版本不替代初审或发送通知。"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from ocr_manager.artifact_lock import artifact_lock
from ocr_manager.cancellation import ReviewCancelled, cancellation_scope, check_cancellation
from ocr_manager.config import Settings
from ocr_manager.git_repo import GitRepository
from ocr_manager.ocr import classify_result, run_review
from ocr_manager.range_preflight import inspect_range
from ocr_manager.review_failures import classify_review_error
from ocr_manager.review_recovery_domain import RecoveryConflict, coverage_items, digest
from ocr_manager.review_recovery_store import current_hash, finish, source_state, stopping
from ocr_manager.review_results import project_review_result
from ocr_manager.secrets import SecretBox
from ocr_manager.storage import Store


def _frozen_source(store: Store, settings: Settings, task: dict[str, Any]) -> tuple[
        dict[str, Any], dict[str, Any], dict[str, Any]]:
    with store.connection() as db:
        db.execute("BEGIN")
        row = db.execute("SELECT * FROM review_recoveries WHERE id=? AND status='running' "
                         "AND execution_token=?", (task["id"], task["execution_token"])).fetchone()
        if row is None or row["cancel_requested"]:
            raise ReviewCancelled
        job, source, revision, _ = source_state(db, task["job_id"])
        attempt = db.execute("SELECT * FROM review_attempts WHERE job_id=? AND attempt_number=?",
                             (task["job_id"], task["source_attempt"])).fetchone()
    if (job["attempts"] != task["source_attempt"] or revision != task["source_revision"]
            or digest(source) != task["source_digest"] or attempt is None
            or attempt["result_json"] != job["result_json"]
            or attempt["config_snapshot"] != task["config_snapshot"]):
        raise RecoveryConflict("source_changed")
    if current_hash(store, settings, job) != job["config_hash"]:
        raise RecoveryConflict("configuration_changed")
    # 不跟随符号链接或越界引用，且必须核验根尝试的原始输入，不依赖候选重建 SHA。
    root = settings.data_dir.resolve() / "runs" / str(job["id"])
    path = Path(attempt["result_path"] or "")
    try:
        resolved = path.resolve(strict=True)
        relative = resolved.relative_to(root)
        if (not relative.parts or path.is_symlink() or resolved.name != "result.json"
                or any(parent.is_symlink() for parent in path.parents)):
            raise ValueError
        with resolved.open("rb") as file:
            content = file.read(16 * 1024 * 1024 + 1)
        if len(content) > 16 * 1024 * 1024:
            raise ValueError
        raw = json.loads(content)
        if not isinstance(raw, dict):
            raise ValueError
        classify_result(raw, job["commit_sha"], job["base_sha"])
        projected = project_review_result(raw)
        original = json.loads(attempt["result_json"])
        if any(projected[key] != original.get(key) for key in ("manifest", "comments")):
            raise ValueError
        if coverage_items(raw)["selected"] != coverage_items(source)["selected"]:
            raise ValueError
    except (OSError, ValueError, TypeError) as error:
        raise RecoveryConflict("source_artifact_invalid") from error
    return job, source, json.loads(task["config_snapshot"])


def execute_recovery(store: Store, settings: Settings, task: dict[str, Any]) -> None:
    """须由独占 Worker 的模型槽调用；失败不自动重跑，所有外部调用都有取消与预算边界。"""

    run_dir = settings.data_dir / "runs" / str(task["job_id"]) / "recoveries" / str(task["id"])
    checkout = run_dir / "checkout"
    git: GitRepository | None = None
    child: dict[str, Any] | None = None
    # 1. 与删除后清理、全量重审及其他工件使用互斥；HTTP 永远不进入本执行链。
    with artifact_lock(settings.data_dir, task["job_id"], blocking=True):
        try:
            with cancellation_scope(lambda: stopping(store, task)):
                job, source, snapshot = _frozen_source(store, settings, task)
                from ocr_manager.worker import review_settings, snapshot_hash

                if snapshot_hash(snapshot) != job["config_hash"]:
                    raise RecoveryConflict("configuration_changed")
                model_settings, model_version = review_settings(
                    store, settings, job["repository_id"])
                # 摘要读取和凭据装配不是同一事务；核对实际设置，拒绝读取窗口中的配置漂移。
                actual = {"provider": model_settings.ocr_provider,
                    "model": model_settings.ocr_model,
                    "base_url": model_settings.ocr_base_url, "model_version": model_version,
                    "timeout_seconds": model_settings.ocr_timeout_seconds,
                    "review_language": model_settings.review_language,
                    "max_files": model_settings.ocr_max_files,
                    "max_tokens_budget": model_settings.ocr_max_tokens_budget,
                    "concurrency": model_settings.ocr_concurrency,
                    "effort": model_settings.ocr_effort}
                if (any(snapshot.get(key) != value for key, value in actual.items()) or
                        snapshot["input_policy"]["filter_enabled"] !=
                        model_settings.ocr_newline_filter_enabled):
                    raise RecoveryConflict("configuration_changed")
                model_settings = replace(model_settings, ocr_max_tokens_budget=task["token_budget"],
                                         ocr_timeout_seconds=task["timeout_seconds"])
                repository = store.get_repository(job["repository_id"])
                if repository is None:
                    raise ReviewCancelled
                if repository["gitlab_token_ciphertext"]:
                    repository["gitlab_token"] = SecretBox(settings.master_key).decrypt(
                        repository["gitlab_token_ciphertext"])
                # 2. 固定原始 SHA 和仓库规则；新 checkout 保留完整上下文，不伪造提交。
                git = GitRepository(settings.data_dir, repository)
                git.fetch()
                if (not git.is_on_target(job["commit_sha"]) or
                        git.rule_digest(job["commit_sha"]) != job["rule_digest"] or
                        job["base_sha"] is not None and
                        not git.is_range_base(job["base_sha"], job["commit_sha"])):
                    raise RecoveryConflict("git_input_changed")
                git.checkout(job["commit_sha"], checkout)
                scope = inspect_range(checkout, job["commit_sha"], job["base_sha"],
                                      filter_enabled=model_settings.ocr_newline_filter_enabled)

                def before_stage(stage: str) -> None:
                    if (stage == "review"
                            and current_hash(store, settings, job) != job["config_hash"]):
                        raise RecoveryConflict("configuration_changed")
                    check_cancellation()

                # 3. 双预览与正式 manifest 均须精确命中剩余集合；用量只属于本批次。
                coverage = coverage_items(source)
                _, child = run_review(model_settings, checkout, run_dir, job["commit_sha"],
                    snapshot["global_rule"], snapshot["project_rule"], before_stage,
                    base_sha=job["base_sha"], scope_analysis=scope,
                    recovery_selection=(set(coverage["selected"]), set(coverage["failed"])))
                check_cancellation()
                classify_result(child, job["commit_sha"], job["base_sha"])
                if current_hash(store, settings, job) != job["config_hash"]:
                    raise RecoveryConflict("configuration_changed")
                finish(store, task, child, str(run_dir / "result.json"))
        except ReviewCancelled:
            finish(store, task, child, error_code="cancelled")
        except RecoveryConflict as error:
            # 错误正文均为本领域固定码，不含 Git stderr、模型响应或原始工件。
            finish(store, task, child, error_code=str(error))
        except Exception as error:
            # 复用允许字段分类，保留范围/超时等可解释事实，不保存异常正文或自动重跑。
            failure = classify_review_error(error)
            finish(store, task, None, error_code=f"execution_{failure.category}")
        finally:
            if git is not None:
                try:
                    git.remove_checkout(checkout)
                except (OSError, RuntimeError):
                    # 清理失败保留受控目录供后续维护，不覆盖已提交批次或泄漏 Git 输出。
                    pass
