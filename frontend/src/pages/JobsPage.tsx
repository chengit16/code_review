/** @description 逐提交评审任务列表与状态筛选。 */

import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, ChevronLeft, ChevronRight, RefreshCw } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";

import { apiRequest } from "../api/client";
import { searchTasks } from "../api/tasks";
import type { Repository } from "../api/types";
import { TaskFilters } from "./TaskFilters";
import { BatchTaskRetry } from "./TaskControls";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { Status } from "../ui/Status";
import { formatTime, shortSha } from "../ui/format";

/** 筛选与页码保留在地址栏，查询键隔离不同搜索条件的结果。 */
export function JobsPage({ token, canEdit = true }: {
  /** 内存中的管理口令。 */ token: string;
  /** 只控制批量操作界面；服务端仍执行角色授权。 */ canEdit?: boolean;
}) {
  const [params, setParams] = useSearchParams();
  const jobs = useQuery({ queryKey: ["jobs", "search", params.toString()], queryFn: ({ signal }) => searchTasks(token, params, signal), refetchInterval: 5000 });
  const repositories = useQuery({ queryKey: ["repositories"], queryFn: () => apiRequest<Repository[]>(token, "/api/repositories") });
  const items = jobs.data?.items ?? [];
  const page = jobs.data?.page ?? Math.max(1, Number(params.get("page")) || 1);
  const pages = Math.max(1, Math.ceil((jobs.data?.total ?? 0) / (jobs.data?.page_size ?? 25)));
  function changePage(next: number) { const query = new URLSearchParams(params); query.set("page", String(next)); setParams(query); }
  return <div className="page"><PageHeader title="评审任务" subtitle="按提交查看 OCR 执行结果" actions={
    <button className="icon-button" type="button" aria-label="刷新任务" title="刷新任务" onClick={() => void jobs.refetch()}><RefreshCw size={18} /></button>
  } />{canEdit && <BatchTaskRetry token={token} />}<TaskFilters key={params.toString()} params={params} repositories={repositories.data ?? []} onApply={setParams} />
  <QueryState loading={jobs.isLoading} error={jobs.error} /><section className="section"><div className="table-scroll responsive-table"><table><thead><tr><th>任务</th><th>仓库</th><th>来源</th><th>提交</th><th>状态</th><th>尝试</th><th>创建时间</th><th aria-label="操作" /></tr></thead><tbody>
    {items.map((job) => <tr key={job.id}><td data-label="任务" className="mono">#{job.id}</td><td data-label="仓库">{job.repository_name}<small className="table-sub">{job.target_branch}</small></td><td data-label="来源">{job.mr_iid < 0 ? "默认分支 Push" : `MR !${job.mr_iid}`}</td><td data-label="提交" className="mono">{shortSha(job.commit_sha)}</td><td data-label="状态"><Status value={job.status} /></td><td data-label="尝试">{job.attempts}</td><td data-label="创建时间">{formatTime(job.created_at)}</td><td data-label="操作"><Link className="row-link" to={`/jobs/${job.id}${params.size ? `?${params}` : ""}`} aria-label={`查看任务 ${job.id}`}><ArrowUpRight size={16} /></Link></td></tr>)}
    {items.length === 0 && <tr><td colSpan={8} className="empty-row">当前筛选下没有任务</td></tr>}
  </tbody></table></div></section><div className="pagination" aria-label="任务分页"><span aria-live="polite">共 {jobs.data?.total ?? 0} 条 · 第 {page} / {pages} 页</span><button className="icon-button" aria-label="上一页" title="上一页" disabled={page <= 1 || jobs.isFetching} onClick={() => changePage(page - 1)}><ChevronLeft size={18} /></button><button className="icon-button" aria-label="下一页" title="下一页" disabled={page >= pages || jobs.isFetching} onClick={() => changePage(page + 1)}><ChevronRight size={18} /></button></div></div>;
}
