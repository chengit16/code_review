/** @description 按项目跟进评审发现，原始出现记录与人工处理状态分开显示。 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUpRight, ChevronLeft, ChevronRight, RefreshCw } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { apiRequest } from "../api/client";
import type { Repository } from "../api/types";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { SelectField } from "../ui/SelectField";
import { formatSeverity, formatTime } from "../ui/format";
import { IssueDetailDrawer } from "./IssueDetailDrawer";
import { IssueBatchBar } from "./IssueBatchBar";
import { useIssueBatch } from "./useIssueBatch";

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

const labels: Record<IssueStatus, string> = {
  open: "待处理", fixed: "已修复", ignored: "已忽略", merged: "已合并",
};

/** 筛选保留在地址栏，详情仍能从不同来源直接定位到问题。 */
export function ReviewIssuesPage({ token, canEdit }: {
  /** 内存会话令牌。 */ token: string;
  /** 服务端权限之外的操作显示控制。 */ canEdit: boolean;
}) {
  const [params] = useSearchParams();
  const scope = new URLSearchParams(params);
  scope.delete("issue");
  // 筛选、分页及浏览器前后退均重建选择草稿，查看单项详情则保留当前页选择。
  return <ReviewIssuesContent key={scope.toString()} token={token} canEdit={canEdit} />;
}

