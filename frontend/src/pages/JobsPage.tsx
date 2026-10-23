/** @description 全量任务检索、显式勾选重审与结果摘要；服务端执行权限和终态校验。 */
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, RefreshCw } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { apiRequest } from "../api/client";
import { searchTasks } from "../api/tasks";
import type { Repository } from "../api/types";
import { MrBatchEnqueue } from "./MrTriggerControls";
import { TaskFilters } from "./TaskFilters";
import { BatchTaskRetry } from "./TaskControls";
import { TaskSelectionBar } from "./TaskSelectionBar";
import { Pagination } from "../ui/Pagination";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { Status } from "../ui/Status";
import { formatCost, formatDuration, formatSeverity, formatTime, shortSha } from "../ui/format";

/** 地址栏变化重建选择范围，浏览器前后退不会复活旧的勾选。 */
export function JobsPage({ token, canEdit = true }: {
  /** 内存中的管理口令。 */ token: string;
  /** 只控制修改动作界面，服务端仍校验角色。 */ canEdit?: boolean;
}) {
  const [params] = useSearchParams();
  return <JobsContent key={params.toString()} token={token} canEdit={canEdit} />;
}

function JobsContent({ token, canEdit }: { token: string; canEdit: boolean }) {
  const [params, setParams] = useSearchParams();
  const [batchPending, setBatchPending] = useState(false);
  const [selected, setSelected] = useState<number[]>([]);
  const jobs = useQuery({ queryKey: ["jobs", "search", params.toString()], queryFn: ({ signal }) => searchTasks(token, params, signal),
    refetchInterval: (query) => query.state.data?.items.some((item) => ["running", "queued"].includes(item.status)) ? 5000 : 30000 });
  const repositories = useQuery({ queryKey: ["repositories"], queryFn: () => apiRequest<Repository[]>(token, "/api/repositories") });
  const items = jobs.data?.items ?? [];
  const selectable = items.filter((item) => ["complete", "partial", "failed", "skipped", "cancelled"].includes(item.status)).map((item) => item.id);
  const targets = selected.filter((id) => selectable.includes(id));
  const page = jobs.data?.page ?? Math.max(1, Number(params.get("page")) || 1);
  function changePage(next: number) { const query = new URLSearchParams(params); query.set("page", String(next)); setParams(query); }
  function quickFilter(value: string) {
    const next = new URLSearchParams(params); next.delete("page"); next.delete("status"); next.delete("view");
    if (["active", "attention", "notification_failed"].includes(value)) next.set("view", value);
    else if (value) next.set("status", value);
    setParams(next);
  }
  function detailPath(id: number) { return `/jobs/${id}${params.size ? `?${params}` : ""}`; }
  return <div className="page"><PageHeader title="评审任务" subtitle="快速定位评审结论、通知状态与待处理异常" actions={
    <button className="icon-button" type="button" aria-label="刷新任务" onClick={() => void jobs.refetch()}><RefreshCw size={18} /></button>
  } />
    <fieldset className="configuration-fields" disabled={batchPending}><div className="quick-filters" aria-label="任务快捷筛选">{[["", "全部任务"], ["active", "排队与运行"], ["attention", "待关注"], ["failed", "失败"], ["partial", "部分完成"], ["notification_failed", "飞书失败"]].map(([value, label]) => <button key={value} className="filter-chip" aria-pressed={(params.get("view") ?? params.get("status") ?? "") === value} onClick={() => quickFilter(value)}>{label}</button>)}</div>
    <TaskFilters key={params.toString()} params={params} repositories={repositories.data ?? []} onApply={setParams} />
    {canEdit && <details className="advanced-panel"><summary>补触发与高级操作</summary><div className="task-command-grid"><MrBatchEnqueue token={token} repositories={repositories.data ?? []} /><BatchTaskRetry token={token} /></div></details>}
    </fieldset><QueryState loading={jobs.isLoading} error={jobs.error || repositories.error} onRetry={() => { void jobs.refetch(); void repositories.refetch(); }} />
    {canEdit && <TaskSelectionBar token={token} ids={targets} disabled={jobs.isFetching || Boolean(jobs.error)} onClear={() => setSelected([])} onAccepted={(accepted) => setSelected((current) => current.filter((id) => !accepted.includes(id)))} onPendingChange={setBatchPending} />}
    <section className="section"><div className="table-scroll responsive-table task-list-table"><table><thead><tr>{canEdit && <th><input className="issue-checkbox" type="checkbox" aria-label="全选本页可重审任务" checked={targets.length > 0 && targets.length === selectable.length} disabled={!selectable.length || jobs.isFetching || batchPending} onChange={(event) => setSelected(event.target.checked ? selectable : [])} /></th>}<th>任务 / 来源</th><th>仓库</th><th>提交</th><th>评审结果</th><th>飞书通知</th><th>耗时 / 尝试</th><th>预估费用</th><th>创建时间</th><th aria-label="操作" /></tr></thead><tbody>
      {items.map((job) => <tr key={job.id}>
        {canEdit && <td data-label="选择"><input className="issue-checkbox" type="checkbox" aria-label={`选择任务 ${job.id}`} checked={targets.includes(job.id)} disabled={!selectable.includes(job.id) || jobs.isFetching || batchPending} onChange={(event) => setSelected(event.target.checked ? [...selected, job.id] : selected.filter((id) => id !== job.id))} /></td>}
        <td data-label="任务 / 来源"><div className="task-mobile-summary">
          <div className="task-mobile-heading"><Link to={detailPath(job.id)}>任务 #{job.id}</Link><Status value={job.status} /></div>
          <strong>{job.repository_name}</strong><small>{job.mr_iid > 0 ? `MR !${job.mr_iid}` : "默认分支 Push"} · {job.target_branch}</small>
          <span>{["queued", "running"].includes(job.status) ? "等待最终结果" : `${job.finding_count ?? 0} 条发现${job.highest_severity ? ` · 最高：${formatSeverity(job.highest_severity)}` : ""}`}</span>
          <details><summary>更多信息</summary><dl><div><dt>提交</dt><dd className="mono">{shortSha(job.commit_sha)}</dd></div><div><dt>飞书通知</dt><dd>{job.delivery_status ? <Status value={job.delivery_status} /> : "未创建"}</dd></div><div><dt>耗时 / 尝试</dt><dd>{formatDuration(job.started_at, job.finished_at)} · {job.attempts} 次</dd></div><div><dt>预估费用</dt><dd className="mono">{formatCost(job.estimated_cost)}</dd></div><div><dt>创建时间</dt><dd>{formatTime(job.created_at)}</dd></div></dl></details>
        </div><div className="task-desktop-summary"><strong>#{job.id}</strong><small className="table-sub">{job.mr_iid > 0 ? `MR !${job.mr_iid}` : "默认分支 Push"}</small></div></td>
        <td data-label="仓库">{job.repository_name}<small className="table-sub">{job.target_branch}</small></td><td data-label="提交" className="mono">{shortSha(job.commit_sha)}</td>
        <td data-label="评审结果"><Status value={job.status} /><small className="table-sub">{["queued", "running"].includes(job.status) ? "等待最终结果" : `${job.finding_count ?? 0} 条发现${job.highest_severity ? ` · 最高：${formatSeverity(job.highest_severity)}` : ""}`}</small></td>
        <td data-label="飞书通知">{job.delivery_status ? <Status value={job.delivery_status} /> : "未创建"}</td><td data-label="耗时 / 尝试">{formatDuration(job.started_at, job.finished_at)}<small className="table-sub">尝试 {job.attempts} 次</small></td><td data-label="预估费用" className="mono">{formatCost(job.estimated_cost)}</td><td data-label="创建时间">{formatTime(job.created_at)}</td><td data-label="操作"><Link className="row-link" to={detailPath(job.id)} aria-label={`查看任务 ${job.id}`}><ArrowUpRight size={16} /></Link></td>
      </tr>)}
      {!jobs.isLoading && !jobs.error && items.length === 0 && <tr><td colSpan={canEdit ? 10 : 9} className="empty-row">当前筛选下没有任务，可清空筛选或检查项目接入。</td></tr>}
    </tbody></table></div></section>
    <Pagination label="任务分页" total={jobs.data?.total ?? 0} page={page} pageSize={jobs.data?.page_size ?? 25} disabled={jobs.isFetching || batchPending || Boolean(jobs.error)} onPage={changePage} onPageSize={(size) => { const next = new URLSearchParams(params); next.set("page_size", String(size)); next.delete("page"); setParams(next); }} />
  </div>;
}
