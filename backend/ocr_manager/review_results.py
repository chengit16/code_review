"""校验 OCR 评论集合并投影可持久化结果；不读取工件、不调用模型或写入数据库。"""

from __future__ import annotations

from typing import Any

from ocr_manager.recovery_budget import budget_gate
from ocr_manager.review_diagnostics import failure_analysis
from ocr_manager.review_failures import ReviewFailure, result_failure, retry_summary


def review_comments(result: dict[str, Any]) -> list[dict[str, Any]]:
    """兼容失败结果的空评论，拒绝把错误集合类型静默解释为无发现。"""

    comments = result.get("comments", [])
    manifest = result.get("manifest")
    state = manifest.get("terminal_state") if isinstance(manifest, dict) else None
    if comments is None and state == "failed":
        return []
    if not isinstance(comments, list) or any(not isinstance(item, dict) for item in comments):
        raise ReviewFailure("result_format", "OCR 评论集合类型无效")
    return comments


def project_review_result(result: dict[str, Any]) -> dict[str, Any]:
    """原始响应留在受控工件；数据库只保存发现、覆盖、用量和可信故障摘要。"""

    manifest, summary = result.get("manifest"), result.get("summary")
    state = manifest.get("terminal_state") if isinstance(manifest, dict) else None
    failure = result_failure(str(state), result)
    gate = budget_gate(result)
    return {
        **({"budget_gate": gate.model_dump()} if gate else {}),
        "comments": [{key: comment[key] for key in (
            "path", "content", "start_line", "end_line", "severity", "category") if key in comment}
            for comment in review_comments(result)],
        "manifest": {"terminal_state": state, "coverage": manifest.get("coverage")}
        if isinstance(manifest, dict) else None,
        "summary": {"budget_exceeded": summary.get("budget_exceeded") is True}
        if isinstance(summary, dict) else None,
        "usage": {key: value for key, value in summary.items()
                  if key in {"input_tokens", "output_tokens", "total_tokens"}
                  and type(value) is int and value >= 0}
        if isinstance(summary, dict) else None,
        "preview": result.get("preview"),
        "input_filter": {"excluded_count": result["input_filter"]["excluded_count"]}
        if isinstance(result.get("input_filter"), dict)
        and type(result["input_filter"].get("excluded_count")) is int else None,
        "message": str(failure) if failure else (
            "无可审查文件" if state == "skipped" else None),
        "source": "preview" if result.get("source") == "preview" else None,
        "diagnostic": failure.projection() if failure else None,
        "retry_summary": retry_summary(result),
        "failure_analysis": failure_analysis(result),
    }
