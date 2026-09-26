"""消费 SQLite 中的合并事件、逐提交评审任务及飞书投递。"""

from __future__ import annotations

import fcntl
import hashlib
import json
import logging
import os
import shutil
import signal
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any

import httpx
from cryptography.fernet import InvalidToken

from ocr_manager.artifact_lock import artifact_lock
from ocr_manager.attempt_history import save_snapshot
from ocr_manager.cancellation import ReviewCancelled, cancellation_scope, check_cancellation
from ocr_manager.checks import run_connection_check
from ocr_manager.config import Settings, load_settings
from ocr_manager.feishu import FeishuDeliveryError, send_review
from ocr_manager.git_repo import GitRepository
from ocr_manager.gitlab import GitLabClient, project_web_url
from ocr_manager.ocr import check_rule, run_review
from ocr_manager.project_limits import apply_limits, get_limits
from ocr_manager.secrets import SecretBox
from ocr_manager.storage import Store
from ocr_manager.task_control import cancellation_requested
from ocr_manager.tasks import set_job_stage

LOGGER = logging.getLogger(__name__)


def stop_worker(_signal: int, _frame: Any) -> None:
    """把系统停止信号变为正常栈展开，以清理 OCR 进程组和 worktree。"""

    raise SystemExit(0)


@contextmanager
def worker_lock(data_dir: Path) -> Iterator[None]:
    """同一数据目录仅允许一个 Worker 领取队列；进程退出后系统自动释放锁。"""

    data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(data_dir / "worker.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("已有 Worker 正在处理此数据目录") from error
        yield
    finally:
        os.close(descriptor)


def worker_is_running(data_dir: Path) -> bool:
    """通过单实例锁判断 Worker 进程是否仍在运行，包括 OCR 执行期间。"""

    try:
        descriptor = os.open(data_dir / "worker.lock", os.O_RDWR)
    except FileNotFoundError:
        return False
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        return False
    finally:
        os.close(descriptor)


def review_settings(
    store: Store, settings: Settings, repository_id: int | None = None
) -> tuple[Settings, int]:
    """从启用的模型配置读取评审参数；测试注入的 Settings 只用于隔离验证。"""

    limits = get_limits(store, repository_id)
    profile_id = limits["model_profile_id"]
    profile = (next((item for item in store.list_model_profiles() if item["id"] == profile_id),
                    None) if profile_id else store.get_model_profile())
    if profile is None:
        if settings.ocr_model and settings.ocr_api_key:
            return apply_limits(settings, limits), 0
        raise ValueError("请先在管理台启用 Agent 模型")
    key = SecretBox(settings.master_key).decrypt(profile["api_key_ciphertext"])
    return replace(
        apply_limits(settings, limits),
        ocr_provider=profile["provider"],
        ocr_model=profile["model"],
        ocr_api_key=key,
        ocr_base_url=profile["base_url"],
    ), int(profile["version"])


def configuration_snapshot(
    store: Store, settings: Settings, rule_digest: str = "", repository_id: int | None = None
) -> dict[str, Any]:
    """按模型、OCR 安装文件及该提交规则记录配置事实，始终排除密钥。"""

    model_settings, model_version = review_settings(store, settings, repository_id)
    command = shutil.which(settings.ocr_command)
    command_fingerprint: dict[str, Any] = {"name": settings.ocr_command}
    if command:
        executable = Path(command).resolve()
        metadata = executable.stat()
        command_fingerprint |= {
            "path": str(executable),
            "size": metadata.st_size,
            "modified_ns": metadata.st_mtime_ns,
        }
        # npm 启动脚本可能保持不变，包版本用于识别其背后的 OCR 二进制升级。
        package = executable.parent.parent / "package.json"
        if executable.name == "ocr.js" and package.is_file():
            package_data = json.loads(package.read_text(encoding="utf-8"))
            command_fingerprint["package_version"] = package_data.get("version")
    return {
            "provider": model_settings.ocr_provider,
            "model": model_settings.ocr_model,
            "base_url": model_settings.ocr_base_url,
            "model_version": model_version,
            "command": command_fingerprint,
            "timeout_seconds": model_settings.ocr_timeout_seconds,
            "max_files": model_settings.ocr_max_files,
            "max_tokens_budget": model_settings.ocr_max_tokens_budget,
            "model_profile_id": get_limits(store, repository_id)["model_profile_id"],
            "rule_digest": rule_digest,
            "global_rule": store.get_review_rule(None),
            "project_rule": (
                store.get_review_rule(repository_id) if repository_id is not None else None
            ),
            "notification_min_severity": (
                store.get_project_policy(repository_id) if repository_id is not None else "medium"
            ),
        }


def config_hash(
    store: Store, settings: Settings, rule_digest: str = "", repository_id: int | None = None
) -> str:
    """对安全配置事实建立稳定摘要，仍作为任务去重与执行校验依据。"""

    snapshot = configuration_snapshot(store, settings, rule_digest, repository_id)
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()


def is_temporary(error: Exception) -> bool:
    """网络与运行时故障可退避重试；提交范围冲突交给管理员确认。"""

    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code == 429 or error.response.status_code >= 500
    return isinstance(error, (httpx.RequestError, TimeoutError, RuntimeError))


def expand_event(store: Store, settings: Settings, event: dict[str, Any]) -> None:
    """按最终合并方式建立可追溯的逐提交评审任务。"""

    repository = store.get_repository(event["repository_id"])
    if repository is None:
        store.finish_event(event["id"], None, {}, "仓库配置已删除")
        return
    try:
        # 1. 从 GitLab 重新确认 MR，防止 webhook 内容或投递顺序决定审查范围。
        if repository["gitlab_token_ciphertext"]:
            repository["gitlab_token"] = SecretBox(settings.master_key).decrypt(
                repository["gitlab_token_ciphertext"]
            )
        gitlab = GitLabClient(
            repository["gitlab_url"], repository.get("gitlab_token") or settings.gitlab_api_token
        )
        gitlab.check_access(
            repository["project_id"], repository["target_branch"], repository["remote_url"]
        )
        if event["mr_iid"] < 0:
            # Push 不存在 MR；仅在 Git 确认快进范围后建立逐提交任务。
            git = GitRepository(settings.data_dir, repository)
            git.fetch()
            commits = git.push_commits(event["squash_sha"], event["merge_sha"])
            push_snapshots = {
                sha: (
                    config_hash(store, settings, git.rule_digest(sha), repository["id"]),
                    git.rule_digest(sha),
                )
                for sha in commits
            }
            store.finish_event(event["id"], commits, push_snapshots, None)
            return
        mr = gitlab.get_merge_request(repository["project_id"], event["mr_iid"])
        if (
            mr.get("state") != "merged"
            or mr.get("target_branch") != repository["target_branch"]
            or mr.get("target_project_id") != repository["project_id"]
        ):
            raise ValueError("MR 未合并到配置项目的目标分支")
        git = GitRepository(settings.data_dir, repository)
        git.fetch()

        # 2. 按实际合并产物取提交，避免审查后来移动的目标分支 HEAD。
        merge_sha = mr.get("merge_commit_sha")
        squash_sha = mr.get("squash_commit_sha")
        if merge_sha:
            if not git.is_on_target(merge_sha):
                raise ValueError("合并 SHA 不在目标分支上")
            commits = [merge_sha] if squash_sha else git.merge_commits(merge_sha)
        elif squash_sha:
            if not git.is_on_target(squash_sha):
                raise ValueError("Squash SHA 不在目标分支上")
            commits = [squash_sha]
        else:
            listed = gitlab.list_commits(repository["project_id"], event["mr_iid"])
            if not listed or any(not git.is_on_target(sha) for sha in listed):
                raise ValueError("Fast-forward MR 提交列表与目标分支不符")
            commits = git.order_commits(listed)
            if len(commits) != len(set(listed)):
                raise ValueError("无法完整排序 Fast-forward 提交")

        # 3. 任务和事件末态同事务写入，配置快照保护重新评审语义。
        snapshots: dict[str, tuple[str, str]] = {}
        for sha in commits:
            digest = git.rule_digest(sha)
            snapshots[sha] = (config_hash(store, settings, digest, repository["id"]), digest)
        store.finish_event(event["id"], commits, snapshots, None)
    except Exception as error:
        # 事件处理失败必须落库为待处理状态，不能因网络库的新异常类型丢失队列项。
        LOGGER.warning("合并事件 %s 需要处理：%s", event["id"], error)
        if is_temporary(error):
            store.defer_event(event["id"], str(error))
        else:
            store.finish_event(event["id"], None, {}, str(error)[:500])


def review_job(store: Store, settings: Settings, job: dict[str, Any]) -> None:
    """在隔离目录评审指定 SHA，保存失败诊断后继续处理其他任务。"""

    set_job_stage(store, job["id"], "configuration")
    repository = store.get_repository(job["repository_id"])
    if repository is None:
        store.finish_job(job["id"], "failed", None, None, "仓库配置已删除")
        return
    try:
        snapshot = configuration_snapshot(store, settings, job["rule_digest"], job["repository_id"])
        current_hash = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    except Exception:
        # 凭据不可解时不能退回旧环境变量继续评审，也不把密钥异常持久化。
        store.finish_job(job["id"], "failed", None, None, "评审配置无法读取")
        return
    if current_hash != job["config_hash"]:
        # 入队快照是不可变输入；管理员可用重评审创建当前配置的新任务。
        store.finish_job(job["id"], "failed", None, None, "评审配置已变化，请按当前配置重新评审")
        return
    save_snapshot(store, job["id"], snapshot)
    run_dir = settings.data_dir / "runs" / str(job["id"]) / str(job["attempts"] + 1)
    checkout = run_dir / "checkout"
    git: GitRepository | None = None
    try:
        set_job_stage(store, job["id"], "git")
        if repository["gitlab_token_ciphertext"]:
            repository["gitlab_token"] = SecretBox(settings.master_key).decrypt(
                repository["gitlab_token_ciphertext"]
            )
        git = GitRepository(settings.data_dir, repository)
        git.fetch()
        if cancellation_requested(store, job["id"]):
            raise ReviewCancelled("用户请求停止评审")
        if not git.is_on_target(job["commit_sha"]):
            raise ValueError("待评审提交不再属于目标分支")
        git.checkout(job["commit_sha"], checkout)
        with store.connection() as db:
            db.execute("UPDATE review_jobs SET changed_files=? WHERE id=?",
                       (json.dumps(git.changed_files(job["commit_sha"])), job["id"]))
        model_settings, _ = review_settings(store, settings, job["repository_id"])
        set_job_stage(store, job["id"], "ocr_configuration")
        with cancellation_scope(lambda: cancellation_requested(store, job["id"])):
            status, result = run_review(
                model_settings, checkout, run_dir, job["commit_sha"],
                store.get_review_rule(None), store.get_review_rule(job["repository_id"]),
                lambda stage: set_job_stage(store, job["id"], stage),
            )
            check_cancellation()
        store.finish_job(job["id"], status, str(run_dir / "result.json"), result, None)
    except ReviewCancelled:
        store.finish_job(job["id"], "cancelled", None, None, "用户请求停止评审")
    except Exception as error:
        # 临时失败记录每次尝试并有限退避；提交范围冲突立即终止，避免盲目重试。
        LOGGER.warning("评审任务 %s 失败：%s", job["id"], error)
        if is_temporary(error):
            store.defer_job(job["id"], str(error))
        else:
            store.finish_job(job["id"], "failed", None, None, str(error)[:500])
    finally:
        if git is not None:
            try:
                git.remove_checkout(checkout)
            except (OSError, RuntimeError) as error:
                LOGGER.warning("评审工作目录清理失败：%s", error)


def deliver_notification(store: Store, settings: Settings, delivery: dict[str, Any]) -> None:
    """从已保存结论生成飞书通知，发送失败只重试投递。"""

    repository = store.get_repository(delivery["repository_id"])
    if repository is None:
        store.finish_delivery(delivery["id"], "仓库配置已删除")
        return
    try:
        target = (
            store.get_notification_target(repository["feishu_target_id"])
            if repository["feishu_target_id"]
            else None
        )
        webhook_ciphertext = (
            target["webhook_ciphertext"] if target else repository["feishu_webhook"]
        )
        if not webhook_ciphertext:
            raise ValueError("飞书 Hook 尚未配置")
        box = SecretBox(settings.master_key)
        webhook = box.decrypt(webhook_ciphertext)
        signing_secret = (
            box.decrypt(target["signing_secret_ciphertext"])
            if target and target["signing_secret_ciphertext"]
            else ""
        )
        delivery["detail_url"] = f"{settings.management_base_url}/jobs/{delivery['job_id']}"
        project_url = project_web_url(repository["gitlab_url"], repository["remote_url"])
        if delivery["mr_iid"] > 0:
            delivery["mr_url"] = f"{project_url}/-/merge_requests/{delivery['mr_iid']}"
        delivery["commit_url"] = f"{project_url}/-/commit/{delivery['commit_sha']}"
        if signing_secret:
            send_review(webhook, delivery, signing_secret)
        else:
            send_review(webhook, delivery)
        store.finish_delivery(delivery["id"], None)
    except FeishuDeliveryError as error:
        LOGGER.warning("飞书投递 %s 失败：%s", delivery["id"], error)
        store.finish_delivery(delivery["id"], str(error), retryable=error.retryable)
    except (InvalidToken, ValueError):
        # 密文不可解或已保存结果损坏时，重复发送不会修复输入。
        LOGGER.warning("飞书投递 %s 的本地配置或结果不可用", delivery["id"])
        store.finish_delivery(delivery["id"], "飞书投递配置或结果不可用", retryable=False)
    except Exception as error:
        # 投递失败只改变通知状态，不重新消耗模型额度。
        # HTTP 客户端异常可能包含带令牌的 webhook URL，持久化时仅记录异常类别。
        LOGGER.warning("飞书投递 %s 失败：%s", delivery["id"], type(error).__name__)
        store.finish_delivery(delivery["id"], f"飞书投递失败：{type(error).__name__}")


def preview_rule(store: Store, settings: Settings, preview: dict[str, Any]) -> None:
    """在目标分支的隔离提交上运行 OCR 规则查询，不生成正式评审任务。"""

    repository = store.get_repository(preview["repository_id"])
    if repository is None:
        store.finish_rule_preview(preview["id"], None, None, "仓库配置已删除")
        return
    git: GitRepository | None = None
    commit_sha: str | None = None
    run_dir = settings.data_dir / "rule-previews" / str(preview["id"])
    checkout = run_dir / "checkout"
    try:
        # 1. 固定目标分支提交并建立隔离 worktree，避免预览后来变化的仓库规则。
        if repository["gitlab_token_ciphertext"]:
            repository["gitlab_token"] = SecretBox(settings.master_key).decrypt(
                repository["gitlab_token_ciphertext"]
            )
        git = GitRepository(settings.data_dir, repository)
        git.fetch()
        commit_sha = git.target_head()
        git.checkout(commit_sha, checkout)

        # 2. 使用与正式评审相同的页面规则层级；CLI 只返回命中规则，不访问模型。
        output = check_rule(
            settings, checkout, run_dir, preview["file_path"],
            store.get_review_rule(None), store.get_review_rule(repository["id"]),
        )
        store.finish_rule_preview(preview["id"], commit_sha, output, None)
    except Exception as error:
        # Git stderr 可能包含远端 URL 或访问凭据；数据库只保存异常类别。
        LOGGER.warning("规则预览 %s 失败：%s", preview["id"], type(error).__name__)
        store.finish_rule_preview(
            preview["id"], commit_sha, None, f"规则预览失败（{type(error).__name__}）"
        )
    finally:
        if git is not None:
            try:
                git.remove_checkout(checkout)
            except (OSError, RuntimeError) as error:
                LOGGER.warning("规则预览目录清理失败：%s", type(error).__name__)


def run_once(
    store: Store, settings: Settings, last_repository_id: int | None = None
) -> tuple[bool, int | None]:
    """处理一个工作单元，并记住上次评审的仓库供下次轮转。"""

    if process_backfill(store, settings):
        return True, last_repository_id
    event = store.next_event()
    if event:
        expand_event(store, settings, event)
        return True, last_repository_id
    delivery = store.next_delivery()
    if delivery:
        deliver_notification(store, settings, delivery)
        return True, last_repository_id
    check = store.next_connection_check()
    if check:
        run_connection_check(store, settings, check)
        return True, last_repository_id
    preview = store.next_rule_preview()
    if preview:
        preview_rule(store, settings, preview)
        return True, last_repository_id
    job = store.next_job(last_repository_id)
    if job:
        with artifact_lock(settings.data_dir, job["id"], blocking=True):
            review_job(store, settings, job)
        return True, int(job["repository_id"])
    return False, last_repository_id


def process_backfill(store: Store, settings: Settings) -> bool:
    """先查询 GitLab，再把已核验时间范围的 IID 入队；失败保留诊断供重建申请。"""

    from datetime import datetime

    with store.connection() as db:
        row = db.execute("SELECT * FROM mr_backfills WHERE status='queued' ORDER BY id LIMIT 1")
        request = row.fetchone()
        if request is None:
            return False
        db.execute("UPDATE mr_backfills SET status='running' WHERE id=?", (request["id"],))
        backfill = dict(request)
    try:
        repository = store.get_repository(backfill["repository_id"])
        if repository is None:
            raise ValueError("项目已删除")
        token = SecretBox(settings.master_key).decrypt(repository["gitlab_token_ciphertext"])
        client = GitLabClient(repository["gitlab_url"], token)
        iids = client.list_merged_requests(repository["project_id"],
                                           datetime.fromisoformat(backfill["since"]),
                                           datetime.fromisoformat(backfill["until"]))
        enqueued = sum(store.enqueue_mr(repository["id"], iid) for iid in iids)
        with store.connection() as db:
            db.execute("""UPDATE mr_backfills SET status='done', scanned=?, enqueued=?,
                       finished_at=CURRENT_TIMESTAMP WHERE id=?""",
                       (len(iids), enqueued, backfill["id"]))
    except Exception as error:
        # GitLab 异常可能携带请求地址或代理细节，数据库仅记录异常类别。
        LOGGER.warning("补审申请 %s 失败：%s", backfill["id"], type(error).__name__)
        with store.connection() as db:
            db.execute("""UPDATE mr_backfills SET status='failed', error=?,
                       finished_at=CURRENT_TIMESTAMP WHERE id=?""",
                       (f"补审失败：{type(error).__name__}", backfill["id"]))
    return True


def main() -> None:
    """启动单实例 Worker 并在重启后恢复未确认任务。"""

    logging.basicConfig(level=logging.INFO)
    # 飞书 Webhook 的完整 URL 含令牌，禁止 HTTP 客户端在 INFO 日志中记录请求地址。
    logging.getLogger("httpx").setLevel(logging.WARNING)
    signal.signal(signal.SIGTERM, stop_worker)
    signal.signal(signal.SIGINT, stop_worker)
    settings = load_settings()
    with worker_lock(settings.data_dir):
        store = Store(settings.data_dir / "app.db")
        store.migrate()
        store.recover()
        last_repository_id: int | None = None
        while True:
            handled, last_repository_id = run_once(store, settings, last_repository_id)
            if not handled:
                time.sleep(2)


if __name__ == "__main__":
    main()
