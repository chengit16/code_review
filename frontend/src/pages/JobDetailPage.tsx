/** @description 展示单次 OCR 评审的覆盖、发现和可重跑状态。 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, ExternalLink, RotateCcw, Send } from "lucide-react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";

import { apiRequest } from "../api/client";
import { downloadTaskReport } from "../api/tasks";
import { JobFiles } from "./JobFiles";
import { JobNavigation } from "./JobNavigation";
import { ModelUsage } from "./ModelUsage";
import { TaskStop } from "./TaskControls";
import { AttemptReports } from "./AttemptReports";
import { FindingsPanel } from "./FindingsPanel";
import { CoverageReasons } from "./CoverageReasons";
import { GitLabPublications } from "./GitLabPublications";
import type { ReviewJobDetail } from "../api/types";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { Status } from "../ui/Status";
import { formatTime } from "../ui/format";

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
  const location = useLocation();
  // 来源保存在 URL 中，刷新和分享仍保留筛选；兼容旧版列表的路由 state。
  const back = location.search ? `/jobs${location.search}` : typeof location.state?.back === "string" && location.state.back.startsWith("/jobs?") ? location.state.back : "/jobs";
  const download = useMutation({ mutationFn: () => downloadTaskReport(token, Number(id)) });
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["job", id], queryFn: ({ signal }) => apiRequest<ReviewJobDetail>(token, `/api/jobs/${id}`, { signal }), refetchInterval: (current) => ["queued", "running"].includes(current.state.data?.status ?? "") ? 5000 : 30000, enabled: Boolean(id) });
  const retry = useMutation({ mutationFn: () => apiRequest<{ job_id: number }>(token, `/api/jobs/${id}/retry`, { method: "POST" }), onSuccess: (result) => { void queryClient.invalidateQueries({ queryKey: ["job", id] }); void queryClient.invalidateQueries({ queryKey: ["jobs"] }); void queryClient.invalidateQueries({ queryKey: ["overview"] }); void queryClient.invalidateQueries({ queryKey: ["job-neighbors"] }); if (result.job_id !== Number(id)) navigate(`/jobs/${result.job_id}${back.startsWith("/jobs?") ? back.slice(5) : ""}`, { state: { back } }); } });
  const resend = useMutation({ mutationFn: () => apiRequest<unknown>(token, `/api/jobs/${id}/notification/retry`, { method: "POST" }), onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["job", id] }) });
  const feedback = useMutation({
    mutationFn: ({ index, verdict }: { index: number; verdict: "helpful" | "false_positive" | "fixed" | null }) => apiRequest<unknown>(token, `/api/jobs/${id}/feedback/${index}`, verdict ? { method: "PUT", body: JSON.stringify({ verdict }) } : { method: "DELETE" }),
    onSuccess: async () => {
      // 反馈可能关闭跨任务共享的问题，刷新所有详情、问题列表及成效统计。
      await Promise.all(["job", "review-feedback-summary", "review-issues", "review-issue", "review-effectiveness"].map((key) =>
        queryClient.invalidateQueries({ queryKey: [key] })));
    },
  });
  const job = query.data;
  const coverage = job?.result?.manifest?.coverage;
  const comments = job?.result?.comments ?? [];
  const excluded = job?.result?.preview?.files.filter((file) => !file.will_review) ?? [];
  return <div className="page job-detail-page">
    <JobNavigation token={token} id={Number(id)} back={back} />
    <PageHeader title={`任务 #${id ?? ""}`} subtitle={job ? `${job.mr_iid < 0 ? "默认分支 Push" : `MR !${job.mr_iid}`} · ${job.commit_sha}` : "逐提交评审详情"} actions={
      job && <><button className="icon-button" title="下载脱敏报告" aria-label="下载脱敏报告" disabled={download.isPending} onClick={() => download.mutate()}><Download size={16} /></button>{canEdit && ["complete", "partial", "failed", "skipped"].includes(job.status) && <><button className="button button-secondary" type="button" disabled={resend.isPending || !["failed", "sent"].includes(job.delivery?.status ?? "")} onClick={() => resend.mutate()}><Send size={16} />重发通知</button><button className="button button-secondary" type="button" disabled={retry.isPending} onClick={() => { if (window.confirm(`重新评审任务 #${id}？将再次调用模型并可能产生费用，不会修改代码。仅通知失败请使用重发通知。`)) retry.mutate(); }}><RotateCcw size={16} />重新评审</button></>}</>
    } />
    <QueryState loading={query.isLoading} error={query.error} onRetry={() => void query.refetch()} />
    {(retry.error || resend.error || feedback.error) && <p className="form-error" role="alert">{(retry.error || resend.error || feedback.error)?.message}</p>}
    {job && <>
      <section className="detail-summary job-summary-card">
        <div><span>评审状态</span><Status value={job.status} /></div>
        <div><span>尝试次数</span><strong>{job.attempts}</strong></div>
        <div><span>创建时间</span><strong>{formatTime(job.created_at)}</strong></div>
        <div><span>完成时间</span><strong>{formatTime(job.finished_at)}</strong></div>
      </section>
      {job.correlation_id && <p className="job-correlation-id">关联编号：<code>{job.correlation_id}</code> · 可用于诊断包检索</p>}
      <div className="job-action-row">
        <div className="job-state-actions">
          {canEdit && <TaskStop token={token} id={job.id} status={job.status} stopping={Boolean(job.cancel_requested)} />}
          {canEdit && job.status === "cancelled" && <button className="button button-secondary" onClick={() => { if (window.confirm(`重新评审任务 #${id}？将再次调用模型并可能产生费用，不会修改代码。仅通知失败请使用重发通知。`)) retry.mutate(); }} disabled={retry.isPending}><RotateCcw size={16} />重新评审</button>}
          {job.failure_stage && <p className="detail-line">{job.status === "running" ? "当前阶段" : "失败阶段"}：{({ configuration: "配置校验", git: "Git 拉取与提交准备", ocr_configuration: "OCR 模型配置", preview: "范围预览", review: "模型评审", validation: "结果校验" } as Record<string, string>)[job.failure_stage] ?? job.failure_stage}</p>}
        </div>
        {(job.mr_url || job.commit_url) && <div className="detail-links">{job.mr_url && <a href={job.mr_url} target="_blank" rel="noreferrer">查看 MR <ExternalLink size={14} /></a>}{job.commit_url && <a href={job.commit_url} target="_blank" rel="noreferrer">查看提交 <ExternalLink size={14} /></a>}</div>}
      </div>
      {download.error && <p className="form-error" role="alert">{download.error.message}</p>}
      {job.error && <div className="detail-error" role="alert">{job.error}<p>{["configuration", "ocr_configuration"].includes(job.failure_stage ?? "") ? <Link to="/settings?tab=model">检查模型配置 →</Link> : <Link to="/repositories">打开项目配置，查看接入诊断 →</Link>}</p></div>}
      <CoverageReasons job={job} />
      <FindingsPanel comments={comments} feedback={job.feedback} issueIds={job.issue_ids} issueStatuses={job.issue_statuses} status={job.status} coverageWaived={Boolean(coverage?.waived.length)} pending={feedback.isPending} canEdit={canEdit} onFeedback={(index, verdict) => feedback.mutate({ index, verdict })} />
      <div className="job-insight-grid">
        <ModelUsage result={job.result} />
        <section className="section detail-insight-card coverage-section">
          <div className="section-head"><h2>覆盖情况</h2></div>
          {coverage ? <div className="coverage-grid"><div><strong>{coverage.selected.length}</strong><span>选中文件</span></div><div><strong>{coverage.completed.length + coverage.reused.length}</strong><span>完成 / 复用</span></div><div><strong>{coverage.failed.length}</strong><span>失败</span></div><div><strong>{coverage.waived.length}</strong><span>豁免</span></div></div> : <p className="empty-inline">尚无 OCR 覆盖结果</p>}
          {job.result?.preview && <p className="coverage-note">范围预览：{job.result.preview.reviewable_count} 个可审查文件，{excluded.length ? `排除 ${excluded.length} 个文件` : "没有排除文件"}</p>}
        </section>
      </div>
      {job.result?.summary?.budget_exceeded && <p className="form-error">Token 预算已用尽，本次结果为部分覆盖</p>}
      {canEdit && <GitLabPublications token={token} job={job} />}
      <details className="advanced-panel"><summary>变更文件与排除范围</summary><JobFiles job={job} />      {job.result?.preview && excluded.length > 0 && <section className="section scope-preview-section"><div className="section-head"><h2>排除文件</h2><span>{excluded.length} 个文件未进入评审</span></div><div className="table-scroll"><table><thead><tr><th>文件</th><th>原因</th></tr></thead><tbody>{excluded.map((file) => <tr key={file.path}><td className="mono file-path">{file.path}</td><td>{file.exclude_reason ?? "未说明"}</td></tr>)}</tbody></table></div></section>}
</details>
      <details className="advanced-panel"><summary>历史报告与对比</summary><AttemptReports token={token} job={job} key={`${job.id}-${job.attempts}`} /></details>
      <div className="job-footer-grid">
        <section className="section delivery-card"><div className="section-head"><h2>飞书通知</h2></div><div className="delivery-summary"><Status value={job.delivery?.status ?? "未创建"} /><span>尝试 {job.delivery?.attempts ?? 0} 次</span>{job.delivery?.sent_at && <span>{formatTime(job.delivery.sent_at)}</span>}</div>{job.delivery?.error && <p className="form-error">{job.delivery.error}</p>}</section>
        <details className="advanced-panel"><summary>执行记录 · {job.attempt_history.length} 次</summary><section className="section attempt-history-card"><div className="section-head"><h2>执行记录</h2><span>{job.attempt_history.length} 次</span></div><div className="table-scroll"><table><thead><tr><th>次数</th><th>状态</th><th>结束时间</th><th>诊断</th></tr></thead><tbody>{job.attempt_history.map((attempt) => <tr key={attempt.id}><td>#{attempt.attempt_number}</td><td><Status value={attempt.status} /></td><td>{formatTime(attempt.finished_at)}</td><td className="diagnostic" title={attempt.error ?? ""}>{attempt.error ?? "—"}</td></tr>)}{job.attempt_history.length === 0 && <tr><td colSpan={4} className="empty-row">暂无执行记录</td></tr>}</tbody></table></div></section></details>
      </div>
    </>}
  </div>;
}
