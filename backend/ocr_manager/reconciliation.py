"""对账 SQLite 业务记录与评审工件目录；仅报告差异，不修复业务事实。"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ocr_manager.storage import Store


def reconcile(store: Store, data_dir: Path) -> dict[str, Any]:
    """核对事件、任务、尝试、投递和工件目录，返回无敏感正文的差异清单。"""

    issues: list[dict[str, Any]] = []

    def report(code: str, object_type: str, object_id: str | int, detail: str) -> None:
        """添加稳定的问题码与人工可读说明，不携带异常正文或文件路径。"""

        issues.append({"code": code, "object_type": object_type,
                       "object_id": object_id, "detail": detail})

    with store.connection() as db:
        events = db.execute("""SELECT e.id, e.status,
            (SELECT COUNT(*) FROM review_jobs j WHERE j.event_id=e.id) AS job_count
            FROM merge_events e ORDER BY e.id""").fetchall()
        jobs = db.execute("""SELECT j.id, j.status, j.attempts, j.result_path,
            j.correlation_id,
            (SELECT COUNT(*) FROM review_attempts a WHERE a.job_id=j.id) AS attempt_count,
            (SELECT status FROM review_attempts a WHERE a.job_id=j.id
             ORDER BY attempt_number DESC LIMIT 1) AS attempt_status,
            (SELECT COUNT(*) FROM notification_deliveries d WHERE d.job_id=j.id) AS delivery_count,
            EXISTS (SELECT 1 FROM review_attempts a WHERE a.job_id=j.id
              AND a.correlation_id!=j.correlation_id) AS attempt_correlation_mismatch,
            EXISTS (SELECT 1 FROM notification_deliveries d WHERE d.job_id=j.id
              AND d.correlation_id!=j.correlation_id) AS delivery_correlation_mismatch
            FROM review_jobs j ORDER BY j.id""").fetchall()
        delivery_orphans = db.execute("""SELECT d.id FROM notification_deliveries d
            LEFT JOIN review_jobs j ON j.id=d.job_id WHERE j.id IS NULL""").fetchall()
        delivery_count = int(db.execute(
            "SELECT COUNT(*) FROM notification_deliveries",
        ).fetchone()[0])
        job_ids = {int(row["id"]) for row in db.execute("SELECT id FROM review_jobs")}

    for event in events:
        if event["status"] == "done" and event["job_count"] == 0:
            report("event_without_jobs", "event", event["id"],
                   "事件已处理完成，但没有关联评审任务。")
        if event["job_count"] > 0 and event["status"] != "done":
            report("event_job_status_mismatch", "event", event["id"],
                   "事件状态与已创建的评审任务不一致。")

    terminal = {"complete", "partial", "failed", "skipped", "cancelled"}
    for job in jobs:
        if job["status"] in terminal and job["attempts"] > 0 and job["attempt_count"] == 0:
            report("job_without_attempt", "job", job["id"],
                   "终态任务没有对应的评审尝试记录。")
        if (job["status"] in terminal and job["attempt_status"]
                and job["attempt_status"] != job["status"]):
            report("job_attempt_status_mismatch", "job", job["id"],
                   "任务末态与最近一次尝试的状态不一致。")
        if job["status"] in {"complete", "partial", "failed", "skipped"} \
                and job["delivery_count"] == 0:
            report("job_without_delivery", "job", job["id"],
                   "已结束的评审任务没有通知投递记录。")
        if job["attempt_correlation_mismatch"]:
            report("attempt_correlation_mismatch", "job", job["id"],
                   "评审尝试与任务的关联标识不一致。")
        if job["delivery_correlation_mismatch"]:
            report("delivery_correlation_mismatch", "job", job["id"],
                   "通知投递与任务的关联标识不一致。")
        if job["result_path"]:
            artifact = Path(job["result_path"])
            run_root = data_dir / "runs" / str(job["id"])
            try:
                resolved_artifact = artifact.resolve()
                resolved_root = run_root.resolve()
                within_run = resolved_root in resolved_artifact.parents
                if (data_dir.joinpath("runs").is_symlink() or run_root.is_symlink()
                        or artifact.is_symlink() or not within_run):
                    report("result_artifact_outside_run", "job", job["id"],
                           "结果工件路径超出任务专属目录。")
                elif not artifact.is_file():
                    report("result_artifact_missing", "job", job["id"],
                           "数据库记录的结果工件不存在。")
            except (OSError, RuntimeError):
                report("result_artifact_missing", "job", job["id"],
                       "数据库记录的结果工件无法访问。")

    for delivery in delivery_orphans:
        report("delivery_without_job", "delivery", delivery["id"],
               "通知投递没有对应的评审任务。")

    runs = data_dir / "runs"
    artifact_count = 0
    orphan_artifact_count = 0
    if runs.is_dir() and not runs.is_symlink():
        for path in runs.iterdir():
            if not path.is_dir() or path.is_symlink() or not path.name.isdecimal():
                continue
            artifact_count += 1
            job_id = int(path.name)
            if job_id not in job_ids:
                orphan_artifact_count += 1
                report("artifact_without_job", "artifact", job_id,
                       "工件目录没有对应的评审任务记录。")

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "issue_count": len(issues),
        "checked": {
            "events": len(events), "jobs": len(jobs), "deliveries": delivery_count,
            "artifact_directories": artifact_count,
        },
        "orphan_artifact_directories": orphan_artifact_count,
        "issues": issues,
    }
