/** @description 按项目跟进评审发现，原始出现记录与人工处理状态分开显示。 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUpRight, ChevronLeft, ChevronRight, RefreshCw } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { apiRequest } from "../api/client";
import type { Repository } from "../api/types";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { SelectField } from "../ui/SelectField";
import { formatCategory, formatSeverity, formatTime, shortSha } from "../ui/format";

type IssueStatus = "open" | "fixed" | "ignored" | "merged";

interface ReviewIssue {
  id: number;
  repository_id: number;
  repository_name: string;
  status: IssueStatus;
  path: string;
  content: string;
  severity: string | null;
  category: string | null;
  first_seen_at: string;
  last_seen_at: string;
  closed_at: string | null;
  occurrence_count: number;
  merged_into_id: number | null;
}

interface IssueDetail extends ReviewIssue {
  occurrences: Array<{ id: number; job_id: number; attempt_number: number; mr_iid: number; commit_sha: string; path: string; start_line: number | null; created_at: string }>;
  events: Array<{ id: number; old_status: string | null; new_status: string; actor: string; note: string | null; created_at: string }>;
}

const labels: Record<IssueStatus, string> = {
  open: "待处理", fixed: "已修复", ignored: "已忽略", merged: "已合并",
};

/** 筛选保留在地址栏，详情仍能从不同来源直接定位到问题。 */
export function ReviewIssuesPage({ token, canEdit }: {
  /** 内存会话令牌。 */ token: string;
  /** 服务端权限之外的操作显示控制。 */ canEdit: boolean;
}) {
  const [params, setParams] = useSearchParams();
  const [note, setNote] = useState("");
  const [mergeTarget, setMergeTarget] = useState("");
  const queryClient = useQueryClient();
  const selectedId = Number(params.get("issue")) || null;
  const page = Math.max(1, Number(params.get("page")) || 1);
  const repositoryId = params.get("repository_id") ?? "";
  const status = params.get("status") ?? "open";
  const severity = params.get("severity") ?? "";
  const query = new URLSearchParams({ page: String(page) });
  if (repositoryId) query.set("repository_id", repositoryId);
  if (status) query.set("status", status);
  if (severity) query.set("severity", severity);
  const issues = useQuery({
    queryKey: ["review-issues", query.toString()],
    queryFn: () => apiRequest<{ items: ReviewIssue[]; total: number; page_size: number }>(token, `/api/review-issues?${query}`),
    refetchInterval: 15000,
  });
  const detail = useQuery({
    queryKey: ["review-issue", selectedId],
    queryFn: () => apiRequest<IssueDetail>(token, `/api/review-issues/${selectedId}`),
    enabled: selectedId !== null,
  });
  const repositories = useQuery({
    queryKey: ["repositories"], queryFn: () => apiRequest<Repository[]>(token, "/api/repositories"),
  });
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["review-issues"] });
    void queryClient.invalidateQueries({ queryKey: ["review-issue", selectedId] });
  };
  const changeStatus = useMutation({
    mutationFn: (next: "open" | "fixed" | "ignored") => apiRequest(token, `/api/review-issues/${selectedId}`, {
      method: "PATCH", body: JSON.stringify({ status: next, note: note.trim() || null }),
    }),
    onSuccess: () => { setNote(""); refresh(); },
  });
  const merge = useMutation({
    mutationFn: () => apiRequest(token, `/api/review-issues/${selectedId}/merge`, {
      method: "POST", body: JSON.stringify({ target_id: Number(mergeTarget) }),
    }),
    onSuccess: () => { setMergeTarget(""); refresh(); },
  });
  function updateFilter(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    next.delete("page");
    next.delete("issue");
    setParams(next);
  }
  function selectIssue(id: number | null) {
    const next = new URLSearchParams(params);
    if (id === null) next.delete("issue"); else next.set("issue", String(id));
    setNote("");
    setMergeTarget("");
    setParams(next);
  }
  function changePage(nextPage: number) {
    const next = new URLSearchParams(params);
    next.set("page", String(nextPage));
    next.delete("issue");
    setParams(next);
  }
  const pages = Math.max(1, Math.ceil((issues.data?.total ?? 0) / (issues.data?.page_size ?? 25)));
  return <div className="page">
    <PageHeader title="待跟进问题" subtitle="跨评审追踪问题与处理记录" actions={<button className="icon-button" type="button" title="刷新问题" aria-label="刷新问题" onClick={refresh}><RefreshCw size={18} /></button>} />
    <div className="filter-bar issue-filters">
      <SelectField label="项目" value={repositoryId} onValueChange={(value) => updateFilter("repository_id", value)} options={[{ value: "", label: "全部项目" }, ...(repositories.data ?? []).map((item) => ({ value: String(item.id), label: item.name }))]} />
      <SelectField label="状态" value={status} onValueChange={(value) => updateFilter("status", value)} options={[{ value: "", label: "全部状态" }, ...Object.entries(labels).map(([value, label]) => ({ value, label }))]} />
      <SelectField label="级别" value={severity} onValueChange={(value) => updateFilter("severity", value)} options={[{ value: "", label: "全部级别" }, ...["critical", "high", "medium", "low"].map((value) => ({ value, label: formatSeverity(value) }))]} />
    </div>
    <QueryState loading={issues.isLoading} error={issues.error || repositories.error} />
    <section className="section"><div className="table-scroll responsive-table"><table><thead><tr><th>问题</th><th>项目</th><th>位置</th><th>级别</th><th>状态</th><th>出现</th><th>最近发现</th><th aria-label="操作" /></tr></thead><tbody>
      {issues.data?.items.map((item) => <tr key={item.id}><td data-label="问题" className="mono">#{item.id}</td><td data-label="项目">{item.repository_name}</td><td data-label="位置" className="file-path mono" title={item.path}>{item.path}</td><td data-label="级别">{formatSeverity(item.severity)}</td><td data-label="状态">{labels[item.status]}</td><td data-label="出现">{item.occurrence_count} 次</td><td data-label="最近发现">{formatTime(item.last_seen_at)}</td><td data-label="操作"><button className="row-link" type="button" title={`查看问题 ${item.id}`} aria-label={`查看问题 ${item.id}`} onClick={() => selectIssue(item.id)}><ArrowUpRight size={16} /></button></td></tr>)}
      {issues.data?.items.length === 0 && <tr><td colSpan={8} className="empty-row">当前筛选下没有问题</td></tr>}
    </tbody></table></div></section>
    <div className="pagination" aria-label="问题分页"><span>共 {issues.data?.total ?? 0} 条 · 第 {page} / {pages} 页</span><button className="icon-button" aria-label="上一页" title="上一页" disabled={page <= 1} onClick={() => changePage(page - 1)}><ChevronLeft size={18} /></button><button className="icon-button" aria-label="下一页" title="下一页" disabled={page >= pages} onClick={() => changePage(page + 1)}><ChevronRight size={18} /></button></div>
    {selectedId !== null && <section className="section issue-detail"><div className="section-head"><h2>问题 #{selectedId}</h2><button className="button button-secondary" type="button" onClick={() => selectIssue(null)}>关闭</button></div><QueryState loading={detail.isLoading} error={detail.error} />
      {detail.data && <><div className="issue-detail-head"><span>{detail.data.repository_name} · {labels[detail.data.status]}</span><span>{formatSeverity(detail.data.severity)} · {formatCategory(detail.data.category)}</span></div><p className="mono file-path">{detail.data.path}</p><p>{detail.data.content}</p>
        {detail.data.merged_into_id && <p>已并入问题 <button className="text-link" type="button" onClick={() => selectIssue(detail.data?.merged_into_id ?? null)}>#{detail.data.merged_into_id}</button></p>}
        {canEdit && detail.data.status !== "merged" && <div className="issue-actions"><label>处理说明<input value={note} maxLength={500} onChange={(event) => setNote(event.target.value)} placeholder="可选" /></label><div className="issue-action-buttons">{(["open", "fixed", "ignored"] as const).map((value) => <button key={value} type="button" className={detail.data?.status === value ? "button button-primary" : "button button-secondary"} disabled={changeStatus.isPending || detail.data?.status === value} onClick={() => changeStatus.mutate(value)}>{labels[value]}</button>)}</div><label>合并到问题编号<input type="number" min="1" value={mergeTarget} onChange={(event) => setMergeTarget(event.target.value)} /></label><button className="button button-secondary" type="button" disabled={!Number(mergeTarget) || merge.isPending} onClick={() => merge.mutate()}>合并重复问题</button></div>}
        {(changeStatus.error || merge.error) && <p className="form-error" role="alert">{(changeStatus.error || merge.error)?.message}</p>}
        <h3>出现记录</h3><div className="table-scroll"><table><thead><tr><th>任务</th><th>来源</th><th>提交</th><th>位置</th><th>时间</th></tr></thead><tbody>{detail.data.occurrences.map((item) => <tr key={item.id}><td><Link to={`/jobs/${item.job_id}`}>#{item.job_id} · 第 {item.attempt_number} 次</Link></td><td>{item.mr_iid > 0 ? `MR !${item.mr_iid}` : "默认分支 Push"}</td><td className="mono">{shortSha(item.commit_sha)}</td><td className="mono">{item.path}{item.start_line ? `:${item.start_line}` : ""}</td><td>{formatTime(item.created_at)}</td></tr>)}</tbody></table></div>
        <h3>处理记录</h3><ul className="issue-history">{detail.data.events.map((item) => <li key={item.id}><span>{formatTime(item.created_at)} · {item.actor} · {labels[item.new_status as IssueStatus]}</span>{item.note && <p>{item.note}</p>}</li>)}</ul>
      </>}
    </section>}
  </div>;
}
