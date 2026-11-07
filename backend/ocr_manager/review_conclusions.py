"""统一只读结论版本、覆盖和发现来源；只查询 SQLite，不提升候选或改写任何业务状态。"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from pydantic import ValidationError

from ocr_manager.review_conclusion_chain import verify_chain
from ocr_manager.review_conclusion_contracts import (
    ConclusionCoverage,
    ConclusionDocument,
    ConclusionFinding,
    ConclusionOverview,
    ConclusionVersion,
    FindingOrigin,
)
from ocr_manager.review_recovery_domain import RecoveryConflict, coverage_items, encoded
from ocr_manager.review_usage_contracts import CumulativeUsage

GROUPS = ("selected", "completed", "reused", "failed", "waived")
# 只对当前 partial 根尝试选择候选；重审排队尚未增加 attempts 的窗口同样失效。
CURRENT_CANDIDATE = """SELECT a.* FROM review_recovery_aggregates a
 JOIN review_jobs j ON j.id=a.job_id AND j.attempts=a.source_attempt
 WHERE j.status='partial' AND j.cancel_requested=0 AND NOT EXISTS (
 SELECT 1 FROM review_recovery_aggregates n WHERE n.job_id=a.job_id
 AND n.source_attempt=a.source_attempt AND n.revision>a.revision)"""


def _version_sql(result: str) -> str:
    counts = ",".join(
        f"'{name}',json_array_length({result},'$.manifest.coverage.{name}')" for name in GROUPS)
    valid = " AND ".join(
        f"json_type({result},'$.manifest.coverage.{name}')='array'" for name in GROUPS)
    return f"""json_extract({result},'$.manifest.terminal_state') AS terminal_state,
        CASE WHEN {valid} THEN json_object({counts}) END AS coverage,
        COALESCE(json_array_length({result},'$.comments'),0) AS finding_count"""


def attach_conclusions(db: sqlite3.Connection, jobs: list[dict[str, Any]]) -> None:
    """调用方保持读事务；列表/详情按 500 条分块，不把完整发现或原始结果加载进列表。"""

    for offset in range(0, len(jobs), 500):
        chunk = jobs[offset:offset + 500]
        marks = ",".join("?" for _ in chunk)
        ids = [job["id"] for job in chunk]
        rows = db.execute(f"""SELECT j.id,j.attempts,j.status,
            {_version_sql('j.result_json')} FROM review_jobs j WHERE j.id IN ({marks})
            AND json_valid(j.result_json)""", ids).fetchall()
        initial = {row["id"]: _header(dict(row), row["attempts"], 0) for row in rows}
        rows = db.execute(f"""WITH candidates AS ({CURRENT_CANDIDATE})
            SELECT job_id,source_attempt,revision,recovery_id,{_version_sql('result_json')}
            FROM candidates WHERE job_id IN ({marks}) AND json_valid(result_json)""",
            ids).fetchall()
        candidates = {row["job_id"]: _header(
            dict(row), row["source_attempt"], row["revision"], row["recovery_id"]) for row in rows}
        for job in chunk:
            job["conclusions"] = ConclusionOverview(
                initial=initial.get(job["id"]), candidate=candidates.get(job["id"])
            ).model_dump()


def _header(row: dict[str, Any], attempt: int, revision: int,
            recovery_id: int | None = None) -> ConclusionVersion:
    return ConclusionVersion(source_attempt=attempt, revision=revision, recovery_id=recovery_id,
        terminal_state=(row["status"] if revision == 0 else row["terminal_state"]),
        coverage=json.loads(row["coverage"]) if row["coverage"] else None,
        finding_count=row["finding_count"])


def candidate_counts(db: sqlite3.Connection) -> dict[str, int]:
    """运维单独统计当前候选状态，不把恢复后的候选伪装成初审成功或成功执行耗时。"""

    rows = db.execute(f"""WITH candidates AS ({CURRENT_CANDIDATE})
        SELECT json_extract(result_json,'$.manifest.terminal_state') AS state,COUNT(*) AS count
        FROM candidates WHERE json_valid(result_json) GROUP BY state""")
    return {row["state"]: row["count"] for row in rows if row["state"] in {"complete", "partial"}}


def _origin(job_id: int, attempt: int, value: dict[str, Any]) -> tuple[str, FindingOrigin]:
    index = value.get("comment_index")
    recovery = value.get("recovery_id")
    if type(index) is not int or index < 0:
        raise RecoveryConflict("finding_origin_invalid")
    if recovery is not None:
        if type(recovery) is not int or recovery <= 0 or "source_attempt" in value:
            raise RecoveryConflict("finding_origin_invalid")
        origin = FindingOrigin(kind="recovery", source_attempt=attempt,
                               recovery_id=recovery, comment_index=index)
        return f"j{job_id}:a{attempt}:r{recovery}:c{index}", origin
    if type(value.get("source_attempt")) is not int or value["source_attempt"] != attempt:
        raise RecoveryConflict("finding_origin_invalid")
    return f"j{job_id}:a{attempt}:c{index}", FindingOrigin(
        kind="attempt", source_attempt=attempt, comment_index=index)


def _findings(db: sqlite3.Connection, job_id: int, attempt: int, revision: int,
              result: dict[str, Any], root: dict[str, Any],
              origins: list[dict[str, Any]]) -> list[ConclusionFinding]:
    comments = result.get("comments")
    if not isinstance(comments, list) or len(comments) > 10000 or len(comments) != len(origins):
        raise RecoveryConflict("finding_origin_invalid")
    # 1. 批量按来源索引取安全评论；独立批次必须属于同一根尝试且已进入目标版本链。
    references: list[dict[str, Any]] = []
    for raw_origin in origins:
        extras = raw_origin.get("also_seen_in", [])
        if not isinstance(extras, list) or len(references) + len(extras) + 1 > 20000:
            raise RecoveryConflict("finding_origin_invalid")
        references.extend([raw_origin, *extras])
    for ref in references:
        _origin(job_id, attempt, ref)
    rows = db.execute("""SELECT b.id,json_extract(ref.value,'$.comment_index') AS idx,
        json_extract(b.result_json,'$.comments[' ||
          json_extract(ref.value,'$.comment_index') || ']') AS comment
        FROM json_each(?) ref JOIN review_recoveries b
          ON b.id=json_extract(ref.value,'$.recovery_id')
        JOIN review_recovery_aggregates a ON a.recovery_id=b.id
        WHERE b.job_id=? AND b.source_attempt=? AND a.source_attempt=?
          AND a.job_id=b.job_id AND a.revision=b.source_revision+1 AND a.revision<=?
          AND b.status IN ('complete','partial') AND json_valid(b.result_json)""",
        (encoded(references), job_id, attempt, attempt, revision))
    recovered = {(row["id"], row["idx"]): json.loads(row["comment"])
                 for row in rows if row["comment"] is not None}
    # 2. 原发现前缀必须保持；去重后的附加来源也验证内容相同，不能靠索引猜测对应。
    original = root.get("comments") or []
    if comments[:len(original)] != original:
        raise RecoveryConflict("finding_origin_invalid")
    findings = []
    known: set[str] = set()
    for comment, raw in zip(comments, origins, strict=True):
        identifier, origin = _origin(job_id, attempt, raw)
        if identifier in known:
            raise RecoveryConflict("finding_origin_invalid")
        known.add(identifier)
        others = []
        for ref in [raw, *raw.get("also_seen_in", [])]:
            _, item = _origin(job_id, attempt, ref)
            if item.kind == "attempt":
                expected = (original[item.comment_index]
                            if item.comment_index < len(original) else None)
            else:
                expected = recovered.get((item.recovery_id, item.comment_index))
            if expected != comment:
                raise RecoveryConflict("finding_origin_invalid")
            if ref is not raw:
                others.append(item)
        findings.append(ConclusionFinding(finding_id=identifier, origin=origin,
            also_seen_in=others, **{key: comment[key] for key in (
                "path", "content", "start_line", "end_line", "severity", "category")
                if key in comment}))
    return findings


def read_conclusion(db: sqlite3.Connection, job_id: int, *,
                    source_attempt: int | None = None,
                    revision: int | None = None) -> ConclusionDocument:
    """调用方持有读事务；默认读当前根尝试最新候选，显式版本可审计历史，绝不改反馈。"""

    from ocr_manager.review_observability import usage_summary

    if source_attempt is not None and revision is None:
        raise RecoveryConflict("explicit_revision_required")
    # 1. 默认选择遵守当前状态；显式历史选择必须同时确认源尝试和版本。
    job = db.execute("SELECT * FROM review_jobs WHERE id=?", (job_id,)).fetchone()
    if job is None:
        raise LookupError("任务不存在")
    number = source_attempt if source_attempt is not None else job["attempts"]
    current = number == job["attempts"] and job["status"] in {
        "complete", "partial", "failed", "skipped"}
    if not current and source_attempt is None:
        raise RecoveryConflict("conclusion_not_available")
    source = db.execute("SELECT * FROM review_attempts WHERE job_id=? AND attempt_number=?",
                        (job_id, number)).fetchone()
    if source is None or not source["result_json"]:
        raise RecoveryConflict("conclusion_not_available")
    aggregate = None
    if revision != 0:
        if (revision is None and current and job["status"] == "partial"
                and not job["cancel_requested"]):
            aggregate = db.execute(f"SELECT * FROM ({CURRENT_CANDIDATE}) WHERE job_id=?",
                                   (job_id,)).fetchone()
        elif revision is not None:
            aggregate = db.execute("""SELECT * FROM review_recovery_aggregates
                WHERE job_id=? AND source_attempt=? AND revision=?""",
                (job_id, number, revision)).fetchone()
            if aggregate is None:
                raise LookupError("结论版本不存在")
    # 2. 只读取已落库投影；来源和覆盖核验失败显式拒绝，不回退成零发现初审。
    try:
        root = json.loads(source["result_json"])
        result = json.loads(aggregate["result_json"]) if aggregate else root
        version = aggregate["revision"] if aggregate else 0
        origins = (json.loads(aggregate["origins_json"]) if aggregate else [
            {"source_attempt": number, "comment_index": index}
            for index, _ in enumerate(root.get("comments") or [])])
        coverage = (result.get("manifest") or {}).get("coverage")
        if aggregate:
            verify_chain(db, job_id, number, version, root, source["config_snapshot"])
            if current and (source["result_json"] != job["result_json"] or
                            source["config_snapshot"] != job["config_snapshot"]):
                raise RecoveryConflict("conclusion_source_invalid")
            batch = db.execute("""SELECT 1 FROM review_recoveries WHERE id=? AND job_id=?
                AND source_attempt=? AND source_revision=? AND status IN ('complete','partial')""",
                (aggregate["recovery_id"], job_id, number, version - 1)).fetchone()
            if batch is None:
                raise RecoveryConflict("conclusion_source_invalid")
            old, new = coverage_items(root), coverage_items(result)
            state = result["manifest"]["terminal_state"]
            if (encoded(old["selected"]) != encoded(new["selected"])
                    or not old["completed"].keys() <= new["completed"].keys()
                    or encoded(old["reused"]) != encoded(new["reused"])
                    or encoded(old["waived"]) != encoded(new["waived"])
                    or state != ("partial" if new["failed"] else "complete")):
                raise RecoveryConflict("conclusion_coverage_invalid")
        findings = _findings(db, job_id, number, version, result, root, origins)
        header = ConclusionVersion(source_attempt=number, revision=version,
            recovery_id=aggregate["recovery_id"] if aggregate else None,
            terminal_state=result["manifest"]["terminal_state"] if aggregate else source["status"],
            coverage=ConclusionCoverage.model_validate(
                {name: len(coverage[name]) for name in GROUPS})
                if isinstance(coverage, dict) and all(
                    isinstance(coverage.get(name), list) for name in GROUPS) else None,
            finding_count=len(findings))
        excluded = (root.get("input_filter") or {}).get("excluded_count")
    except (ValueError, TypeError, KeyError, AttributeError, ValidationError) as error:
        raise RecoveryConflict("conclusion_evidence_invalid") from error
    # 3. 版本费用包含源尝试及到该版本为止的所有批次，包括失败/取消；未知绝不填零。
    executions = [dict(source)]
    if aggregate:
        executions += [dict(row) for row in db.execute("""SELECT status,
            CASE WHEN json_valid(result_json) THEN
              json_object('usage',json_extract(result_json,'$.usage')) END AS result_json,
            CASE WHEN json_valid(config_snapshot) THEN
              json_object('pricing',json_extract(config_snapshot,'$.pricing')) END
              AS config_snapshot
            FROM review_recoveries WHERE job_id=? AND source_attempt=? AND id<=?
            AND started_at IS NOT NULL ORDER BY id""",
            (job_id, number, aggregate["recovery_id"]))]
    try:
        usage = CumulativeUsage.model_validate(
            usage_summary({"attempts": len(executions)}, executions))
    except (ValueError, TypeError, AttributeError) as error:
        raise RecoveryConflict("conclusion_usage_invalid") from error
    return ConclusionDocument(job_id=job_id, version=header,
        role="candidate" if aggregate else "initial", is_current_source=current,
        findings=findings,
        input_filter_excluded_count=excluded if type(excluded) is int and excluded >= 0 else None,
        execution_usage=usage,
        usage_through_recovery_id=header.recovery_id)
