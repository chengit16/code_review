/** @description 展示单次 OCR 评审的覆盖、发现和可重跑状态。 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ExternalLink, RotateCcw, Send } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { apiRequest } from "../api/client";
import type { ReviewJobDetail } from "../api/types";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { Status } from "../ui/Status";
import { formatTime } from "../ui/format";

/** 保留 OCR 部分覆盖与失败结论，并在重跑后刷新服务端事实。 */
export function JobDetailPage({ token }: { /** 内存中的管理口令。 */ token: string }) {
  const { id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["job", id], queryFn: () => apiRequest<ReviewJobDetail>(token, `/api/jobs/${id}`), refetchInterval: 5000, enabled: Boolean(id) });
  const retry = useMutation({ mutationFn: () => apiRequest<{ job_id: number }>(token, `/api/jobs/${id}/retry`, { method: "POST" }), onSuccess: (result) => { void queryClient.invalidateQueries({ queryKey: ["job", id] }); void queryClient.invalidateQueries({ queryKey: ["jobs"] }); if (result.job_id !== Number(id)) navigate(`/jobs/${result.job_id}`); } });
  const resend = useMutation({ mutationFn: () => apiRequest<unknown>(token, `/api/jobs/${id}/notification/retry`, { method: "POST" }), onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["job", id] }) });
  const job = query.data;
  const coverage = job?.result?.manifest?.coverage;
  const comments = job?.result?.comments ?? [];
  const excluded = job?.result?.preview?.files.filter((file) => !file.will_review) ?? [];
  return <div className="page"><Link className="back-link" to="/jobs"><ArrowLeft size={16} />返回任务列表</Link><PageHeader title={`任务 #${id ?? ""}`} subtitle={job ? `${job.mr_iid < 0 ? "默认分支 Push" : `MR !${job.mr_iid}`} · ${job.commit_sha}` : "逐提交评审详情"} actions={
    job && ["complete", "partial", "failed", "skipped"].includes(job.status) ? <><button className="button button-secondary" type="button" disabled={resend.isPending || !["failed", "sent"].includes(job.delivery?.status ?? "")} onClick={() => resend.mutate()}><Send size={16} />重发通知</button><button className="button button-secondary" type="button" disabled={retry.isPending} onClick={() => retry.mutate()}><RotateCcw size={16} />重新评审</button></> : null
  } /><QueryState loading={query.isLoading} error={query.error} />{(retry.error || resend.error) && <p className="form-error" role="alert">{(retry.error || resend.error)?.message}</p>}
  {job && <><section className="detail-summary"><div><span>评审状态</span><Status value={job.status} /></div><div><span>尝试次数</span><strong>{job.attempts}</strong></div><div><span>创建时间</span><strong>{formatTime(job.created_at)}</strong></div><div><span>完成时间</span><strong>{formatTime(job.finished_at)}</strong></div></section>
    {(job.mr_url || job.commit_url) && <div className="detail-links">{job.mr_url && <a href={job.mr_url} target="_blank" rel="noreferrer">查看 MR <ExternalLink size={14} /></a>}{job.commit_url && <a href={job.commit_url} target="_blank" rel="noreferrer">查看提交 <ExternalLink size={14} /></a>}</div>}
    {job.error && <div className="detail-error" role="alert">{job.error}</div>}
    <section className="section"><div className="section-head"><h2>覆盖情况</h2></div>{coverage ? <div className="coverage-grid"><div><strong>{coverage.selected.length}</strong><span>选中文件</span></div><div><strong>{coverage.completed.length + coverage.reused.length}</strong><span>完成 / 复用</span></div><div><strong>{coverage.failed.length}</strong><span>失败</span></div><div><strong>{coverage.waived.length}</strong><span>豁免</span></div></div> : <p className="empty-inline">尚无 OCR 覆盖结果</p>}</section>
    {job.result?.preview && <section className="section"><div className="section-head"><h2>范围预览</h2><span>{job.result.preview.reviewable_count} 个可审查文件 · {excluded.length} 个排除文件</span></div>{excluded.length ? <div className="table-scroll"><table><thead><tr><th>排除文件</th><th>原因</th></tr></thead><tbody>{excluded.map((file) => <tr key={file.path}><td className="mono">{file.path}</td><td>{file.exclude_reason ?? "未说明"}</td></tr>)}</tbody></table></div> : <p className="empty-inline">没有被排除的文件</p>}</section>}
    <section className="section"><div className="section-head"><h2>评审发现</h2><span>{comments.length} 条</span></div>{comments.length ? <div className="findings">{comments.map((comment, index) => <article className="finding" key={`${comment.path}-${index}`}><div className="finding-meta"><span className="mono">{comment.path}{comment.start_line ? `:${comment.start_line}` : ""}</span><span>{comment.severity ?? "未分级"}</span></div><p>{comment.content}</p></article>)}</div> : <p className="empty-inline">{job.status === "complete" && !coverage?.waived.length ? "评审完成，未发现问题" : "暂无可展示的发现"}</p>}</section>
    <section className="section"><div className="section-head"><h2>飞书通知</h2></div><div className="detail-line"><Status value={job.delivery?.status ?? "未创建"} /><span>尝试 {job.delivery?.attempts ?? 0} 次</span><span>{job.delivery?.sent_at ? formatTime(job.delivery.sent_at) : ""}</span></div>{job.delivery?.error && <p className="form-error">{job.delivery.error}</p>}</section>
    <section className="section"><div className="section-head"><h2>执行记录</h2></div><div className="table-scroll"><table><thead><tr><th>次数</th><th>状态</th><th>结束时间</th><th>诊断</th></tr></thead><tbody>{job.attempt_history.map((attempt) => <tr key={attempt.id}><td>#{attempt.attempt_number}</td><td><Status value={attempt.status} /></td><td>{formatTime(attempt.finished_at)}</td><td className="diagnostic" title={attempt.error ?? ""}>{attempt.error ?? "—"}</td></tr>)}{job.attempt_history.length === 0 && <tr><td colSpan={4} className="empty-row">暂无执行记录</td></tr>}</tbody></table></div></section>
  </>}</div>;
}
