/** @description 任务列表与首页复用的处置摘要，只展示持久化关联事实。 */
import { Link } from "react-router-dom";

import type { ReviewJob } from "../../api/types";
import { formatSeverity } from "../../ui/format";

/** 最近任务与任务主列表共用当前有效发现的处置事实，不将完整评审等同修复。 */
export function IssueSummary({ job, detailPath }: { /** 当前任务的服务端处置摘要。 */ job: ReviewJob; /** 保留来源筛选的详情路径。 */ detailPath: (id: number) => string }) {
  const summary = job.issue_summary;
  if (!summary) return <span>状态待核实</span>;
  if (!summary.available) return <span>{job.status === "queued" ? "待评审" : job.status === "running" ? "评审中" : ["complete", "partial"].includes(job.effective_status ?? job.status) ? "状态待核实" : "未形成有效结论"}</span>;
  if (summary.no_findings) return <span>本次未发现问题</span>;
  if (!summary.finding_count) return <span>{(job.effective_status ?? job.status) === "partial" ? "暂无发现 · 覆盖不完整" : summary.coverage_limited ? "选中范围内暂无发现" : "暂无发现 · 覆盖待核实"}</span>;
  return <div className="jobs-issue-summary">
    <span>{summary.finding_count} 条发现{summary.highest_severity ? ` · 最高${formatSeverity(summary.highest_severity)}` : ""}</span>
    <small title="按最终关联问题去重计数；同一问题可能有多条发现">{summary.open_count > 0 ? <Link to={openFindingPath(detailPath(job.id))} aria-label={`任务 ${job.id} 待处理 ${summary.open_count} 个问题`}>待处理 {summary.open_count}</Link> : summary.complete ? "全部已处置" : "状态待核实"}{summary.fixed_count > 0 && ` · 修复 ${summary.fixed_count}`}{summary.ignored_count > 0 && ` · 忽略 ${summary.ignored_count}`}{summary.unknown_count > 0 && summary.open_count > 0 && " · 部分待核实"}</small>
  </div>;
}

function openFindingPath(path: string): string {
  const [pathname, search = ""] = path.split("?");
  const params = new URLSearchParams(search);
  params.set("finding_state", "open");
  return `${pathname}?${params}#job-result`;
}

