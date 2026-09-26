"""保留逐次评审的安全结果与配置事实；不读取原始 thinking 或执行外部调用。"""

from __future__ import annotations

import json
from typing import Any

from ocr_manager.storage import Store


def save_snapshot(store: Store, job_id: int, snapshot: dict[str, Any]) -> None:
    """只保存无凭据的配置，在开始评审前写入以覆盖失败与中断场景。"""

    with store.connection() as db:
        db.execute("UPDATE review_jobs SET config_snapshot=? WHERE id=? AND status='running'",
                   (json.dumps(snapshot, ensure_ascii=False), job_id))


def attempt_job(job: dict[str, Any], number: int) -> dict[str, Any]:
    """将指定历史尝试投影为报告输入；历史未保存结果时明确返回无结果。"""

    attempt = next((item for item in job["attempt_history"]
                    if item["attempt_number"] == number), None)
    if attempt is None:
        raise ValueError("尝试不存在")
    return job | {"result": json.loads(attempt["result_json"])
                  if attempt.get("result_json") else None,
                  "status": attempt["status"], "error": attempt["error"],
                  "failure_stage": attempt.get("failure_stage"),
                  "config_snapshot": json.loads(attempt["config_snapshot"])
                  if attempt.get("config_snapshot") else None,
                  "changed_files": attempt.get("changed_files"),
                  "finished_at": attempt["finished_at"], "delivery": None,
                  "attempt_history": [attempt]}


def compare_results(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """同提交的发现按文件、行号、级别和内容匹配；不宣称消失的问题已修复。"""

    def findings(job: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {json.dumps(item, sort_keys=True, ensure_ascii=False): item
                for item in (job.get("result") or {}).get("comments", [])}

    old, new = findings(before), findings(after)
    return {"added": [new[key] for key in new.keys() - old.keys()],
            "removed": [old[key] for key in old.keys() - new.keys()],
            "unchanged_count": len(old.keys() & new.keys()),
            "before_status": before["status"], "after_status": after["status"]}
