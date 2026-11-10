"""当前有效发现的质量聚合与分页样本共用集合；只读 SQLite，不修改反馈或调用外部服务。"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import HTTPException

from ocr_manager.review_effective import EFFECTIVE

FeedbackFilter = Literal["all", "helpful", "false_positive", "ignored", "fixed", "unmarked"]
DispositionFilter = Literal["all", "open", "fixed", "ignored", "false_positive", "unknown"]

# 时间窗以外的完整性校验也复用同一主身份约束。
VALID_FINDING = """typeof(finding_id)='text' AND typeof(path)='text' AND trim(path)!=''
 AND typeof(content)='text' AND trim(content)!=''"""

# 初审镜像只取一次；有效补审只取主身份，不展开 also_seen_in，不复活历史尝试。
QUALITY_CTE = f"""WITH effective AS ({EFFECTIVE}), documents AS (
 SELECT j.id AS job_id,j.repository_id,j.attempts AS source_attempt,j.finished_at,
 e.revision,COALESCE(e.document_json,j.result_json) AS document,
 CASE WHEN e.job_id IS NULL THEN 0 ELSE 1 END AS promoted
 FROM review_jobs j LEFT JOIN effective e ON e.job_id=j.id
 WHERE j.status IN ('complete','partial','failed','skipped')
 AND (? IS NULL OR j.repository_id=?)
 AND ((j.finished_at>=? AND j.finished_at<?) OR e.job_id IS NOT NULL
      OR j.finished_at IS NULL)
), findings AS (
 SELECT d.*,x.value AS finding,CAST(x.key AS INTEGER) AS idx,
 CASE WHEN promoted=1 THEN json_extract(x.value,'$.finding_id')
 ELSE 'j'||job_id||':a'||source_attempt||':c'||x.key END AS finding_id,
 CASE WHEN promoted=1 THEN json_extract(x.value,'$.origin.recovery_id') END AS recovery_id,
 CASE WHEN promoted=1 THEN json_extract(x.value,'$.origin.comment_index')
 ELSE CAST(x.key AS INTEGER) END AS comment_index
 FROM documents d,json_each(CASE WHEN json_valid(d.document) THEN d.document ELSE '{{}}' END,
 CASE WHEN promoted=1 THEN '$.findings' ELSE '$.comments' END) x
 WHERE x.type='object'
), current_findings AS (
 SELECT f.job_id,f.repository_id,f.source_attempt,COALESCE(f.revision,0) AS revision,
 f.finding_id,f.recovery_id,f.comment_index,
 CASE WHEN f.recovery_id IS NULL THEN f.finished_at ELSE o.created_at END AS generated_at,
 COALESCE(NULLIF(CAST(json_extract(f.finding,'$.category') AS TEXT),''),'未分类') AS category,
 CASE WHEN json_extract(f.finding,'$.severity') IN ('critical','high','medium','low')
 THEN json_extract(f.finding,'$.severity') ELSE 'unclassified' END AS severity,
 json_extract(f.finding,'$.path') AS path,json_extract(f.finding,'$.content') AS content,
 json_extract(f.finding,'$.start_line') AS start_line,
 o.issue_id,i.status AS issue_status,
 NULLIF(CASE WHEN f.recovery_id IS NULL THEN COALESCE(legacy.verdict,feedback.verdict)
 ELSE feedback.verdict END,'fixed') AS verdict
 FROM findings f LEFT JOIN review_issue_occurrences o ON o.finding_id=f.finding_id
 LEFT JOIN review_issue_states i ON i.id=o.issue_id
 LEFT JOIN review_finding_feedback feedback ON feedback.finding_id=f.finding_id
 LEFT JOIN review_feedback legacy ON legacy.job_id=f.job_id
 AND legacy.comment_index=f.comment_index AND f.recovery_id IS NULL
), scoped AS (
 SELECT * FROM current_findings WHERE generated_at>=? AND generated_at<?
 AND {VALID_FINDING}
)"""

COUNTS = """COUNT(*) AS total,
 COALESCE(SUM(verdict='helpful'),0) AS helpful,
 COALESCE(SUM(verdict='false_positive'),0) AS false_positive,
 COALESCE(SUM(verdict='ignored'),0) AS ignored,
 COALESCE(SUM(verdict IS NULL),0) AS unmarked"""

DISPOSITION_COUNTS = """COUNT(*) AS total,
 COALESCE(SUM(issue_status='open'),0) AS open,
 COALESCE(SUM(issue_status='fixed'),0) AS fixed,
 COALESCE(SUM(issue_status='ignored'),0) AS ignored,
 COALESCE(SUM(issue_status='false_positive'),0) AS false_positive,
 COALESCE(SUM(issue_status IS NULL OR issue_status='merged'),0) AS unknown"""


def disposition_snapshot(db: sqlite3.Connection, args: tuple[Any, ...],
                         start: str, days: int) -> dict[str, Any]:
    """处置按发现条数投影，分母与样本一致；历史评价保持独立，不撤销或推断。"""

    summary = dict(db.execute(
        f"{QUALITY_CTE} SELECT {DISPOSITION_COUNTS} FROM scoped", args).fetchone())
    daily = {row["day"]: dict(row) for row in db.execute(f"""{QUALITY_CTE}
        SELECT date(generated_at) AS day,{DISPOSITION_COUNTS} FROM scoped GROUP BY day""", args)}
    categories = [dict(row) for row in db.execute(f"""{QUALITY_CTE}
        SELECT category AS name,{DISPOSITION_COUNTS} FROM scoped
        GROUP BY category ORDER BY false_positive DESC,total DESC,name""", args)]
    projects = [dict(row) for row in db.execute(f"""{QUALITY_CTE}
        SELECT s.repository_id AS id,r.name,{DISPOSITION_COUNTS} FROM scoped s
        JOIN repositories r ON r.id=s.repository_id GROUP BY s.repository_id
        ORDER BY false_positive DESC,total DESC,r.name,s.repository_id""", args)]
    trend = []
    for offset in range(days):
        day = (datetime.fromisoformat(start).date() + timedelta(days=offset)).isoformat()
        trend.append(daily.get(day, {"day": day, **dict.fromkeys(summary, 0)}))
    return {"summary": summary, "trend": trend, "categories": categories, "projects": projects}


def quality_window(days: int) -> tuple[str, str, str]:
    """用 UTC 自然日闭开区间，汇总与样本在跨日时也使用同一显式范围。"""

    today = datetime.now(UTC).date()
    start = today - timedelta(days=days - 1)
    end = today + timedelta(days=1)
    return start.isoformat(), f"{start.isoformat()} 00:00:00", f"{end.isoformat()} 00:00:00"


def quality_snapshot(db: sqlite3.Connection, repository_id: int | None,
                     days: int) -> dict[str, Any]:
    """调用方持有读取事务；所有分类同分母，缺失来源显式标注，不用历史生成总量相减。"""

    # 1. 集合与诊断同范围读取；缺少来源时间的发现不能伪装为本期零值。
    start, since, until = quality_window(days)
    args = (repository_id, repository_id, since, until, since, until)
    summary = dict(db.execute(f"{QUALITY_CTE} SELECT {COUNTS} FROM scoped", args).fetchone())
    unavailable = db.execute(f"""{QUALITY_CTE} SELECT
        (SELECT COUNT(*) FROM current_findings WHERE generated_at IS NULL OR
         ((generated_at>=? AND generated_at<?) AND (typeof(finding_id)!='text'
          OR typeof(path)!='text' OR trim(path)='' OR typeof(content)!='text'
          OR trim(content)=''))) +
        (SELECT COUNT(*) FROM documents WHERE (finished_at>=? AND finished_at<?) AND
         (NOT json_valid(document) OR json_type(CASE WHEN json_valid(document)
          THEN document ELSE '{{}}' END,CASE WHEN promoted=1 THEN '$.findings'
          ELSE '$.comments' END) IS NOT 'array')) +
        (SELECT COUNT(*) FROM documents d,json_each(CASE WHEN json_valid(d.document)
         THEN d.document ELSE '{{}}' END,CASE WHEN promoted=1 THEN '$.findings'
         ELSE '$.comments' END) x WHERE finished_at>=? AND finished_at<?
         AND x.type!='object')""", (*args, since, until, since, until,
                                     since, until)).fetchone()[0]
    # 2. 按来源日期、类别、项目聚合，不逐项目或逐发现加载详情。
    daily = {row["day"]: dict(row) for row in db.execute(
        f"{QUALITY_CTE} SELECT date(generated_at) AS day,{COUNTS} FROM scoped GROUP BY day", args)}
    categories = [dict(row) for row in db.execute(
        f"""{QUALITY_CTE} SELECT category AS name,{COUNTS} FROM scoped
        GROUP BY category ORDER BY false_positive DESC,total DESC,name""", args)]
    projects = [dict(row) for row in db.execute(
        f"""{QUALITY_CTE} SELECT s.repository_id AS id,r.name,{COUNTS} FROM scoped s
        JOIN repositories r ON r.id=s.repository_id GROUP BY s.repository_id
        ORDER BY false_positive DESC,total DESC,r.name,s.repository_id""", args)]
    pending_severity = dict.fromkeys(("critical", "high", "medium", "low", "unclassified"), 0)
    for row in db.execute(f"""{QUALITY_CTE} SELECT severity,COUNT(*) AS count
            FROM scoped WHERE verdict IS NULL GROUP BY severity""", args):
        pending_severity[row["severity"]] = row["count"]
    trend = []
    for offset in range(days):
        day = (datetime.fromisoformat(start).date() + timedelta(days=offset)).isoformat()
        trend.append(daily.get(day, {
            "day": day, "total": 0, "helpful": 0, "false_positive": 0,
            "ignored": 0, "unmarked": 0,
        }))
    return {"summary": summary, "trend": trend, "categories": categories,
            "projects": projects, "unavailable_sources": unavailable,
            "since": since, "until": until,
            "pending_severity": pending_severity,
            "dispositions": disposition_snapshot(db, args, start, days)}


def quality_findings(db: sqlite3.Connection, repository_id: int | None, days: int,
                     feedback: FeedbackFilter, category: str | None,
                     page: int, page_size: int, since: str | None = None,
                     until: str | None = None, severity: str | None = None,
                     status: DispositionFilter = "all", *, handling: str = "all",
                     issue_id: int | None = None, finding_id: str | None = None,
                     keyword: str | None = None, detail: bool = False) -> dict[str, Any]:
    """汇总、发现列表与历史关联共用集合；筛选在分页前执行，详情按稳定身份读取。"""

    if repository_id is not None and not db.execute(
        "SELECT 1 FROM repositories WHERE id=?", (repository_id,)
    ).fetchone():
        raise HTTPException(404, "项目不存在")
    _, default_since, default_until = quality_window(days)
    start = since or (default_since if days else "1970-01-01 00:00:00")
    end = until or (default_until if days else "9999-12-31 00:00:00")
    # 旧修复筛选兼容为未评价，不再单列与价值无关的修复反馈。
    if feedback == "fixed":
        feedback = "unmarked"
    where = """(?='all' OR COALESCE(verdict,'unmarked')=?) AND (? IS NULL OR category=?)
        AND (? IS NULL OR severity=?) AND (?='all' OR
        CASE WHEN issue_status IS NULL OR issue_status='merged' THEN 'unknown'
        ELSE issue_status END=?) AND
        (?='all' OR (?='pending' AND verdict IS NULL) OR (?='handled' AND verdict IS NOT NULL))
        AND (? IS NULL OR issue_id=?) AND (? IS NULL OR finding_id=?)
        AND (? IS NULL OR instr(lower(content),lower(?))>0 OR instr(lower(path),lower(?))>0)"""
    args = (repository_id, repository_id, start, end, start, end, feedback, feedback,
            category, category, severity, severity, status, status,
            handling, handling, handling, issue_id, issue_id, finding_id, finding_id,
            keyword, keyword, keyword)
    total = db.execute(
        f"{QUALITY_CTE} SELECT COUNT(*) FROM scoped WHERE {where}", args).fetchone()[0]
    rows = [dict(row) for row in db.execute(f"""{QUALITY_CTE} SELECT
        s.finding_id,s.job_id,s.repository_id,r.name AS repository_name,s.source_attempt,
        s.revision,s.recovery_id,s.comment_index,s.generated_at,s.category,s.severity,
        s.path,substr(s.content,1,160) AS excerpt,s.issue_id,s.issue_status,
        {"s.content,s.start_line," if detail else ""}
        j.commit_author,COALESCE(s.verdict,'unmarked') AS feedback,
        CASE WHEN s.verdict IS NULL THEN 'pending' ELSE 'handled' END AS handling FROM scoped s
        JOIN repositories r ON r.id=s.repository_id JOIN review_jobs j ON j.id=s.job_id
        WHERE {where}
        ORDER BY generated_at DESC,s.job_id DESC,s.finding_id LIMIT ? OFFSET ?""",
        (*args, page_size, (page - 1) * page_size))]
    return {"items": rows, "total": total, "page": page, "page_size": page_size,
            "since": start, "until": end}
