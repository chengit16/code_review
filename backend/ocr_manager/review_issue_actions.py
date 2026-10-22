"""统一单项与批量问题处理事务；仅修改 SQLite 状态及审计，不触发外部调用。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from ocr_manager.storage import Store

IssueStatus = Literal["open", "fixed", "ignored"]


def update_review_issues(
    store: Store, targets: list[tuple[int, IssueStatus | None]],
    status: IssueStatus, actor: str, note: str | None,
) -> dict[str, int]:
    """在写锁内先校验全部目标再更新；状态冲突整批回滚，重复提交不重复审计。"""

    ids = [issue_id for issue_id, _ in targets]
    if not 1 <= len(ids) <= 100 or len(set(ids)) != len(ids):
        raise ValueError("每次请选择 1 至 100 个不重复的问题")
    with store.connection() as db:
        # 1. 写锁内读取全部事实，避免校验与更新之间被其他管理员或卡片修改。
        db.execute("BEGIN IMMEDIATE")
        placeholders = ",".join("?" for _ in ids)
        rows = db.execute(f"SELECT id,status FROM review_issues WHERE id IN ({placeholders})",
                          ids).fetchall()
        current = {row["id"]: row["status"] for row in rows}
        if len(current) != len(ids):
            raise LookupError("部分问题不存在，请刷新列表后重新选择")
        for issue_id, expected in targets:
            if current[issue_id] == "merged":
                raise ValueError(f"问题 #{issue_id} 已合并，不能修改状态，请刷新后重新选择")
            if expected is not None and current[issue_id] not in (expected, status):
                raise ValueError(f"问题 #{issue_id} 状态已变化，本次未更新，请刷新后重新选择")

        # 2. 全部校验通过后写入状态和逐项审计；已是目标状态的项保持幂等。
        updated = 0
        for issue_id in ids:
            if current[issue_id] == status:
                continue
            db.execute("""UPDATE review_issues SET status=?,
                closed_at=CASE WHEN ?='open' THEN NULL ELSE CURRENT_TIMESTAMP END WHERE id=?""",
                (status, status, issue_id))
            db.execute("""INSERT INTO review_issue_events
                (issue_id,old_status,new_status,actor,note) VALUES(?,?,?,?,?)""",
                (issue_id, current[issue_id], status, actor, note))
            updated += 1
    return {"updated": updated, "unchanged": len(ids) - updated}
