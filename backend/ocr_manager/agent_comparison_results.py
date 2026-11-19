"""投影固定的双路结果和证据；仅查 SQLite，省略端点、配置正文和原始模型响应。"""

from __future__ import annotations

import json
import re
import sqlite3
from collections import defaultdict

from pydantic import BaseModel, TypeAdapter

from ocr_manager.agent_comparison_contracts import (
    AgentComparisonResult,
    AgentCoverageFile,
    ComparisonFinding,
    ComparisonUsage,
    FindingMatch,
    OcrComparisonResult,
)
from ocr_manager.review_conclusions import read_conclusion
from ocr_manager.review_prototype.graph import AgentProgress
from ocr_manager.review_prototype.result import ReviewResult

RESULT = TypeAdapter(ReviewResult)
PROGRESS = TypeAdapter(AgentProgress)


class ManifestHunk(BaseModel):
    """冻结差异块的安全清单，不含提交正文。"""

    id: int
    path: str
    records: int


class InputManifest(BaseModel):
    """展示实际记录数及因无文本差异被排除的文件。"""

    hunks: list[ManifestHunk]
    excluded_paths: list[str]


def _model(snapshot: str | None) -> str | None:
    data = json.loads(snapshot or "{}")
    value = data.get("model") if isinstance(data, dict) else None
    if isinstance(value, str) and re.fullmatch(r"[a-zA-Z0-9_.:/-]{1,160}", value):
        return value
    return None


def ocr_result(db: sqlite3.Connection, row: sqlite3.Row) -> OcrComparisonResult:
    """只读取本轮引用的原始 OCR 尝试；旧失败记录可能没有结果。"""

    source = db.execute("SELECT result_json,config_snapshot FROM review_attempts WHERE id=?",
                        (row["source_attempt_id"],)).fetchone()
    usage = ComparisonUsage(model=_model(source["config_snapshot"]))
    if not source["result_json"]:
        return OcrComparisonResult(status=row["ocr_status"], coverage=None,
                                   findings=[], usage=usage)
    document = read_conclusion(db, row["job_id"], source_attempt=row["ocr_attempt"], revision=0)
    usage.input_tokens = (document.execution_usage.known_tokens or {}).get("input_tokens")
    usage.output_tokens = (document.execution_usage.known_tokens or {}).get("output_tokens")
    costs = document.execution_usage.known_costs
    if document.execution_usage.cost_complete and len(costs) == 1:
        usage.cost, usage.currency = costs[0].total, costs[0].currency
    return OcrComparisonResult(status=row["ocr_status"], coverage=document.version.coverage,
        usage=usage, findings=[ComparisonFinding(
            id=f"ocr:{item.origin.comment_index}", path=item.path,
            line=item.start_line if item.start_line and item.start_line > 0 else None,
            title=item.category or "初审发现", content=item.content,
        ) for item in document.findings])


def agent_result(db: sqlite3.Connection, row: sqlite3.Row) -> AgentComparisonResult:
    """终态发现使用稳定索引，正在处理的比较仅展示已保存覆盖。"""

    result = RESULT.validate_json(row["result_json"]) if row["result_json"] else None
    progress = PROGRESS.validate_json(row["progress_json"]) if row["progress_json"] else None
    manifest = InputManifest.model_validate_json(row["input_manifest_json"]) if row[
        "input_manifest_json"] else None
    coverage = result.coverage if result else progress.coverage if progress else ()
    by_hunk = {item.hunk_id: item for item in coverage}
    by_file: dict[str, AgentCoverageFile] = {}
    if manifest:
        for item in manifest.hunks:
            file = by_file.setdefault(item.path, AgentCoverageFile(path=item.path))
            file.total += item.records
            records = by_hunk.get(item.id)
            if records:
                file.delivered += records.delivered_end
                file.reviewed += records.reviewed_end
    # 汇总冻结版本的账目；未知调用没有零值回执，也不估算成本。
    calls = db.execute("""SELECT SUM(prompt_tokens) AS input_tokens,
        SUM(completion_tokens) AS output_tokens,COUNT(*) FILTER(WHERE status='unknown') AS unknown,
        CASE WHEN COUNT(DISTINCT provider_model)=1 THEN MIN(provider_model) END AS model
        FROM agent_review_calls WHERE agent_review_id=?""", (row["id"],)).fetchone()
    return AgentComparisonResult(reason=row["reason"],
        files=list(by_file.values()) if manifest else None,
        excluded_paths=manifest.excluded_paths if manifest else [],
        findings=[ComparisonFinding(id=f"agent:{index}", path=item.evidence.path,
            line=item.evidence.line, side=item.evidence.side, title=item.title,
            content=item.trigger,
            impact=item.impact, excerpt=item.evidence.excerpt[:800],
        ) for index, item in enumerate(result.findings if result else ())],
        usage=ComparisonUsage(model=calls["model"] or _model(row["model_snapshot"]),
            input_tokens=calls["input_tokens"], output_tokens=calls["output_tokens"],
            unknown_calls=calls["unknown"]))


def suggest_matches(ocr: OcrComparisonResult, agent: AgentComparisonResult) -> list[FindingMatch]:
    """同文件同行仅生成待确认提示；无行证据、旧侧和一对多位置交给人工裁定。"""

    by_location: dict[tuple[str, int], list[ComparisonFinding]] = defaultdict(list)
    for item in agent.findings:
        if item.line is not None and item.side == "head":
            by_location[(item.path, item.line)].append(item)
    ocr_locations: dict[tuple[str, int], list[ComparisonFinding]] = defaultdict(list)
    for item in ocr.findings:
        if item.line is not None:
            ocr_locations[(item.path, item.line)].append(item)
    return [FindingMatch(id=f"match:{items[0].id}", label=f"{path} · 第 {line} 行"[-200:],
                ocr_ids=[items[0].id], agent_ids=[by_location[(path, line)][0].id])
            for (path, line), items in ocr_locations.items()
            if len(items) == len(by_location.get((path, line), [])) == 1]
