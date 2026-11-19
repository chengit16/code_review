"""以 GitLab 身份和精确 Git 差异证明复用；未审范围保留独立任务，不猜测覆盖。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ocr_manager.unified_reviews import link_event

if TYPE_CHECKING:
    from ocr_manager.git_repo import GitRepository
    from ocr_manager.gitlab import GitLabClient
    from ocr_manager.storage import Store


def merged_range(
    store: Store,
    repository: dict[str, Any],
    mr: dict[str, Any],
    git: GitRepository,
    client: GitLabClient,
) -> tuple[str, str, int] | None:
    """只有同项目、目标分支、版本且完整差异一致时复用任务，失败任务也保留原状态。"""

    if (
        mr.get("state") != "merged"
        or mr.get("target_project_id") != repository["project_id"]
        or mr.get("target_branch") != repository["target_branch"]
    ):
        return None
    with store.connection() as db:
        job = db.execute(
            """SELECT * FROM review_jobs WHERE repository_id=? AND mr_iid=?
            AND commit_sha=? AND target_branch=? AND source='premerge' AND superseded=0
            ORDER BY id DESC LIMIT 1""",
            (repository["id"], mr["iid"], mr.get("sha"), repository["target_branch"]),
        ).fetchone()
    if job is None:
        with store.connection() as db:
            removed = db.execute(
                "SELECT 1 FROM deleted_premerge_versions WHERE repository_id=? "
                "AND mr_iid=? AND head_sha=? AND target_branch=?",
                (repository["id"], mr["iid"], mr.get("sha"), repository["target_branch"]),
            ).fetchone()
        if removed:
            raise ValueError("对应版本任务已删除，请核实后决定是否完整重审")
        return None
    refs = mr.get("diff_refs") or {}
    base = job["base_sha"] or refs.get("base_sha")
    if not base or refs.get("head_sha") != job["commit_sha"]:
        raise RuntimeError("对应合并前版本的 diff 基准尚不可核验")
    git.fetch_mr_head(mr["iid"], job["commit_sha"])
    after = mr.get("merge_commit_sha") or mr.get("squash_commit_sha")
    if after:
        before = git.first_parent(after)
    else:
        commits = client.list_commits(repository["project_id"], mr["iid"])
        ordered = git.order_commits(commits)
        if not ordered:
            raise RuntimeError("Fast-forward 提交范围尚不可核验")
        after, before = ordered[-1], git.first_parent(ordered[0])
    if not git.is_on_target(after) or not git.is_range_base(before, after):
        raise ValueError("合并产物不再属于目标分支")
    if git.range_signature(base, job["commit_sha"]) != git.range_signature(before, after):
        raise ValueError("合并差异与预审版本不一致，请核实冲突处理或 rebase 后范围")
    with store.connection() as db:
        db.execute(
            """INSERT OR REPLACE INTO merged_review_ranges
            (repository_id,mr_iid,head_sha,before_sha,after_sha,job_id,target_branch)
                VALUES(?,?,?,?,?,?,?)""",
            (
                repository["id"],
                mr["iid"],
                job["commit_sha"],
                before,
                after,
                job["id"],
                repository["target_branch"],
            ),
        )
        db.execute(
            "UPDATE review_jobs SET mr_state='merged',base_sha=COALESCE(base_sha,?) WHERE id=?",
            (base, job["id"]),
        )
    return before, after, int(job["id"])


def reuse_merge(
    store: Store,
    event: dict[str, Any],
    repository: dict[str, Any],
    mr: dict[str, Any],
    git: GitRepository,
    client: GitLabClient,
) -> bool:
    """关联 MR 合并事件；同版本已存在则不再展开普通提交任务。"""

    mr = {**mr, "iid": event["mr_iid"]}
    covered = merged_range(store, repository, mr, git, client)
    if covered is None:
        return False
    before, after, job_id = covered
    link_event(
        store, event["id"], [job_id], {"before": before, "after": after, "proof": "exact_diff"}
    )
    return True


def push_ranges(
    store: Store,
    event: dict[str, Any],
    repository: dict[str, Any],
    git: GitRepository,
    client: GitLabClient,
    before: str,
    after: str,
) -> tuple[list[tuple[str, str]], list[int]]:
    """按第一父链连续段拆分；关联查询暂不可用则保留事件重试，不能退化为重复全审。"""

    with store.connection() as db:
        known = db.execute(
            "SELECT before_sha,after_sha,job_id FROM merged_review_ranges "
            "WHERE repository_id=? AND target_branch=?",
            (repository["id"], repository["target_branch"]),
        ).fetchall()
        exists = db.execute(
            "SELECT 1 FROM review_jobs WHERE repository_id=? AND source='premerge'",
            (repository["id"],),
        ).fetchone()
    with store.connection() as db:
        tombstones = db.execute(
            "SELECT 1 FROM deleted_premerge_versions WHERE repository_id=? LIMIT 1",
            (repository["id"],),
        ).fetchone()
    if not exists and not known and not tombstones:
        return [(before, after)], []
    chain = [before, *git.first_parent_range(before, after)]
    coverage: dict[str, tuple[str, int]] = {}
    for row in known:
        if row["after_sha"] not in chain[1:]:
            continue
        if row["job_id"] is None:
            raise ValueError("对应已审任务已删除，请核实后决定是否重新评审")
        coverage[row["after_sha"]] = (row["before_sha"], row["job_id"])
    # 合并和 Push 可乱序：先复核尚无持久化范围的已知版本，不依赖异步提交索引。
    with store.connection() as db:
        candidates = db.execute(
            "SELECT DISTINCT j.mr_iid FROM review_jobs j WHERE j.repository_id=? "
            "AND j.source='premerge' AND j.target_branch=? AND j.superseded=0 AND NOT EXISTS "
            "(SELECT 1 FROM merged_review_ranges m WHERE m.job_id=j.id) "
            "ORDER BY j.id DESC LIMIT 101",
            (repository["id"], repository["target_branch"]),
        ).fetchall()
    if len(candidates) > 100:
        raise ValueError("待核验 MR 超过上限，请先处理历史版本")
    checked: set[int] = set()
    for row in candidates:
        checked.add(row["mr_iid"])
        mr = client.get_merge_request(repository["project_id"], row["mr_iid"])
        tip = mr.get("merge_commit_sha") or mr.get("squash_commit_sha") or mr.get("sha")
        if mr.get("state") != "merged" or tip not in chain[1:]:
            continue
        covered = merged_range(store, repository, {**mr, "iid": row["mr_iid"]}, git, client)
        if covered:
            start, end, job_id = covered
            coverage[end] = (start, job_id)
    # 未索引的合并产物继续通过提交关联核验，网络失败不会退回全量重复审查。
    for sha in chain[1:]:
        if sha in coverage:
            continue
        for iid in client.commit_merge_requests(repository["project_id"], sha):
            if iid in checked:
                continue
            checked.add(iid)
            mr = client.get_merge_request(repository["project_id"], iid)
            covered = merged_range(store, repository, {**mr, "iid": iid}, git, client)
            if covered:
                start, end, job_id = covered
                coverage[end] = (start, job_id)
    intervals: list[tuple[int, int, int]] = []
    for end, (start, job_id) in coverage.items():
        if end not in chain:
            continue
        if start not in chain:
            raise ValueError("Push 与已审合并范围交错，请核实后选择完整重审")
        left, right = chain.index(start), chain.index(end)
        intervals.append((left, right, job_id))
    intervals.sort()
    cursor = 0
    ranges: list[tuple[str, str]] = []
    reused: list[int] = []
    for left, right, job_id in intervals:
        if left < cursor or right <= left:
            raise ValueError("已审范围交错，需人工核实")
        if left > cursor:
            ranges.append((chain[cursor], chain[left]))
        cursor = right
        reused.append(job_id)
    if cursor < len(chain) - 1:
        ranges.append((chain[cursor], chain[-1]))
    return ranges, reused


def force_event(store: Store, event_id: int) -> bool:
    """管理员显式授权完整重审；仅允许待核实事件，保留会重复覆盖部分代码的审计事实。"""

    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        cursor = db.execute(
            "UPDATE merge_events SET status='queued',attempts=0,error=NULL,"
            "next_run_at=CURRENT_TIMESTAMP,force_full_review=1 "
            "WHERE id=? AND status='needs_attention' AND source!='premerge'",
            (event_id,),
        )
        return cursor.rowcount == 1
