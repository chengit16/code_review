/** @description 任务列表按当前发现展示反馈处理进度，不混入跨任务问题的修复状态。 */
import { Tag } from "antd";

import type { ReviewJob } from "../../api/types";
import { formatSeverity } from "../../ui/format";

type Progress = { text: string; color?: "orange" | "blue" | "green"; title: string };

/** 按发现展示反馈处理进度；未知数据不补零，完成仅针对当前已发现范围。 */
export function IssueSummary({ job }: { /** 当前任务的服务端发现与反馈摘要。 */ job: ReviewJob }) {
  const summary = job.issue_summary;
  if (!summary) return <span>状态待核实</span>;
  if (!summary.available) return <span>{job.status === "queued" ? "待评审" : job.status === "running" ? "评审中" : ["complete", "partial"].includes(job.effective_status ?? job.status) ? "状态待核实" : "未形成有效结论"}</span>;
  if (!isCount(summary.finding_count)) return <span>状态待核实</span>;
  if (summary.finding_count === 0) {
    if (summary.no_findings && summary.coverage_complete && !summary.coverage_limited
      && (job.effective_status ?? job.status) === "complete") return <span>本次未发现问题</span>;
    return <span>{(job.effective_status ?? job.status) === "partial" ? "暂无发现 · 覆盖不完整" : summary.coverage_limited ? "选中范围内暂无发现" : "暂无发现 · 覆盖待核实"}</span>;
  }
  const feedback = feedbackProgress(job.feedback_summary, summary.finding_count);
  const limited = (job.effective_status ?? job.status) === "partial" || summary.coverage_limited || !summary.coverage_complete;
  return <div className="jobs-issue-summary">
    <span>{summary.finding_count} 条发现{summary.highest_severity ? ` · 最高${formatSeverity(summary.highest_severity)}` : ""}</span>
    {limited && <small>仅当前已发现范围</small>}
    <div className="jobs-completion-tags">
      <Tag color={feedback.color} title={feedback.title} aria-label={`反馈进度：${feedback.text}`}>{feedback.text}</Tag>
    </div>
    {feedback.detail && <small title="按当前有效发现逐条计数，有反馈即表示该发现已处理">{feedback.detail}</small>}
  </div>;
}

function isCount(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}

function feedbackProgress(summary: ReviewJob["feedback_summary"], findingCount: number): Progress & { detail?: string } {
  const unknown: Progress = { text: "反馈待核实", title: "当前反馈数据缺失或不一致，不能确认是否已反馈。" };
  if (!summary?.available || summary.total !== findingCount
    || ![summary.total, summary.helpful, summary.false_positive, summary.ignored, summary.unmarked].every(isCount)) return unknown;
  const marked = summary.helpful + summary.false_positive + summary.ignored;
  if (marked + summary.unmarked !== findingCount) return unknown;
  const detail = `有帮助 ${summary.helpful} · 误报 ${summary.false_positive} · 忽略 ${summary.ignored}`;
  const title = "按当前发现逐条统计，有帮助、误报和忽略均表示已反馈、已处理；历史修复反馈仍按未评价处理。";
  if (summary.unmarked === 0) return { text: `反馈完成 ${marked}/${findingCount}`, color: "green", title, detail };
  if (marked === 0) return { text: `待反馈 · 剩 ${summary.unmarked} 条`, color: "orange", title, detail };
  return { text: `反馈中 ${marked}/${findingCount} · 剩 ${summary.unmarked} 条`, color: "blue", title, detail };
}
