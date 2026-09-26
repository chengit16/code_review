/** @description 查看 GitLab 行内评论的独立结果和重试；飞书状态保持分离。 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { RotateCcw, Send } from "lucide-react";

import { apiRequest } from "../api/client";
import type { ReviewJobDetail } from "../api/types";
import { Status } from "../ui/Status";

/** 旧任务可主动准备评论，失败与不可定位结果逐条重试。 */
export function GitLabPublications({ token, job }: {
  /** 内存口令。 */ token: string;
  /** 已鉴权的任务详情。 */ job: ReviewJobDetail;
}) {
  const client = useQueryClient();
  const refresh = () => void client.invalidateQueries({ queryKey: ["job", String(job.id)] });
  const prepare = useMutation({ mutationFn: () => apiRequest(token, `/api/jobs/${job.id}/gitlab-publications/prepare`, { method: "POST" }), onSuccess: refresh });
  const retry = useMutation({ mutationFn: (id: number) => apiRequest(token, `/api/gitlab-publications/${id}/retry`, { method: "POST" }), onSuccess: refresh });
  if (job.mr_iid < 1 || !["complete", "partial"].includes(job.status)) return null;
  return <section className="section"><div className="section-head"><h2>GitLab 行内评论</h2><button className="button button-secondary" disabled={prepare.isPending} onClick={() => prepare.mutate()}><Send size={16} />准备发布</button></div>{(prepare.error || retry.error) && <p role="alert" className="form-error">{(prepare.error || retry.error)?.message}</p>}{job.publications?.length ? <div className="table-scroll"><table><thead><tr><th>发现</th><th>尝试</th><th>状态</th><th>诊断</th><th aria-label="操作" /></tr></thead><tbody>{job.publications.map((item) => <tr key={item.id}><td>#{item.comment_index + 1}</td><td>第 {item.attempt_number} 次</td><td><Status value={item.status} /></td><td>{item.error ?? "—"}</td><td>{["failed", "skipped"].includes(item.status) && <button className="icon-button" title="重试行内评论" aria-label={`重试行内评论 ${item.id}`} disabled={retry.isPending} onClick={() => retry.mutate(item.id)}><RotateCcw size={16} /></button>}</td></tr>)}</tbody></table></div> : <p className="empty-inline">暂无行内发布记录</p>}</section>;
}
