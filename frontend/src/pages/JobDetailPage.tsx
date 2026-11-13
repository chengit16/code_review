/** @description 展示单次 OCR 评审的覆盖、发现和可重跑状态。 */

import { Button } from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, ExternalLink, RotateCcw, Send } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";

import { setFindingFeedback } from "../api/reviewConclusions";
import { apiRequest } from "../api/client";
import { downloadTaskReport } from "../api/tasks";
import type { ReviewJobDetail } from "../api/types";
import { ListExcerpt } from "../ui/ListControls";
import { ListTable } from "../ui/ListTable";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { Status } from "../ui/Status";
import { formatTime } from "../ui/format";

import { AttemptReports } from "./AttemptReports";
import { EffectiveReview } from "./EffectiveReview";
import { FindingsPanel } from "./FindingsPanel";
import { GitLabPublications } from "./GitLabPublications";
import { JobDiagnosticSections } from "./JobDiagnosticSections";
import { AttemptTimeline } from "./JobExecution";
import { JobFiles } from "./JobFiles";
import { JobNavigation } from "./JobNavigation";
import { TaskStop } from "./TaskControls";
import { TaskDelete } from "./TaskDelete";
import type { FindingFeedbackChoice } from "./FindingActions";

/** 按任务重新挂载详情，防止连续导航时沿用旧任务的发现筛选和操作状态。 */
export function JobDetailPage({ token, canEdit = true }: {
  /** 内存中的管理口令。 */ token: string;
  /** 只控制修改动作界面；服务端仍执行角色授权。 */ canEdit?: boolean;
}) {
  const { id } = useParams();
  return <JobDetail key={id} token={token} canEdit={canEdit} />;
}