function ReviewIssuesContent({ token, canEdit }: { token: string; canEdit: boolean }) {
  const [params, setParams] = useSearchParams();
  const [keyword, setKeyword] = useState(params.get("q") ?? "");
  const queryClient = useQueryClient();
  const selectedId = Number(params.get("issue")) || null;
  const page = Math.max(1, Number(params.get("page")) || 1);
  const repositoryId = params.get("repository_id") ?? "";
  const status = params.get("status") ?? "open";
  const severity = params.get("severity") ?? "";
  const query = new URLSearchParams({ page: String(page) });
  if (repositoryId) query.set("repository_id", repositoryId);
  if (status && status !== "all") query.set("status", status);
  if (severity) query.set("severity", severity);
  if (params.get("q")) query.set("q", params.get("q") ?? "");
  const issues = useQuery({
    queryKey: ["review-issues", query.toString()],
    queryFn: ({ signal }) => apiRequest<{ items: ReviewIssue[]; total: number; page_size: number }>(token, `/api/review-issues?${query}`, { signal }),
    refetchInterval: 15000,
  });
  const batch = useIssueBatch(token, issues.data?.items ?? []);
  const repositories = useQuery({
    queryKey: ["repositories"], queryFn: () => apiRequest<Repository[]>(token, "/api/repositories"),
  });
  const refresh = () => {
    // 单项修改也可能影响其他任务卡片和统计，不能只刷新当前问题详情。
    for (const key of ["review-issues", "review-issue", "job", "review-effectiveness"]) {
      void queryClient.invalidateQueries({ queryKey: [key] });
    }
  };
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
    <PageHeader title="待跟进问题" subtitle="跨评审追踪问题与处理记录" actions={<button className="icon-button" type="button" title="刷新问题" aria-label="刷新问题" disabled={batch.mutation.isPending} onClick={() => { batch.selectAll(false); batch.mutation.reset(); refresh(); }}><RefreshCw size={18} /></button>} />
    <div className="filter-bar issue-filters">
      <SelectField label="项目" value={repositoryId || "all"} disabled={batch.mutation.isPending} onValueChange={(value) => updateFilter("repository_id", value === "all" ? "" : value)} options={[{ value: "all", label: "全部项目" }, ...(repositories.data ?? []).map((item) => ({ value: String(item.id), label: item.name }))]} />
      <SelectField label="状态" value={status} disabled={batch.mutation.isPending} onValueChange={(value) => updateFilter("status", value)} options={[{ value: "all", label: "全部状态" }, ...Object.entries(labels).map(([value, label]) => ({ value, label }))]} />
      <SelectField label="级别" value={severity || "all"} disabled={batch.mutation.isPending} onValueChange={(value) => updateFilter("severity", value === "all" ? "" : value)} options={[{ value: "all", label: "全部级别" }, ...["critical", "high", "medium", "low"].map((value) => ({ value, label: formatSeverity(value) }))]} />
    </div>
    <form className="issue-search" onSubmit={(event) => { event.preventDefault(); updateFilter("q", keyword.trim()); }}><label>搜索问题<input value={keyword} onChange={(event) => setKeyword(event.target.value)} maxLength={200} placeholder="搜索问题描述、文件路径或编号" /></label><button className="button button-secondary" disabled={batch.mutation.isPending}>搜索</button></form>
    <QueryState loading={issues.isLoading} error={issues.error || repositories.error} onRetry={refresh} />
    {canEdit && <IssueBatchBar count={batch.targets.length} allSelected={batch.allSelected}
      disabled={issues.isFetching || Boolean(issues.error) || batch.selectableCount === 0} pending={batch.mutation.isPending}
      note={batch.note} onNote={batch.setNote} onSelectAll={batch.selectAll} onClear={() => batch.selectAll(false)} onSubmit={batch.submit} />}
    {batch.mutation.error && <p className="form-error" role="alert">{batch.mutation.error.message}；勾选和处理说明已保留，可刷新列表后重新确认。</p>}
    {batch.mutation.data && <p className="form-success" role="status">批量处理完成：更新 {batch.mutation.data.updated} 条，状态未变化 {batch.mutation.data.unchanged} 条。</p>}
    <section className="section"><div className="table-scroll responsive-table"><table><thead><tr>{canEdit && <th>选择</th>}<th>问题摘要</th><th>项目</th><th>位置</th><th>级别</th><th>状态</th><th>出现</th><th>最近发现</th><th aria-label="操作" /></tr></thead><tbody>
      {issues.data?.items.map((item) => <tr key={item.id}>{canEdit && <td data-label="选择"><input className="issue-checkbox" type="checkbox" aria-label={`选择问题 ${item.id}`} checked={batch.targets.some((target) => target.id === item.id)} disabled={item.status === "merged" || batch.mutation.isPending || issues.isFetching} onChange={(event) => batch.toggle(item, event.target.checked)} /></td>}<td data-label="问题摘要" className="issue-summary"><button type="button" className="issue-summary-button" onClick={() => selectIssue(item.id)}><span className="mono">#{item.id}</span><strong>{item.content}</strong></button></td><td data-label="项目">{item.repository_name}</td><td data-label="位置" className="file-path mono" title={item.path}>{item.path}</td><td data-label="级别">{formatSeverity(item.severity)}</td><td data-label="状态">{labels[item.status]}</td><td data-label="出现">{item.occurrence_count} 次</td><td data-label="最近发现">{formatTime(item.last_seen_at)}</td><td data-label="操作"><button className="row-link" type="button" title={`查看问题 ${item.id}`} aria-label={`查看问题 ${item.id}`} onClick={() => selectIssue(item.id)}><ArrowUpRight size={16} /></button></td></tr>)}
      {!issues.isLoading && !issues.error && issues.data?.items.length === 0 && <tr><td colSpan={canEdit ? 9 : 8} className="empty-row">当前筛选下没有问题</td></tr>}
    </tbody></table></div></section>
    <div className="pagination" aria-label="问题分页"><span>共 {issues.data?.total ?? 0} 条 · 第 {page} / {pages} 页</span><button className="icon-button" aria-label="上一页" title="上一页" disabled={page <= 1 || batch.mutation.isPending} onClick={() => changePage(page - 1)}><ChevronLeft size={18} /></button><button className="icon-button" aria-label="下一页" title="下一页" disabled={page >= pages || batch.mutation.isPending} onClick={() => changePage(page + 1)}><ChevronRight size={18} /></button></div>
    {selectedId !== null && <IssueDetailDrawer key={selectedId} token={token} id={selectedId} canEdit={canEdit} batchPending={batch.mutation.isPending} onSelect={selectIssue} />}
  </div>;
}
