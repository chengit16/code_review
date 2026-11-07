"""从初审逐版重放补审覆盖及来源，拒绝损坏中间版本重新进入有效结论；仅查询 SQLite。"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from ocr_manager.review_recovery_domain import RecoveryConflict, digest, encoded, merge_candidate


def verify_chain(db: sqlite3.Connection, job_id: int, attempt: int, revision: int,
                 root: dict[str, Any], snapshot: str | None) -> None:
    """校验完整、连续的证据链；来源失败或覆盖增量无法由实际批次证明即默认拒绝。"""

    rows = db.execute("""SELECT b.*,a.revision,a.result_json AS aggregate_result,
        a.origins_json FROM review_recovery_aggregates a JOIN review_recoveries b
        ON b.id=a.recovery_id AND b.job_id=a.job_id AND b.source_attempt=a.source_attempt
        WHERE a.job_id=? AND a.source_attempt=? AND a.revision<=? ORDER BY a.revision""",
        (job_id, attempt, revision)).fetchall()
    if not 0 < revision <= 100 or len(rows) != revision:
        raise RecoveryConflict('conclusion_chain_invalid')
    result = root
    origins = [{'source_attempt': attempt, 'comment_index': index}
               for index, _ in enumerate(root.get('comments') or [])]
    # 逐版比较冻结输入、批准范围和真实增量；仅根覆盖单调性无法证明中间批次真的完成。
    for number, row in enumerate(rows, 1):
        if (row['revision'] != number or row['source_revision'] != number - 1 or
                row['status'] not in {'complete', 'partial'} or
                row['config_snapshot'] != snapshot or row['source_digest'] != digest(result) or
                encoded(json.loads(row['source_result_json'])) != encoded(result)):
            raise RecoveryConflict('conclusion_chain_invalid')
        child = json.loads(row['result_json'])
        result, origins = merge_candidate(result, child, json.loads(row['approved_json']),
                                          row['id'], origins)
        if (result['manifest']['terminal_state'] != row['status'] or
                encoded(result) != encoded(json.loads(row['aggregate_result'])) or
                encoded(origins) != encoded(json.loads(row['origins_json']))):
            raise RecoveryConflict('conclusion_chain_invalid')
