/** @description 查看 GitLab 事件，并在 webhook 漏投时补触发已合并 MR。 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, RefreshCw, RotateCcw, X } from "lucide-react";
import { useState } from "react";

import { apiRequest } from "../api/client";
import type { MergeEvent, Repository } from "../api/types";
import { Modal } from "../ui/Modal";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { SelectField } from "../ui/SelectField";
import { Status } from "../ui/Status";
import { formatTime, shortSha } from "../ui/format";

/** 逐条展示收到的 GitLab 事件及无法确认提交范围的原因。 */
export function EventsPage({ token }: { /** 内存中的管理口令。 */ token: string }) {
  const queryClient = useQueryClient();
  const events = useQuery({ queryKey: ["events"], queryFn: () => apiRequest<MergeEvent[]>(token, "/api/events"), refetchInterval: 5000 });
  const repositories = useQuery({ queryKey: ["repositories"], queryFn: () => apiRequest<Repository[]>(token, "/api/repositories") });
  const [manualOpen, setManualOpen] = useState(false);
  const [manualRepository, setManualRepository] = useState("");
  const [manualMrIid, setManualMrIid] = useState("");
  const [feedback, setFeedback] = useState("");
  const retry = useMutation({
    mutationFn: (id: number) => apiRequest<unknown>(token, `/api/events/${id}/retry`, { method: "POST" }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["events"] }),
  });
  // 漏投补救只建立事件，Worker 仍会向 GitLab 确认 MR 已合并。
  const enqueue = useMutation({
    mutationFn: () => apiRequest<{ status: string }>(token, `/api/repositories/${manualRepository}/mrs/${Number(manualMrIid)}/enqueue`, { method: "POST" }),
    onSuccess: () => {
      setManualOpen(false);
      setManualRepository("");
      setManualMrIid("");
      setFeedback("已加入事件队列");
      void queryClient.invalidateQueries({ queryKey: ["events"] });
    },
  });
  const enabledRepositories = repositories.data?.filter((repo) => Boolean(repo.enabled)) ?? [];

  return <div className="page"><PageHeader title="GitLab 事件" subtitle="Webhook 收件箱" actions={
    <><button className="button button-secondary" type="button" disabled={!enabledRepositories.length} title={enabledRepositories.length ? "补触发已合并 MR" : "没有可用仓库"} onClick={() => { setFeedback(""); enqueue.reset(); setManualOpen(true); }}><Plus size={16} />补触发 MR</button><button className="icon-button" type="button" aria-label="刷新事件" title="刷新事件" onClick={() => void events.refetch()}><RefreshCw size={18} /></button></>
  } /><QueryState loading={events.isLoading} error={events.error} />{feedback && <p className="form-success" role="status">{feedback}</p>}{retry.error && <p className="form-error" role="alert">{retry.error.message}</p>}<section className="section"><div className="table-scroll responsive-table"><table><thead><tr><th>事件</th><th>仓库</th><th>来源</th><th>提交</th><th>状态</th><th>接收时间</th><th>诊断</th><th aria-label="操作" /></tr></thead><tbody>
    {events.data?.map((event) => <tr key={event.id}><td data-label="事件" className="mono">#{event.id}</td><td data-label="仓库">{repositories.data?.find((repo) => repo.id === event.repository_id)?.name ?? `仓库 #${event.repository_id}`}</td><td data-label="来源">{event.mr_iid < 0 ? "默认分支 Push" : `MR !${event.mr_iid}`}</td><td data-label="提交" className="mono">{shortSha(event.merge_sha ?? event.squash_sha)}</td><td data-label="状态"><Status value={event.status} /></td><td data-label="接收时间">{formatTime(event.created_at)}</td><td data-label="诊断" className="diagnostic" title={event.error ?? ""}>{event.error ?? "—"}</td><td data-label="操作">{event.status === "needs_attention" && <button className="icon-button" type="button" title="重试事件" aria-label={`重试事件 ${event.id}`} disabled={retry.isPending} onClick={() => retry.mutate(event.id)}><RotateCcw size={16} /></button>}</td></tr>)}
    {events.data?.length === 0 && <tr><td colSpan={8} className="empty-row">尚无事件</td></tr>}
  </tbody></table></div></section>
  {manualOpen && <Modal titleId="enqueue-mr-title" onClose={() => setManualOpen(false)}><div className="modal-heading"><h2 id="enqueue-mr-title">补触发已合并 MR</h2><button className="icon-button" type="button" aria-label="关闭" title="关闭" onClick={() => setManualOpen(false)}><X size={19} /></button></div>
    <form className="form-grid" onSubmit={(event) => { event.preventDefault(); enqueue.mutate(); }}>
      <SelectField label="仓库" name="repository" value={manualRepository} onValueChange={setManualRepository} placeholder="选择仓库" required options={enabledRepositories.map((repo) => ({ value: String(repo.id), label: repo.name }))} />
      <label>MR IID<input type="number" min="1" step="1" value={manualMrIid} onChange={(event) => setManualMrIid(event.target.value)} required /></label>
      {enqueue.error && <p className="form-error wide" role="alert">{enqueue.error.message}</p>}
      <div className="form-actions wide"><button className="button button-secondary" type="button" onClick={() => setManualOpen(false)}>取消</button><button className="button button-primary" type="submit" disabled={enqueue.isPending || !manualRepository}>加入事件队列</button></div>
    </form>
  </Modal>}</div>;
}
