/** @description 汇总运行指标、异常与旧工件维护；所有数字来自服务端。 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, RefreshCw, Trash2 } from "lucide-react";
import { useState } from "react";

import { apiRequest } from "../api/client";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { formatTime } from "../ui/format";
import { ServiceAddresses } from "./ServiceAddresses";
import { AlertsPanel } from "./AlertsPanel";

interface Snapshot {
  jobs: Record<string, number>; events: Record<string, number>;
  deliveries: Record<string, number>; retry_count: number;
  average_review_seconds: number; review_count_7d: number;
  oldest_pending_at: string | null; disk_free_bytes: number;
  backup: { last_at: string | null; healthy: boolean; age_seconds: number | null };
  alerts: string[];
}

/** 清理必须先展示服务端候选数量，并在二次确认后重新核算范围。 */
export function OperationsPage({ token }: { /** 内存中的管理口令。 */ token: string }) {
  const [days, setDays] = useState(90);
  const [message, setMessage] = useState("");
  const queryClient = useQueryClient();
  const metrics = useQuery({ queryKey: ["operations"], queryFn: () => apiRequest<Snapshot>(token, "/api/operations"), refetchInterval: 30000 });
  const preview = useQuery({ queryKey: ["maintenance-preview", days], queryFn: () => apiRequest<{ count: number; bytes: number }>(token, `/api/maintenance/preview?days=${days}`) });
  const prune = useMutation({ mutationFn: () => apiRequest<{ count: number; bytes: number }>(token, `/api/maintenance/prune?days=${days}`, { method: "POST" }), onSuccess: (result) => { setMessage(`已清理 ${result.count} 个旧工件目录`); void queryClient.invalidateQueries({ queryKey: ["maintenance-preview"] }); void queryClient.invalidateQueries({ queryKey: ["operations"] }); } });
  const data = metrics.data;
  return <div className="page"><PageHeader title="运行监控" subtitle="队列、通知、备份与存储" actions={<button className="icon-button" title="刷新监控" aria-label="刷新监控" onClick={() => { void metrics.refetch(); void preview.refetch(); }}><RefreshCw size={18} /></button>} />
    <QueryState loading={metrics.isLoading} error={metrics.error} />
    {data && <><section className="metrics" aria-label="运行指标">
      <div className="metric"><span>排队 / 运行</span><strong>{(data.jobs.queued ?? 0) + (data.jobs.running ?? 0)}</strong><small>最早 {formatTime(data.oldest_pending_at)}</small></div>
      <div className="metric"><span>评审异常</span><strong>{(data.jobs.failed ?? 0) + (data.jobs.partial ?? 0)}</strong><small>失败与部分覆盖</small></div>
      <div className="metric"><span>平均耗时</span><strong>{data.average_review_seconds} 秒</strong><small>近 7 天 {data.review_count_7d} 次</small></div>
      <div className="metric"><span>重试 / 通知失败</span><strong>{data.retry_count} / {data.deliveries.failed ?? 0}</strong><small>累计任务重试与飞书异常</small></div>
    </section><section className="section"><div className="section-head"><h2>运行异常</h2><span>{data.alerts.length} 项</span></div>{data.alerts.length ? <ul className="operation-alerts">{data.alerts.map((alert) => <li key={alert}><AlertTriangle size={16} />{alert}</li>)}</ul> : <p className="empty-inline">当前没有达到告警阈值的项目</p>}</section>
    <section className="section"><div className="section-head"><h2>存储与备份</h2></div><div className="operation-facts"><div><span>可用空间</span><strong>{(data.disk_free_bytes / 1024 ** 3).toFixed(1)} GB</strong></div><div><span>最近成对备份</span><strong>{formatTime(data.backup.last_at)}</strong></div><div><span>完整性</span><strong>{data.backup.healthy ? "已通过" : "待检查"}</strong></div></div></section></>}
    <section className="section"><div className="section-head"><h2>旧评审工件</h2></div><div className="maintenance-bar"><label>保留天数<input type="number" min="7" max="3650" value={days} onChange={(event) => setDays(Math.max(7, Math.min(3650, Number(event.target.value) || 7)))} /></label><span>{preview.data ? `${preview.data.count} 个目录 · ${(preview.data.bytes / 1024 ** 2).toFixed(1)} MB` : "计算中"}</span><button className="button button-secondary" disabled={!preview.data?.count || prune.isPending} onClick={() => { if (window.confirm(`清理 ${preview.data?.count} 个超过 ${days} 天的终态评审工件？任务和报告摘要会保留。`)) prune.mutate(); }}><Trash2 size={16} />清理工件</button></div>{message && <p className="form-success" role="status">{message}</p>}<QueryState loading={preview.isLoading} error={preview.error || prune.error} /></section>
    <ServiceAddresses token={token} />
    <AlertsPanel token={token} />
  </div>;
}
