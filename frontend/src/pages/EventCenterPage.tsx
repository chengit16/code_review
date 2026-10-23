/** @description GitLab 事件检索、异常恢复与 MR 时间范围补审的管理入口。 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, RotateCcw, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type { FormEvent } from "react";

import { enqueueMrBackfill, listMrBackfills, retryEvent, searchEvents } from "../api/events";
import type { MrBackfill } from "../api/events";
import { apiRequest } from "../api/client";
import type { Repository } from "../api/types";
import { PageHeader } from "../ui/PageHeader";
import { Pagination } from "../ui/Pagination";
import { QueryState } from "../ui/QueryState";
import { SelectField } from "../ui/SelectField";
import { Status } from "../ui/Status";
import { formatTime } from "../ui/format";

function localDateTime(date: Date) {
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

function toUtc(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) throw new Error("请选择有效的起止时间");
  return date.toISOString();
}

/** 只提交时间范围和项目；任务扫描与外部 API 均留给 Worker。 */
function BackfillForm({ token, repositories }: { token: string; repositories: Repository[] }) {
  const [repositoryId, setRepositoryId] = useState(repositories[0] ? String(repositories[0].id) : "");
  const [since, setSince] = useState(() => localDateTime(new Date(Date.now() - 7 * 86400000)));
  const [until, setUntil] = useState(() => localDateTime(new Date()));
  const [localError, setLocalError] = useState("");
  const client = useQueryClient();
  const create = useMutation({
    mutationFn: () => {
      const start = toUtc(since);
      const end = toUtc(until);
      if (new Date(end).getTime() <= new Date(start).getTime()) {
        throw new Error("结束时间必须晚于起始时间");
      }
      if (new Date(end).getTime() - new Date(start).getTime() > 31 * 86400000) {
        throw new Error("单次补审范围不能超过 31 天");
      }
      return enqueueMrBackfill(token, Number(repositoryId), start, end);
    },
    onSuccess: () => {
      setLocalError("");
      void client.invalidateQueries({ queryKey: ["mr-backfills"] });
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLocalError("");
    if (!repositoryId) {
      setLocalError("请先选择一个已接入项目");
      return;
    }
    try {
      const start = toUtc(since);
      const end = toUtc(until);
      const duration = new Date(end).getTime() - new Date(start).getTime();
      if (duration <= 0) throw new Error("结束时间必须晚于起始时间");
      if (duration > 31 * 86400000) throw new Error("单次补审范围不能超过 31 天");
    } catch (error) {
      setLocalError(error instanceof Error ? error.message : "请选择有效的起止时间");
      return;
    }
    const repository = repositories.find((item) => String(item.id) === repositoryId);
    if (!window.confirm(`为“${repository?.name ?? "所选项目"}”扫描 ${since} 至 ${until} 的已合并 MR？Worker 会在后台逐个核对并创建事件。`)) return;
    create.mutate();
  }

  return <section className="section event-backfill-card">
    <div className="section-head"><h2>按合并时间补审 MR</h2><span>每次最多 31 天</span></div>
    <p className="form-note">系统会在后台扫描指定项目的已合并 MR，并逐个创建事件；此操作不会在页面请求中访问 GitLab。</p>
    <form className="event-backfill-form" onSubmit={submit}>
      <fieldset className="configuration-fields event-backfill-fields" disabled={create.isPending}>
        <SelectField label="项目" value={repositoryId} onValueChange={setRepositoryId}
          options={repositories.map((item) => ({ value: String(item.id), label: item.name }))}
          placeholder="选择项目" required disabled={!repositories.length} />
        <label>起始时间<input type="datetime-local" value={since} onChange={(event) => setSince(event.target.value)} required /></label>
        <label>结束时间<input type="datetime-local" value={until} onChange={(event) => setUntil(event.target.value)} required /></label>
        <button className="button button-primary" disabled={!repositories.length}><Search size={16} />{create.isPending ? "提交中…" : "创建补审申请"}</button>
      </fieldset>
    </form>
    {(localError || create.error) && <p className="form-error" role="alert">{localError || create.error?.message}</p>}
    {create.data && <p className="form-success" role="status">补审申请 #{create.data.id} 已排队；扫描完成后可在事件列表查看新事件。</p>}
  </section>;
}

/** 展示最近申请的真实 Worker 状态，扫描完成不代表对应评审任务已完成。 */
function BackfillHistory({ token }: { token: string }) {
  const query = useQuery({
    queryKey: ["mr-backfills"],
    queryFn: ({ signal }) => listMrBackfills(token, signal),
    refetchInterval: (current) => current.state.data?.some((item) => ["queued", "running"].includes(item.status)) ? 5000 : 30000,
  });
  const labels: Record<MrBackfill["status"], string> = {
    queued: "排队中", running: "扫描中", done: "扫描完成", failed: "失败",
  };
  return <section className="section"><div className="section-head"><h2>补审申请记录</h2><span>{query.data?.length ?? 0} 条</span></div>
    <QueryState loading={query.isLoading} error={query.error} onRetry={() => void query.refetch()} />
    {query.data && <div className="table-scroll responsive-table"><table><thead><tr><th>项目 / 申请</th><th>时间范围</th><th>扫描 / 入队</th><th>状态</th><th>诊断</th></tr></thead><tbody>
      {query.data.map((item) => <tr key={item.id}><td data-label="项目 / 申请">{item.repository_name}<small className="table-sub">申请 #{item.id} · {formatTime(item.created_at)}</small></td><td data-label="时间范围">{formatTime(item.since)} – {formatTime(item.until)}</td><td data-label="扫描 / 入队">{item.scanned} / {item.enqueued} 个 MR</td><td data-label="状态">{labels[item.status]}</td><td data-label="诊断">{item.error ?? "—"}</td></tr>)}
      {query.data.length === 0 && <tr><td colSpan={5} className="empty-row">还没有补审申请</td></tr>}
    </tbody></table></div>}
  </section>;
}

/** URL 保存筛选和分页；只读用户可查询，异常恢复与补审入口仅管理员可用。 */
export function EventCenterPage({ token, canEdit }: {
  /** 内存中的管理口令或会话。 */ token: string;
  /** 只控制写操作界面，服务端仍负责角色授权。 */ canEdit: boolean;
}) {
  const [params, setParams] = useSearchParams();
  const client = useQueryClient();
  const [message, setMessage] = useState("");
  const [repositoryFilter, setRepositoryFilter] = useState(params.get("repository_id") ?? "all");
  const [statusFilter, setStatusFilter] = useState(params.get("status") ?? "all");
  const [filterError, setFilterError] = useState("");
  useEffect(() => {
    setRepositoryFilter(params.get("repository_id") ?? "all");
    setStatusFilter(params.get("status") ?? "all");
  }, [params]);
  const repositories = useQuery({ queryKey: ["repositories"], queryFn: () => apiRequest<Repository[]>(token, "/api/repositories") });
  const events = useQuery({ queryKey: ["event-search", params.toString()], queryFn: ({ signal }) => searchEvents(token, params, signal),
    refetchInterval: (current) => current.state.data?.items.some((item) => ["queued", "running"].includes(item.status)) ? 5000 : 30000 });
  const retry = useMutation({ mutationFn: (id: number) => retryEvent(token, id), onSuccess: (_, id) => {
    setMessage(`事件 #${id} 已重新排队`);
    void client.invalidateQueries({ queryKey: ["event-search"] });
    void client.invalidateQueries({ queryKey: ["overview"] });
  } });
  const items = events.data?.items ?? [];

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    const next = new URLSearchParams();
    const pageSize = params.get("page_size");
    if (pageSize) next.set("page_size", pageSize);
    for (const key of ["repository_id", "status", "mr_iid", "since", "until"]) {
      const value = values.get(key);
      if (typeof value !== "string" || !value || value === "all") continue;
      try {
        next.set(key, key === "since" || key === "until" ? toUtc(value) : value.trim());
      } catch (error) {
        setFilterError(error instanceof Error ? error.message : "筛选时间无效");
        return;
      }
    }
    setFilterError("");
    setMessage("");
    setParams(next);
  }

  function changePage(page: number) {
    const next = new URLSearchParams(params);
    next.set("page", String(page));
    setParams(next);
  }

  return <div className="page event-center-page">
    <PageHeader title="合并事件" subtitle="检查 GitLab 事件处理状态，恢复异常并补扫历史 MR" actions={
      <button className="icon-button" type="button" aria-label="刷新事件" onClick={() => { void events.refetch(); void repositories.refetch(); }}><RefreshCw size={18} /></button>
    } />
    <form className="event-filters section" key={params.toString()} onSubmit={applyFilters}>
      <SelectField label="项目" name="repository_id" value={repositoryFilter}
        onValueChange={setRepositoryFilter}
        options={[{ value: "all", label: "全部项目" }, ...(repositories.data ?? []).map((item) => ({ value: String(item.id), label: item.name }))]} />
      <SelectField label="事件状态" name="status" value={statusFilter}
        onValueChange={setStatusFilter}
        options={[{ value: "all", label: "全部状态" }, ...[["queued", "排队中"], ["running", "处理中"], ["done", "已处理"], ["needs_attention", "需要处理"]].map(([value, label]) => ({ value, label }))]} />
      <label>MR IID<input name="mr_iid" type="number" min="1" defaultValue={params.get("mr_iid") ?? ""} placeholder="全部 MR" /></label>
      <label>起始时间<input name="since" type="datetime-local" defaultValue={toLocal(params.get("since"))} /></label>
      <label>结束时间<input name="until" type="datetime-local" defaultValue={toLocal(params.get("until"))} /></label>
      <div className="filter-actions"><button className="button button-primary"><Search size={16} />查询</button><Link className="button button-secondary" to="/events">清空</Link></div>
    </form>
    {filterError && <p className="form-error" role="alert">{filterError}</p>}
    {canEdit && repositories.data && repositories.data.length > 0 && <BackfillForm key={repositories.data.map((item) => item.id).join(",")} token={token} repositories={repositories.data} />}
    {canEdit && <BackfillHistory token={token} />}
    {message && <p className="form-success" role="status">{message}</p>}
    {(retry.error || repositories.error) && <p className="form-error" role="alert">{retry.error?.message || repositories.error?.message}</p>}
    <section className="section"><div className="section-head"><h2>事件收件箱</h2><span>{events.data?.total ?? 0} 条</span></div>
      <QueryState loading={events.isLoading} error={events.error} onRetry={() => void events.refetch()} />
      {events.data && <div className="table-scroll responsive-table"><table><thead><tr><th>项目 / MR</th><th>提交范围</th><th>状态</th><th>关联任务</th><th>接收时间</th><th>诊断</th><th aria-label="操作" /></tr></thead><tbody>
        {items.map((item) => <tr key={item.id}><td data-label="项目 / MR">{item.repository_name}<small className="table-sub">{item.mr_iid > 0 ? `MR !${item.mr_iid}` : "默认分支 Push"} · 事件 #{item.id}</small></td>
          <td data-label="提交范围" className="mono">{item.mr_iid < 0 ? `${item.squash_sha?.slice(0, 8) ?? "?"}…${item.merge_sha?.slice(0, 8) ?? "?"}` : item.merge_sha?.slice(0, 12) ?? "待 Worker 核验"}</td>
          <td data-label="状态"><Status value={item.status} /><small className="table-sub">尝试 {item.attempts} 次</small></td>
          <td data-label="关联任务">{item.latest_job_id ? <Link to={`/jobs/${item.latest_job_id}`}>查看最新任务 #{item.latest_job_id}</Link> : `${item.job_count ?? 0} 个任务`}</td>
          <td data-label="接收时间">{formatTime(item.created_at)}</td><td data-label="诊断">{item.error ?? "—"}</td>
          <td data-label="操作">{canEdit && item.status === "needs_attention" && <button className="icon-button" type="button" title="重新处理事件" aria-label={`重试事件 ${item.id}`} disabled={retry.isPending} onClick={() => { if (window.confirm(`重新处理事件 #${item.id}？Worker 会重新向 GitLab 核对 MR 和提交范围。`)) retry.mutate(item.id); }}><RotateCcw size={16} /></button>}</td>
        </tr>)}
        {items.length === 0 && <tr><td colSpan={7} className="empty-row">当前条件下没有事件；可尝试清除筛选或创建历史 MR 补审申请。</td></tr>}
      </tbody></table></div>}
    </section>
    <Pagination label="事件分页" total={events.data?.total ?? 0} page={events.data?.page ?? Number(params.get("page") || 1)}
      pageSize={events.data?.page_size ?? Number(params.get("page_size") || 25)} disabled={events.isFetching || Boolean(events.error)}
      onPage={changePage} onPageSize={(size) => { const next = new URLSearchParams(params); next.set("page_size", String(size)); next.delete("page"); setParams(next); }} />
  </div>;
}

function toLocal(value: string | null) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : localDateTime(date);
}
