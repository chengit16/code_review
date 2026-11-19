"""维护合并前版本与统一任务的原子关联；旧表仅作兼容投影，不再独立调度。"""

from __future__ import annotations

import json
import sqlite3
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ocr_manager.storage import Store


def supersede(
    db: sqlite3.Connection,
    repository_id: int,
    mr_iid: int,
    through_id: int = 9223372036854775807,
) -> None:
    """撤销旧版本有效性与未投递通知；运行中通过取消栅栏停止，保留真实历史结果。"""

    db.execute(
        """UPDATE review_jobs SET superseded=1,cancel_requested=1,
        status=CASE WHEN status='queued' THEN 'cancelled' ELSE status END,
        finished_at=CASE WHEN status='queued' THEN CURRENT_TIMESTAMP ELSE finished_at END
        WHERE repository_id=? AND mr_iid=? AND source='premerge' AND superseded=0
        AND id<=?""",
        (repository_id, mr_iid, through_id),
    )
    db.execute(
        """UPDATE notification_deliveries SET status='failed',error='版本已被替代，停止投递'
        WHERE status='pending' AND job_id IN
        (SELECT id FROM review_jobs WHERE repository_id=? AND mr_iid=?
         AND source='premerge' AND superseded=1)""",
        (repository_id, mr_iid),
    )

    db.execute(
        "UPDATE gitlab_publications SET status='skipped',error='版本已被替代' "
        "WHERE status='pending' AND job_id IN (SELECT id FROM review_jobs "
        "WHERE repository_id=? AND mr_iid=? AND superseded=1)",
        (repository_id, mr_iid),
    )
    db.execute(
        "UPDATE review_recoveries SET cancel_requested=1,"
        "status=CASE WHEN status='queued' THEN 'cancelled' ELSE status END "
        "WHERE job_id IN (SELECT id FROM review_jobs WHERE repository_id=? "
        "AND mr_iid=? AND superseded=1) AND status IN ('queued','running')",
        (repository_id, mr_iid),
    )


def attach_premerge(db: sqlite3.Connection, legacy_id: int) -> int:
    """旧接口写入后在同一事务建立唯一统一身份；不产生模型或通知副作用。"""

    existing = db.execute(
        "SELECT id FROM review_jobs WHERE legacy_premerge_id=?", (legacy_id,)
    ).fetchone()
    if existing:
        return int(existing[0])
    row = db.execute(
        "SELECT p.* FROM premerge_reviews p JOIN repositories r "
        "ON r.id=p.repository_id WHERE p.id=?",
        (legacy_id,),
    ).fetchone()
    if row is None:
        raise ValueError("合并前版本不存在")
    event = db.execute(
        """INSERT INTO merge_events(repository_id,mr_iid,delivery_id,status,
        source,correlation_id,target_branch) VALUES(?,?,?,'done','premerge',?,?)""",
        (
            row["repository_id"],
            -3000000000000000000 - legacy_id,
            f"premerge-{legacy_id}",
            f"premerge-{legacy_id}",
            row["target_branch"],
        ),
    ).lastrowid
    identity = db.execute("INSERT INTO job_identity DEFAULT VALUES").lastrowid
    db.execute(
        """INSERT INTO review_jobs(id,repository_id,event_id,mr_iid,commit_sha,ordinal,
        config_hash,target_branch,source,legacy_premerge_id,context_hint,execution_policy,
        correlation_id,mr_state,notification_min_severity)
        VALUES(?,?,?,?,?,0,?,?,'premerge',?,?,?,?,'unknown',
        COALESCE((SELECT minimum_severity FROM project_policies WHERE repository_id=?),
        'medium'))""",
        (
            identity,
            row["repository_id"],
            event,
            row["mr_iid"],
            row["head_sha"],
            f"premerge-{legacy_id}",
            row["target_branch"] or db.execute("SELECT target_branch FROM repositories WHERE id=?",
                (row["repository_id"],)).fetchone()[0],
            legacy_id,
            row["context_hint"],
            row["execution_policy"],
            f"premerge-{legacy_id}",
            row["repository_id"],
        ),
    )
    db.execute(
        "INSERT INTO review_event_links(event_id,job_id,relation) VALUES(?,?,'created')",
        (event, identity),
    )
    return int(identity or 0)


def link_event(store: Store, event_id: int, job_ids: list[int], evidence: dict[str, Any]) -> None:
    """关联与事件完成在同一短事务；被删除的任务留待核实，不伪造完成事实。"""

    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        for job_id in job_ids:
            if not db.execute("SELECT 1 FROM review_jobs WHERE id=?", (job_id,)).fetchone():
                raise ValueError("对应版本任务已删除，请核实评审范围")
            db.execute(
                """INSERT OR IGNORE INTO review_event_links
                (event_id,job_id,relation,evidence_json) VALUES(?,?,'reused',?)""",
                (event_id, job_id, json.dumps(evidence, ensure_ascii=False)),
            )
        db.execute("UPDATE merge_events SET status='done',error=NULL WHERE id=?", (event_id,))


def event_links(store: Store, job_id: int) -> list[dict[str, Any]]:
    """仅投影可信事件身份与范围，不返回原始 webhook 或外部响应。"""

    with store.connection() as db:
        return [
            dict(row)
            for row in db.execute(
                """SELECT e.id,e.source,e.mr_iid,e.merge_sha,
            e.squash_sha,e.created_at,l.relation,l.evidence_json FROM review_event_links l
            JOIN merge_events e ON e.id=l.event_id WHERE l.job_id=? ORDER BY e.id""",
                (job_id,),
            )
        ]
