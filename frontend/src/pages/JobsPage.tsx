/** @description 逐提交评审任务列表与状态筛选。 */

import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, RefreshCw } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { apiRequest } from "../api/client";
import type { Repository, ReviewJob } from "../api/types";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { SelectField } from "../ui/SelectField";
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
  } /><div className="filter-bar"><SelectField label="状态" value={filter} onValueChange={setFilter} options={[{ value: "all", label: "全部状态" }, { value: "queued", label: "排队中" }, { value: "running", label: "运行中" }, { value: "complete", label: "已完成" }, { value: "partial", label: "部分完成" }, { value: "failed", label: "失败" }, { value: "skipped", label: "已跳过" }]} /><span>{items.length} 个任务</span></div>
  <QueryState loading={jobs.isLoading} error={jobs.error} /><section className="section"><div className="table-scroll responsive-table"><table><thead><tr><th>任务</th><th>仓库</th><th>来源</th><th>提交</th><th>状态</th><th>尝试</th><th>创建时间</th><th aria-label="操作" /></tr></thead><tbody>
    {items.map((job) => <tr key={job.id}><td data-label="任务" className="mono">#{job.id}</td><td data-label="仓库">{repositories.data?.find((repo) => repo.id === job.repository_id)?.name ?? `仓库 #${job.repository_id}`}</td><td data-label="来源">{job.mr_iid < 0 ? "默认分支 Push" : `MR !${job.mr_iid}`}</td><td data-label="提交" className="mono">{shortSha(job.commit_sha)}</td><td data-label="状态"><Status value={job.status} /></td><td data-label="尝试">{job.attempts}</td><td data-label="创建时间">{formatTime(job.created_at)}</td><td data-label="操作"><Link className="row-link" to={`/jobs/${job.id}`} aria-label={`查看任务 ${job.id}`}><ArrowUpRight size={16} /></Link></td></tr>)}
    {items.length === 0 && <tr><td colSpan={8} className="empty-row">当前筛选下没有任务</td></tr>}
  </tbody></table></div></section></div>;
}