function JobDetail({ token, canEdit }: {
  token: string;
  canEdit: boolean;
}) {
  const { id } = useParams();
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState<string[]>(() => window.location.hash === "#job-cost" ? ["cost"] : window.location.hash === "#job-execution" ? ["execution"] : []);
  const location = useLocation();
  function openDiagnostic(key: string, anchor: string) { setExpanded((value) => [...new Set([...value, key])]); requestAnimationFrame(() => document.getElementById(anchor)?.scrollIntoView({ block: "start" })); }
  // 来源保存在 URL 中，刷新和分享仍保留筛选；兼容旧版列表的路由 state。
  const listParams = new URLSearchParams(location.search);
  const openFindings = listParams.get("finding_state") === "open";
  listParams.delete("finding_state");
  const back = listParams.size ? `/jobs?${listParams}` : typeof location.state?.back === "string" && location.state.back.startsWith("/jobs?") ? location.state.back : "/jobs";
  const download = useMutation({ mutationFn: () => downloadTaskReport(token, Number(id)) });
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["job", id], queryFn: ({ signal }) => apiRequest<ReviewJobDetail>(token, `/api/jobs/${id}`, { signal }), refetchInterval: (current) => (["queued", "running"].includes(current.state.data?.status ?? "") || current.state.data?.active_recovery_id) ? 5000 : 30000, enabled: Boolean(id) });
  useEffect(() => {
    const key = location.hash === "#job-execution" ? "execution" : location.hash === "#job-cost" ? "cost" : null;
    if (!key) return;
    setExpanded((value) => value.includes(key) ? value : [...value, key]);
  }, [location.hash]);
  const retry = useMutation({ mutationFn: () => apiRequest<{ job_id: number }>(token, `/api/jobs/${id}/retry`, { method: "POST" }), onSuccess: (result) => { void queryClient.invalidateQueries({ queryKey: ["job", id] }); void queryClient.invalidateQueries({ queryKey: ["jobs"] }); void queryClient.invalidateQueries({ queryKey: ["overview"] }); void queryClient.invalidateQueries({ queryKey: ["job-neighbors"] }); if (result.job_id !== Number(id)) navigate(`/jobs/${result.job_id}${back.startsWith("/jobs?") ? back.slice(5) : ""}`, { state: { back } }); } });
  const resend = useMutation({ mutationFn: () => apiRequest<unknown>(token, `/api/jobs/${id}/notification/retry`, { method: "POST" }), onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["job", id] }) });
  const feedback = useMutation({
    mutationFn: ({ index, verdict, sourceAttempt }: { index: number; verdict: FindingFeedbackChoice | null; sourceAttempt: number }) => setFindingFeedback(token, Number(id), `j${id}:a${sourceAttempt}:c${index}`, { source_attempt: sourceAttempt, revision: 0 }, verdict),
    onSuccess: async () => {
      // 反馈不改变问题处置；刷新发现评价及同源统计，避免旧评价留在缓存。
      await Promise.all(["jobs", "job-neighbors", "job", "review-feedback-summary", "review-issues", "review-issue", "review-effectiveness", "overview", "review-findings", "review-finding"].map((key) =>
        queryClient.invalidateQueries({ queryKey: [key] })));
    },
  });
  const job = query.data;
  const coverage = job?.result?.manifest?.coverage;
  const comments = job?.result?.comments ?? [];
  const issueIds = { ...job?.issue_ids };
  const issueStatuses = { ...job?.issue_statuses };
  if (job?.resolved_finding_issues) {
    comments.forEach((_, index) => {
      const issue = job.resolved_finding_issues?.[`j${job.id}:a${job.attempts}:c${index}`];
      if (issue) { issueIds[index] = issue.id; issueStatuses[index] = issue.status; }
    });
  }
  const excluded = job?.result?.preview?.files.filter((file) => !file.will_review) ?? [];
  return <div className="page job-detail-page">
    <JobNavigation token={token} id={Number(id)} back={back} />
    <PageHeader title={`任务 #${id ?? ""}`} subtitle={job ? `${job.mr_iid < 0 ? "默认分支 Push" : `MR !${job.mr_iid}`} · ${job.commit_sha}` : "逐提交评审详情"} actions={
      job && <><button className="icon-button" title="下载脱敏报告" aria-label="下载脱敏报告" disabled={download.isPending} onClick={() => download.mutate()}><Download size={16} /></button>{canEdit && ["complete", "partial", "failed", "skipped"].includes(job.status) && <><button className="button button-secondary" type="button" disabled={resend.isPending || !["failed", "sent"].includes(job.delivery?.status ?? "")} onClick={() => resend.mutate()}><Send size={16} />重发通知</button><button className="button button-secondary" type="button" disabled={retry.isPending || Boolean(job.active_recovery_id)} onClick={() => { if (window.confirm(`重新评审任务 #${id}？将再次调用模型并可能产生费用，不会修改代码。仅通知失败请使用重发通知。`)) retry.mutate(); }}><RotateCcw size={16} />重新评审</button></>}{canEdit && <TaskDelete token={token} target={job} back={back} disabled={Boolean(job.active_recovery_id) || retry.isPending || resend.isPending || feedback.isPending} />}</>
    } />
    <QueryState loading={query.isLoading} error={query.error} onRetry={() => void query.refetch()} />
    {(retry.error || resend.error || feedback.error) && <p className="form-error" role="alert">{(retry.error || resend.error || feedback.error)?.message}</p>}
    {feedback.error && <p role="alert">反馈未保存，操作版本与输入已保留，请刷新核对后重新选择。<span>保留目标 j{id}:a{feedback.variables?.sourceAttempt}:c{feedback.variables?.index} · 版本 {feedback.variables?.sourceAttempt}/0 · 反馈 {feedback.variables?.verdict ?? "撤销"}。</span><Button onClick={async () => { await query.refetch(); feedback.reset(); }}>刷新并重新核对</Button></p>}
    {job && <>
      <section className="detail-summary job-summary-card">
        <div><span>评审状态</span><Status value={job.effective_status ?? job.status} /></div>
        <div><span>提交人</span><strong>{job.commit_author?.trim() || "未记录"}</strong></div>
        <div><span>尝试次数</span><strong>{job.attempts}</strong></div>
        <div><span>创建时间</span><strong>{formatTime(job.created_at)}</strong></div>
        <div><span>完成时间</span><strong>{formatTime(job.finished_at)}</strong></div>
      </section>
      {job.correlation_id && <p className="job-correlation-id">关联编号：<code>{job.correlation_id}</code> · 可用于诊断包检索</p>}
      <div className="job-action-row">
        <div className="job-state-actions">
          {canEdit && <TaskStop token={token} id={job.id} status={job.status} stopping={Boolean(job.cancel_requested)} />}
          {canEdit && job.status === "cancelled" && <button className="button button-secondary" onClick={() => { if (window.confirm(`重新评审任务 #${id}？将再次调用模型并可能产生费用，不会修改代码。仅通知失败请使用重发通知。`)) retry.mutate(); }} disabled={retry.isPending || Boolean(job.active_recovery_id)}><RotateCcw size={16} />重新评审</button>}
          {job.failure_stage && <p className="detail-line">{job.status === "running" ? "当前阶段" : "失败阶段"}：{({ configuration: "配置校验", git: "Git 拉取与提交准备", ocr_configuration: "OCR 模型配置", preflight: "固定范围预检", preview: "范围预览", review: "模型评审", validation: "结果校验" } as Record<string, string>)[job.failure_stage] ?? job.failure_stage}</p>}
        </div>
        {(job.mr_url || job.commit_url) && <div className="detail-links">{job.mr_url && <a href={job.mr_url} target="_blank" rel="noreferrer">查看 MR <ExternalLink size={14} /></a>}{job.commit_url && <a href={job.commit_url} target="_blank" rel="noreferrer">查看提交 <ExternalLink size={14} /></a>}</div>}
      </div>
      <nav className="job-detail-jump" aria-label="任务详情分区">
        <a href="#job-result">结论与发现</a><a href="#job-execution" onClick={() => openDiagnostic("execution", "job-execution")}>执行与恢复</a><a href="#job-cost" onClick={() => openDiagnostic("cost", "job-cost")}>覆盖与费用</a><a href="#job-history" onClick={() => { const detail = document.getElementById("job-history"); if (detail instanceof HTMLDetailsElement) detail.open = true; }}>文件与历史</a><a href="#job-notifications">通知与尝试</a>
      </nav>
      {download.error && <p className="form-error" role="alert">{download.error.message}</p>}
      {job.error && <div className="detail-error" role="alert">{job.error}<p>{["configuration", "ocr_configuration"].includes(job.failure_stage ?? "") ? <Link to="/settings?tab=model">检查模型配置 →</Link> : <Link to="/repositories">打开项目配置，查看接入诊断 →</Link>}</p></div>}
      <section id="job-result" className="job-detail-region" aria-label="评审结论与发现">
        {job.effective_document ? <EffectiveReview token={token} job={job} canEdit={canEdit} initialIssueState={openFindings ? "open" : "all"} /> : <FindingsPanel initialIssueState={openFindings ? "open" : "all"} comments={comments} feedback={job.feedback} issueIds={issueIds} issueStatuses={issueStatuses} status={job.status} coverageWaived={Boolean(coverage?.waived.length)} pending={feedback.isPending || Boolean(feedback.error)} canEdit={canEdit} onFeedback={(index, verdict) => feedback.mutate({ index, verdict, sourceAttempt: job.attempts })} />}
      </section>
      <JobDiagnosticSections token={token} job={job} canEdit={canEdit} expanded={expanded} onExpanded={setExpanded} />
      {job.result?.summary?.budget_exceeded && <p className="form-error">Token 预算已用尽，本次结果为部分覆盖</p>}
      {canEdit && !job.effective_document && <GitLabPublications token={token} job={job} />}
      <details id="job-history" className="advanced-panel"><summary>变更文件与排除范围</summary><JobFiles job={job} />      {job.result?.preview && excluded.length > 0 && <section className="section scope-preview-section"><div className="section-head"><h2>排除文件</h2><span>{excluded.length} 个文件未进入评审</span></div><ListTable rowKey="path" dataSource={excluded} pagination={false} scroll={{ x: 650 }} columns={[
        { title: "文件", key: "path", render: (_, file) => <ListExcerpt text={file.path} /> },
        { title: "原因", key: "reason", render: (_, file) => <ListExcerpt text={file.exclude_reason ?? "未说明"} /> },
      ]} /></section>}
</details>
      <details className="advanced-panel"><summary>历史报告与对比</summary><AttemptReports token={token} job={job} key={`${job.id}-${job.attempts}`} /></details>
      <div id="job-notifications" className="job-footer-grid job-detail-region">
        <section className="section delivery-card"><div className="section-head"><h2>飞书通知</h2></div><div className="delivery-summary"><Status value={job.delivery?.status ?? "未创建"} /><span>尝试 {job.delivery?.attempts ?? 0} 次</span>{job.delivery?.sent_at && <span>{formatTime(job.delivery.sent_at)}</span>}</div>{job.delivery?.error && <p className="form-error">{job.delivery.error}</p>}</section>
        <AttemptTimeline job={job} />
      </div>
    </>}
  </div>;
}
