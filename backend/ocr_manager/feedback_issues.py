"""在反馈写入事务内同步关联问题；不调用外部服务，不覆盖其他入口的关闭决定。"""

from __future__ import annotations

import sqlite3


def sync_feedback_issue(
    db: sqlite3.Connection, job_id: int, attempt_number: int, comment_index: int,
    verdict: str | None, actor: str,
) -> None:
    """仅处理当前尝试关联的问题；重复反馈幂等，撤销只重开本卡片关闭的问题。"""

    # 1. 只使用当前尝试的出现记录，重审后的同一索引不会修改旧问题。
    issue = db.execute("""SELECT i.id,i.status FROM review_issue_occurrences o
        JOIN review_issues i ON i.id=o.issue_id
        WHERE o.job_id=? AND o.attempt_number=? AND o.comment_index=?""",
        (job_id, attempt_number, comment_index)).fetchone()
    if issue is None or issue["status"] == "merged":
        return
    # 2. 来源说明用于识别本卡片的关闭决定；调整文案时须兼容已有审计记录。
    source = f"任务 #{job_id} 第 {attempt_number} 次发现 {comment_index + 1}"
    notes = {
        "false_positive": f"{source}：标记为误报，同步忽略",
        "fixed": f"{source}：标记为已修复，同步关闭",
    }
    latest = db.execute("""SELECT note FROM review_issue_events
        WHERE issue_id=? ORDER BY id DESC LIMIT 1""", (issue["id"],)).fetchone()
    owns_closure = latest is not None and latest["note"] in notes.values()
    # 仅开放问题或本卡片拥有的关闭记录可被改写，避免旧反馈覆盖其他人的决定。
    if issue["status"] != "open" and not owns_closure:
        return
    target = {"false_positive": "ignored", "fixed": "fixed"}.get(verdict or "", "open")
    if issue["status"] == target:
        return
    # 3. 复用调用方写事务，问题、操作者审计与反馈必须同时成功或回滚。
    note = notes.get(verdict or "", f"{source}：撤销处理，恢复待处理")
    db.execute("""UPDATE review_issues SET status=?,
        closed_at=CASE WHEN ?='open' THEN NULL ELSE CURRENT_TIMESTAMP END WHERE id=?""",
        (target, target, issue["id"]))
    db.execute("""INSERT INTO review_issue_events
        (issue_id,old_status,new_status,actor,note) VALUES(?,?,?,?,?)""",
        (issue["id"], issue["status"], target, actor, note))
