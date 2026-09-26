/** @description 逐提交评审任务列表与状态筛选。 */

import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, RefreshCw } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { apiRequest } from "../api/client";
import type { Repository, ReviewJob } from "../api/types";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { Status } from "../ui/Status";
import { formatTime, shortSha } from "../ui/format";

/** 按运行状态筛选最近任务，不把失败或部分覆盖隐藏在完成数量内。 */
export function JobsPage({ token }: { /** 内存中的管理口令。 */ token: string }) {
  const [filter, setFilter] = useState("all");
  const jobs = useQuery({ queryKey: ["jobs"], queryFn: () => apiRequest<ReviewJob[]>(token, "/api/jobs"), refetchInterval: 5000 });
  const repositories = useQuery({ queryKey: ["repositories"], queryFn: () => apiRequest<Repository[]>(token, "/api/repositories") });
  const items = (jobs.data ?? []).filter((job) => filter === "all" || job.status === filter);
  return <div className="page"><PageHeader title="评审任务" subtitle="按提交查看 OCR 执行结果" actions={
    <button className="icon-button" type="button" aria-label="刷新任务" title="刷新任务" onClick={() => void jobs.refetch()}><RefreshCw size={18} /></button>
  } /><div className="filter-bar"><label htmlFor="job-status">状态</label><select id="job-status" value={filter} onChange={(event) => setFilter(event.target.value)}><option value="all">全部状态</option><option value="queued">排队中</option><option value="running">运行中</option><option value="complete">已完成</option><option value="partial">部分完成</option><option value="failed">失败</option><option value="skipped">已跳过</option></select><span>{items.length} 个任务</span></div>
  <QueryState loading={jobs.isLoading} error={jobs.error} /><section className="section"><div className="table-scroll"><table><thead><tr><th>任务</th><th>仓库</th><th>MR</th><th>提交</th><th>状态</th><th>尝试</th><th>创建时间</th><th aria-label="操作" /></tr></thead><tbody>
    {items.map((job) => <tr key={job.id}><td className="mono">#{job.id}</td><td>{repositories.data?.find((repo) => repo.id === job.repository_id)?.name ?? `仓库 #${job.repository_id}`}</td><td>!{job.mr_iid}</td><td className="mono">{shortSha(job.commit_sha)}</td><td><Status value={job.status} /></td><td>{job.attempts}</td><td>{formatTime(job.created_at)}</td><td><Link className="row-link" to={`/jobs/${job.id}`} aria-label={`查看任务 ${job.id}`}><ArrowUpRight size={16} /></Link></td></tr>)}
    {items.length === 0 && <tr><td colSpan={8} className="empty-row">当前筛选下没有任务</td></tr>}
  </tbody></table></div></section></div>;
}
