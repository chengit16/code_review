/** @description 有效结论与初审分开展示；反馈按主身份发送，不将聚合序号交给旧入口。 */
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { setFindingFeedback } from "../api/reviewConclusions";
import type { ReviewJobDetail } from "../api/types";
import { Status } from "../ui/Status";

import type { FindingFeedbackChoice } from "./FindingActions";
import { FindingsPanel } from "./FindingsPanel";

/** 已验证有效结论的来源和覆盖；旧初审作为不可覆盖的独立证据保留。 */
export function EffectiveReview({ token, job, canEdit, initialIssueState = "all" }: {
  /** 任务列表直达时初始显示开放问题的发现。 */ initialIssueState?: "all" | "open";
  /** 内存凭据。 */ token: string;
  /** 包含服务端已校验结论、稳定反馈及问题映射。 */ job: ReviewJobDetail;
  /** 仅控制显示，服务端继续核验版本和角色。 */ canEdit: boolean;
}) {
  const client = useQueryClient();
  const document = job.effective_document;
  const feedback = useMutation({
    mutationFn: ({ index, verdict }: { index: number; verdict: FindingFeedbackChoice | null }) => {
      if (!document) throw new Error("有效结论尚不可用，请刷新");
      const finding = document.findings[index];
      const version = { source_attempt: document.version.source_attempt, revision: document.version.revision };
      return setFindingFeedback(token, job.id, finding.finding_id, version, verdict);
    },
    onSuccess: async () => { await Promise.all(["jobs", "job-neighbors", "job", "review-feedback-summary", "review-issues", "review-issue", "review-effectiveness", "overview"].map((key) => client.invalidateQueries({ queryKey: [key] }))); },
  });
  if (!document) return null;
  const coverage = document.version.coverage;
  const comments = document.findings.map((item) => ({ ...item, start_line: item.start_line ?? undefined, end_line: item.end_line ?? undefined, severity: item.severity ?? undefined, category: item.category ?? undefined }));
  const marks: ReviewJobDetail["feedback"] = {};
  const issueIds: Record<number, number> = {};
  const issueStatuses: ReviewJobDetail["issue_statuses"] = {};
  document.findings.forEach((item, index) => {
    const verdict = job.finding_feedback?.[item.finding_id];
    const issue = job.resolved_finding_issues?.[item.finding_id] ?? job.finding_issues?.[item.finding_id];
    if (verdict) marks[index] = verdict;
    if (issue) { issueIds[index] = issue.id; issueStatuses[index] = issue.status; }
  });
  return <section aria-label="当前有效评审结论">
    <div className="section"><h2>当前有效结论 · 版本 {document.version.revision}</h2><p>源尝试 {document.version.source_attempt} · <Status value={document.version.terminal_state} /> · 初审记录保持不变</p>{coverage && <p>完成 / 复用 {coverage.completed + coverage.reused}/{coverage.selected} · 失败 {coverage.failed} · 豁免 {coverage.waived}</p>}<p>GitLab 补审发现发布尚未支持，当前入口不重发初审发现。飞书补充通知独立于初审通知。</p></div>
    {feedback.error && <p className="form-error" role="alert">{feedback.error.message}。版本可能已变化，请刷新后核对，未自动重试。</p>}
    <FindingsPanel initialIssueState={initialIssueState} key={`${document.version.source_attempt}-${document.version.revision}`} comments={comments} findingIds={document.findings.map((item) => item.finding_id)} findingSources={document.findings.map((item) => item.origin.kind === "recovery" ? `补审 #${item.origin.recovery_id} · 原始发现 ${item.origin.comment_index + 1}` : `初审第 ${item.origin.source_attempt} 次 · 原始发现 ${item.origin.comment_index + 1}`)} feedback={marks} issueIds={issueIds} issueStatuses={issueStatuses} status={document.version.terminal_state} coverageWaived={Boolean(coverage?.waived)} pending={feedback.isPending} canEdit={canEdit} onFeedback={(index, verdict) => feedback.mutate({ index, verdict })} />
    <details className="advanced-panel"><summary>保留的初审发现 · {job.result?.comments?.length ?? 0} 条</summary><p>初审状态 <Status value={job.status} />，不以补审完成改写原执行事实。</p>{job.result?.comments?.map((item, index) => <article key={index} className="attempt-evidence"><p className="mono file-path">{item.path}</p><p>{item.content}</p></article>)}</details>
  </section>;
}
