"""生成仅含状态、时间与关联标识的诊断数据，不导出凭据或评审内容。"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ocr_manager.reconciliation import reconcile
from ocr_manager.storage import SCHEMA_VERSION, Store


def create_diagnostic_bundle(store: Store, data_dir: Path) -> dict[str, Any]:
    """导出受限运行元数据与对账结果；不读取原始 OCR、仓库或配置正文。"""

    with store.connection() as db:
        events = [dict(row) for row in db.execute("""SELECT id, correlation_id, status,
            attempts, created_at FROM merge_events ORDER BY id DESC LIMIT 200""")]
        jobs = [dict(row) for row in db.execute("""SELECT id, event_id, correlation_id,
            status, attempts, created_at, finished_at FROM review_jobs
            ORDER BY id DESC LIMIT 500""")]
        attempts = [dict(row) for row in db.execute("""SELECT id, job_id, attempt_number,
            correlation_id, status, failure_stage, finished_at,
            CASE WHEN error IS NULL THEN 0 ELSE 1 END AS has_error
            FROM review_attempts ORDER BY id DESC LIMIT 1000""")]
        deliveries = [dict(row) for row in db.execute("""SELECT id, job_id,
            correlation_id, status, attempts, sent_at,
            CASE WHEN error IS NULL THEN 0 ELSE 1 END AS has_error
            FROM notification_deliveries ORDER BY id DESC LIMIT 500""")]
        management_requests = [dict(row) for row in db.execute("""SELECT id, correlation_id,
            action, object_type, object_id, outcome, created_at
            FROM audit_log ORDER BY id DESC LIMIT 500""")]

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "schema_version": SCHEMA_VERSION,
        "limits": {
            "events": 200, "jobs": 500, "attempts": 1000,
            "deliveries": 500, "management_requests": 500,
        },
        "events": events,
        "jobs": jobs,
        "attempts": attempts,
        "deliveries": deliveries,
        "management_requests": management_requests,
        "reconciliation": reconcile(store, data_dir),
    }
