/** @description 评审任务页编排查询、URL 与当前页选择；不实现 HTTP、调度或服务端授权。 */
import { useQuery } from "@tanstack/react-query";
import { Button, Card, Collapse } from "antd";
import { RefreshCw } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { apiRequest } from "../api/client";
import { searchTasks } from "../api/tasks";
import type { Repository } from "../api/types";
import { PageHeader } from "../ui/PageHeader";
import { ReadFeedback } from "../ui/ReadFeedback";
import { MrBatchEnqueue } from "./MrTriggerControls";
import { TaskFilters } from "./TaskFilters";
import { BatchTaskRetry } from "./TaskControls";
import { TaskSelectionBar } from "./TaskSelectionBar";
import { JobsPagination } from "./jobs/JobsPagination";
import { JobsTable } from "./jobs/JobsTable";

/** URL 变化重建选择，浏览器前后退不会恢复旧勾选；只读用户不展示写入入口。 */
export function JobsPage({ token, canEdit = true }: {
  /** 内存中的管理口令。 */ token: string;
  /** 仅控制修改动作界面，服务端仍校验角色。 */ canEdit?: boolean;
}) {
  const [params] = useSearchParams();
  return <JobsContent key={params.toString()} token={token} canEdit={canEdit} />;
}

function JobsContent({ token, canEdit }: { token: string; canEdit: boolean }) {
  const [params, setParams] = useSearchParams();
  const [batchPending, setBatchPending] = useState(false);
  const [selected, setSelected] = useState<number[]>([]);
  // 活跃初审或补审短轮询，其余任务低频刷新；查询键隔离每组 URL 条件。
  const jobs = useQuery({ queryKey: ["jobs", "search", params.toString()], queryFn: ({ signal }) => searchTasks(token, params, signal),
    refetchInterval: (query) => query.state.data?.items.some((item) => ["running", "queued"].includes(item.status) || Boolean(item.active_recovery_id)) ? 5000 : 30000 });
  const repositories = useQuery({ queryKey: ["repositories"], queryFn: ({ signal }) => apiRequest<Repository[]>(token, "/api/repositories", { signal }) });
  const items = jobs.data?.items ?? [];
  const selectable = items.filter((item) => ["complete", "partial", "failed", "skipped", "cancelled"].includes(item.status) && !item.active_recovery_id).map((item) => item.id);
  const targets = selected.filter((id) => selectable.includes(id));
  const page = jobs.data?.page ?? Math.max(1, Number(params.get("page")) || 1);
  const pageSize = jobs.data?.page_size ?? Number(params.get("page_size") || 25);
  function applyFilters(next: URLSearchParams) {
    if (batchPending) return;
    // 路由过渡可能在返回时被取消，不能仅依赖 key 重挂载清除旧选择。
    setSelected([]);
    setParams(next);
  }
  function changePage(next: number) { const query = new URLSearchParams(params); query.set("page", String(next)); applyFilters(query); }
  function quickFilter(value: string) {
    const next = new URLSearchParams(params); next.delete("page"); next.delete("status"); next.delete("view");
    if (["active", "attention", "notification_failed"].includes(value)) next.set("view", value);
    else if (value) next.set("status", value);
    applyFilters(next);
  }
  function detailPath(id: number) { return `/jobs/${id}${params.size ? `?${params}` : ""}`; }
  return <div className="page jobs-migration"><PageHeader title="评审任务" subtitle="先看评审结论，再核对通知、耗时与费用。批量操作仅限当前页。" actions={
    <Button aria-label="刷新任务" icon={<RefreshCw size={18} />} disabled={batchPending} loading={jobs.isFetching} onClick={() => void jobs.refetch()}>刷新</Button>
  } />
    <Card size="small" className="jobs-search-card">
      <div className="jobs-quick-filters" aria-label="任务快捷筛选">{[["", "全部任务"], ["active", "排队与运行"], ["attention", "待关注"], ["failed", "失败"], ["partial", "部分完成"], ["notification_failed", "飞书失败"]].map(([value, label]) => <Button key={value} size="small" type={(params.get("view") ?? params.get("status") ?? "") === value ? "primary" : "default"} aria-pressed={(params.get("view") ?? params.get("status") ?? "") === value} disabled={batchPending} onClick={() => quickFilter(value)}>{label}</Button>)}</div>
      <TaskFilters params={params} repositories={repositories.data ?? []} repositoriesKnown={repositories.isSuccess} disabled={batchPending} onApply={applyFilters} />
      <ReadFeedback name="项目筛选" loading={repositories.isPending} error={repositories.error} onRetry={() => void repositories.refetch()} />
    </Card>
    <ReadFeedback name="任务" loading={false} error={jobs.error} onRetry={() => void jobs.refetch()} />
    {canEdit && <TaskSelectionBar token={token} ids={targets} disabled={jobs.isFetching || Boolean(jobs.error)} onClear={() => setSelected([])} onAccepted={(accepted) => setSelected((current) => current.filter((id) => !accepted.includes(id)))} onPendingChange={setBatchPending} />}
    <JobsTable items={items} canEdit={canEdit} selectable={selectable} targets={targets} disabled={jobs.isFetching || batchPending || Boolean(jobs.error)} onSelect={setSelected} detailPath={detailPath} loading={jobs.isPending} failed={Boolean(jobs.error)} />
    <JobsPagination total={jobs.isSuccess ? jobs.data.total : undefined} page={page} pageSize={pageSize} disabled={jobs.isFetching || batchPending || Boolean(jobs.error)} onPage={changePage} onPageSize={(size) => { const next = new URLSearchParams(params); next.set("page_size", String(size)); next.delete("page"); applyFilters(next); }} />
    {canEdit && <Collapse className="jobs-commands" items={[{ key: "commands", label: "补触发与高级操作", children: <fieldset className="configuration-fields" disabled={batchPending || !repositories.isSuccess}><div className="task-command-grid"><MrBatchEnqueue token={token} repositories={repositories.data ?? []} /><BatchTaskRetry token={token} /></div></fieldset> }]} />}
  </div>;
}
