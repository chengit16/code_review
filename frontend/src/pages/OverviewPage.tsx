/** @description 汇总仓库、评审任务和异常状态。 */

import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, RefreshCw } from "lucide-react";
import { Link } from "react-router-dom";

import { apiRequest } from "../api/client";
import type { Health, Repository, ReviewJob } from "../api/types";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { Status } from "../ui/Status";
import { formatTime, shortSha } from "../ui/format";
import { ReviewEffectivenessSection } from "./ReviewEffectivenessSection";

/** 展示当前队列压力和最近任务；数据始终以服务端状态为准。 */
export function OverviewPage({ token }: { /** 内存中的管理口令。 */ token: string }) {
  // Worker 在 OCR 长任务期间仍持有单实例锁，定期刷新能区分繁忙与进程退出。
  const health = useQuery({ queryKey: ["health"], queryFn: () => apiRequest<Health>(token, "/api/health"), refetchInterval: 5000 });
  const repositories = useQuery({ queryKey: ["repositories"], queryFn: () => apiRequest<Repository[]>(token, "/api/repositories") });
  const jobs = useQuery({ queryKey: ["jobs"], queryFn: () => apiRequest<ReviewJob[]>(token, "/api/jobs"), refetchInterval: 5000 });
  const loading = repositories.isLoading || jobs.isLoading;
  const error = repositories.error || jobs.error;
  const items = jobs.data ?? [];
  const queued = items.filter((item) => item.status === "queued" || item.status === "running").length;
  const exceptions = items.filter((item) => item.status === "failed" || item.status === "partial").length;

  return <div className="page"><PageHeader title="运行概览" subtitle="GitLab 合并评审的当前状态" actions={
    <><div className="worker-health" role="status">Worker <Status value={health.isError ? "unknown" : health.data?.worker ?? "unknown"} /></div><button className="icon-button" type="button" aria-label="刷新概览" title="刷新概览" onClick={() => { void health.refetch(); void repositories.refetch(); void jobs.refetch(); }}><RefreshCw size={18} /></button></>
  } /><QueryState loading={loading} error={error} />{!loading && !error && <>
    <section className="metrics" aria-label="运行指标">
      <div className="metric"><span>已接入仓库</span><strong>{repositories.data?.length ?? 0}</strong><small>个 GitLab 项目</small></div>
      <div className="metric"><span>排队与运行</span><strong>{queued}</strong><small>个逐提交任务</small></div>
      <div className="metric"><span>需要关注</span><strong>{exceptions}</strong><small>个评审任务</small></div>
      <div className="metric"><span>已完成评审</span><strong>{items.filter((item) => item.status === "complete").length}</strong><small>最近 200 个任务</small></div>
    </section>
  </>}
  <ReviewEffectivenessSection token={token} />
  {!loading && !error && <section className="section"><div className="section-head"><h2>最近评审</h2><Link to="/jobs">查看全部 <ArrowUpRight size={15} /></Link></div>
      <div className="table-scroll responsive-table"><table><thead><tr><th>任务</th><th>仓库</th><th>提交</th><th>状态</th><th>创建时间</th><th aria-label="操作" /></tr></thead><tbody>
        {items.slice(0, 8).map((job) => <tr key={job.id}><td data-label="任务">#{job.id}</td><td data-label="仓库">{repositories.data?.find((repo) => repo.id === job.repository_id)?.name ?? `仓库 #${job.repository_id}`}</td><td data-label="提交" className="mono">{shortSha(job.commit_sha)}</td><td data-label="状态"><Status value={job.status} /></td><td data-label="创建时间">{formatTime(job.created_at)}</td><td data-label="操作"><Link className="row-link" to={`/jobs/${job.id}`} aria-label={`查看任务 ${job.id}`}><ArrowUpRight size={16} /></Link></td></tr>)}
        {items.length === 0 && <tr><td colSpan={6} className="empty-row">暂无评审任务</td></tr>}
      </tbody></table></div>
  </section>}</div>;
}
