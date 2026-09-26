/** @description 查看 GitLab MR 合并与默认分支 Push 的接收状态。 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, RotateCcw } from "lucide-react";

import { apiRequest } from "../api/client";
import type { MergeEvent, Repository } from "../api/types";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { Status } from "../ui/Status";
import { formatTime, shortSha } from "../ui/format";

/** 逐条展示收到的 GitLab 事件及无法确认提交范围的原因。 */
export function EventsPage({ token }: { /** 内存中的管理口令。 */ token: string }) {
  const queryClient = useQueryClient();
  const events = useQuery({ queryKey: ["events"], queryFn: () => apiRequest<MergeEvent[]>(token, "/api/events"), refetchInterval: 5000 });
  const repositories = useQuery({ queryKey: ["repositories"], queryFn: () => apiRequest<Repository[]>(token, "/api/repositories") });
  const retry = useMutation({
    mutationFn: (id: number) => apiRequest<unknown>(token, `/api/events/${id}/retry`, { method: "POST" }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["events"] }),
  });
  return <div className="page"><PageHeader title="GitLab 事件" subtitle="Webhook 收件箱" actions={
    <button className="icon-button" type="button" aria-label="刷新事件" title="刷新事件" onClick={() => void events.refetch()}><RefreshCw size={18} /></button>
  } /><QueryState loading={events.isLoading} error={events.error} />{retry.error && <p className="form-error" role="alert">{retry.error.message}</p>}<section className="section"><div className="table-scroll"><table><thead><tr><th>事件</th><th>仓库</th><th>来源</th><th>提交</th><th>状态</th><th>接收时间</th><th>诊断</th><th aria-label="操作" /></tr></thead><tbody>
    {events.data?.map((event) => <tr key={event.id}><td className="mono">#{event.id}</td><td>{repositories.data?.find((repo) => repo.id === event.repository_id)?.name ?? `仓库 #${event.repository_id}`}</td><td>{event.mr_iid < 0 ? "默认分支 Push" : `MR !${event.mr_iid}`}</td><td className="mono">{shortSha(event.merge_sha ?? event.squash_sha)}</td><td><Status value={event.status} /></td><td>{formatTime(event.created_at)}</td><td className="diagnostic" title={event.error ?? ""}>{event.error ?? "—"}</td><td>{event.status === "needs_attention" && <button className="icon-button" type="button" title="重试事件" aria-label={`重试事件 ${event.id}`} disabled={retry.isPending} onClick={() => retry.mutate(event.id)}><RotateCcw size={16} /></button>}</td></tr>)}
    {events.data?.length === 0 && <tr><td colSpan={8} className="empty-row">尚无事件</td></tr>}
  </tbody></table></div></section></div>;
}
