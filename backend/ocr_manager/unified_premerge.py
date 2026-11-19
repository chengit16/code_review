"""普通任务执行链中的 MR 版本校验；冻结范围与背景，不持有外部调用事务。"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from ocr_manager.gitlab import GitLabClient
from ocr_manager.premerge import SHA, description_digest, enqueue_premerge
from ocr_manager.premerge_context import build_premerge_context

if TYPE_CHECKING:
    from ocr_manager.git_repo import GitRepository
    from ocr_manager.storage import Store


def verify_version(
    store: Store, repository: dict[str, Any], job: dict[str, Any], client: GitLabClient
) -> dict[str, Any]:
    """正常合并不撤销同版本；关闭、改头或描述变化立即失效并补入已核验的新版本。"""

    mr = client.get_merge_request(repository["project_id"], job["mr_iid"])
    with store.connection() as db:
        setting = db.execute(
            "SELECT * FROM premerge_settings WHERE repository_id=?", (repository["id"],)
        ).fetchone()
    valid = (
        mr.get("state") in {"opened", "merged"}
        and mr.get("sha") == job["commit_sha"]
        and mr.get("target_branch") == job["target_branch"]
        and mr.get("target_project_id") == repository["project_id"]
    )
    hint = description_digest(mr.get("description"))
    if setting and setting["include_description"] and job.get("context_hint") is not None:
        valid = valid and job["context_hint"] == hint
    if not valid:
        from ocr_manager.unified_reviews import supersede

        with store.connection() as db:
            supersede(db, repository["id"], job["mr_iid"], through_id=job["id"])
        head = mr.get("sha")
        if mr.get("state") == "opened" and isinstance(head, str) and SHA.fullmatch(head):
            enqueue_premerge(
                store,
                repository["id"],
                job["mr_iid"],
                head,
                hint if setting and setting["include_description"] else None,
                target_branch=mr.get("target_branch"),
            )
        raise ValueError("MR 输入已变化，旧版本已失效")
    with store.connection() as db:
        db.execute("UPDATE review_jobs SET mr_state=? WHERE id=?", (mr["state"], job["id"]))
    return mr


def prepare(
    store: Store,
    repository: dict[str, Any],
    job: dict[str, Any],
    git: GitRepository,
    client: GitLabClient,
) -> tuple[str, str | None]:
    """核验 diff refs 并冻结固定范围；重试不得静默移动原基准。"""

    mr = verify_version(store, repository, job, client)
    refs = mr.get("diff_refs") or {}
    base = job.get("base_sha") or refs.get("base_sha")
    if (
        not isinstance(base, str)
        or not SHA.fullmatch(base)
        or refs.get("head_sha") != job["commit_sha"]
    ):
        raise RuntimeError("GitLab 尚未生成可核验的 MR diff 基准")
    git.fetch_mr_head(job["mr_iid"], job["commit_sha"])
    if not git.is_range_base(base, job["commit_sha"]):
        raise ValueError("MR diff 基准与代码版本不符")
    with store.connection() as db:
        setting = db.execute(
            "SELECT * FROM premerge_settings WHERE repository_id=?", (repository["id"],)
        ).fetchone()
    if not setting:
        raise ValueError("合并前评审配置不存在")
    background, context = build_premerge_context(
        git,
        job["commit_sha"],
        mr,
        bool(setting["include_description"]),
        json.loads(setting["context_paths"]),
    )
    with store.connection() as db:
        db.execute(
            "UPDATE review_jobs SET base_sha=?,context_json=? WHERE id=?",
            (base, json.dumps(context, ensure_ascii=False) if context else None, job["id"]),
        )
    return base, background
