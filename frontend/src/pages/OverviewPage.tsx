/** @description 全量运行聚合与最近任务；未恢复异常和历史失败分开，不把截断列表当成队列总量。 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUpRight, RefreshCw } from "lucide-react";
import { Link } from "react-router-dom";

import { apiRequest } from "../api/client";
import type { Health, ReviewJob } from "../api/types";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { Status } from "../ui/Status";
import { formatTime, shortSha } from "../ui/format";
import { ReviewEffectivenessSection } from "./ReviewEffectivenessSection";

interface Overview {
  summary: { repositories: number; queued: number; running: number; complete: number;
    attention: number; historical_failed: number; notification_failed: number; total: number };
  recent: ReviewJob[];
}

/** 首页只读展示；点击指标直接进入相同口径的筛选列表。 */
export function OverviewPage({ token }: { /** 内存中的管理口令。 */ token: string }) {
  const client = useQueryClient();
  const health = useQuery({ queryKey: ["health"], queryFn: () => apiRequest<Health>(token, "/api/health"), refetchInterval: 10000 });
  const overview = useQuery({ queryKey: ["overview"], queryFn: () => apiRequest<Overview>(token, "/api/overview"),
    refetchInterval: (query) => query.state.data?.summary.running || query.state.data?.summary.queued ? 5000 : 30000 });
  const summary = overview.data?.summary;
  function refresh() {
    void health.refetch();
    void overview.refetch();
    void client.invalidateQueries({ queryKey: ["review-effectiveness"] });
  }
  return <div className="page"><PageHeader title="运行概览" subtitle="先看当前待办，再查看评审结果" actions={
    <><div className="worker-health" role="status">Worker <Status value={health.isError ? "unknown" : health.data?.worker ?? "unknown"} /></div><button className="icon-button" aria-label="刷新概览" onClick={refresh}><RefreshCw size={18} /></button></>
  } /><QueryState loading={overview.isLoading} error={overview.error} onRetry={() => void overview.refetch()} />
    {health.data?.worker === "stopped" && <p className="attention-note" role="alert">Worker 未运行，已接收任务会等待处理。请先启动 Worker，不要反复重新评审。</p>}
    {summary && <><section className="metrics" aria-label="运行指标">
      <Link to="/repositories" className="metric metric-link"><span>已接入仓库</span><strong>{summary.repositories}</strong><small>查看项目接入状态 →</small></Link>
      <Link to="/jobs?view=active" className="metric metric-link"><span>排队与运行</span><strong>{summary.queued + summary.running}</strong><small>排队 {summary.queued} · 运行 {summary.running}</small></Link>
      <Link to="/jobs?view=attention" className="metric metric-link"><span>待关注评审</span><strong>{summary.attention}</strong><small>失败或部分完成，未被后续完整结果覆盖</small></Link>
      <Link to="/jobs?status=complete" className="metric metric-link"><span>已完成评审</span><strong>{summary.complete}</strong><small>全部 {summary.total} 个历史任务</small></Link>
    </section><div className="overview-links"><span>失败任务 {summary.historical_failed} 条（含历史记录），不等于当前待办</span><Link to="/jobs?view=notification_failed">飞书发送失败 {summary.notification_failed} 条 · 查看并重发 →</Link></div></>}
    <ReviewEffectivenessSection token={token} />
    {overview.data && <section className="section"><div className="section-head"><h2>最近评审</h2><Link to="/jobs">查看全部 <ArrowUpRight size={15} /></Link></div>
      <div className="table-scroll responsive-table"><table><thead><tr><th>任务</th><th>仓库 / 来源</th><th>提交</th><th>状态</th><th>创建时间</th><th aria-label="操作" /></tr></thead><tbody>
        {overview.data.recent.map((job) => <tr key={job.id}><td data-label="任务">#{job.id}</td><td data-label="仓库 / 来源">{job.repository_name}<small className="table-sub">{job.mr_iid > 0 ? `MR !${job.mr_iid}` : "默认分支 Push"}</small></td><td data-label="提交" className="mono">{shortSha(job.commit_sha)}</td><td data-label="状态"><Status value={job.status} /></td><td data-label="创建时间">{formatTime(job.created_at)}</td><td data-label="操作"><Link className="row-link" to={`/jobs/${job.id}`} aria-label={`查看任务 ${job.id}`}><ArrowUpRight size={16} /></Link></td></tr>)}
        {overview.data.recent.length === 0 && <tr><td colSpan={6} className="empty-row">暂无任务，先在项目配置中完成接入。</td></tr>}
      </tbody></table></div>
    </section>}
  </div>;
}
