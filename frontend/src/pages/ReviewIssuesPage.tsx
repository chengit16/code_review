/** @description 按项目跟进评审发现，原始出现记录与人工处理状态分开显示。 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Card, Input, Select, Table } from "antd";
import type { TableColumnsType } from "antd";
import { ArrowUpRight, RefreshCw } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { apiRequest } from "../api/client";
import type { Repository } from "../api/types";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { formatSeverity, formatTime } from "../ui/format";
import { IssueDetailDrawer } from "./IssueDetailDrawer";
import { IssueBatchBar } from "./IssueBatchBar";
import { useIssueBatch } from "./useIssueBatch";

type IssueStatus = "open" | "fixed" | "ignored" | "merged";

interface ReviewIssue {
  id: number;
  repository_id: number;
  repository_name: string;
  commit_author: string | null;
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
  if (params.get("page_size")) query.set("page_size", params.get("page_size") ?? "25");
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
  const columns: TableColumnsType<ReviewIssue> = [
    ...(canEdit ? [{
      title: "选择", key: "select", width: 64,
      render: (_: unknown, item: ReviewIssue) => <input className="issue-checkbox" type="checkbox" aria-label={`选择问题 ${item.id}`} checked={batch.targets.some((target) => target.id === item.id)} disabled={item.status === "merged" || batch.mutation.isPending || issues.isFetching} onChange={(event) => batch.toggle(item, event.target.checked)} />,
    }] : []),
    { title: "问题摘要", dataIndex: "content", key: "content", render: (content: string, item) => <button type="button" className="issue-summary-button" onClick={() => selectIssue(item.id)}><span className="mono">#{item.id}</span><strong>{content}</strong></button> },
    { title: "项目", dataIndex: "repository_name", key: "repository_name", width: 160 },
    { title: <span title="最近一次出现关联评审提交的 Git 作者，不代表问题责任人">提交人</span>, dataIndex: "commit_author", key: "commit_author", width: 140, render: (value: string | null) => value?.trim() || "未记录" },
    { title: "位置", dataIndex: "path", key: "path", width: 220, render: (value: string) => <span className="file-path mono" title={value}>{value}</span> },
    { title: "级别", dataIndex: "severity", key: "severity", width: 90, render: (value: string | null) => formatSeverity(value) },
    { title: "状态", dataIndex: "status", key: "status", width: 96, render: (value: IssueStatus) => labels[value] },
    { title: "出现", dataIndex: "occurrence_count", key: "occurrence_count", width: 84, render: (value: number) => `${value} 次` },
    { title: "最近发现", dataIndex: "last_seen_at", key: "last_seen_at", width: 160, render: (value: string) => formatTime(value) },
    { title: "操作", key: "actions", width: 68, render: (_: unknown, item) => <Button type="link" aria-label={`查看问题 ${item.id}`} onClick={() => selectIssue(item.id)}><ArrowUpRight size={16} /></Button> },
  ];
  return <div className="page">
    <PageHeader title="待跟进问题" subtitle="跨评审追踪问题与处理记录" actions={<button className="icon-button" type="button" title="刷新问题" aria-label="刷新问题" disabled={batch.mutation.isPending} onClick={() => { batch.selectAll(false); batch.mutation.reset(); refresh(); }}><RefreshCw size={18} /></button>} />
    <Card className="issue-filter-card" size="small">
      <div className="issue-filter-grid">
        <label>项目<Select aria-label="项目" value={repositoryId || "all"} disabled={batch.mutation.isPending} onChange={(value) => updateFilter("repository_id", value === "all" ? "" : value)} options={[{ value: "all", label: "全部项目" }, ...(repositories.data ?? []).map((item) => ({ value: String(item.id), label: item.name }))]} /></label>
        <label>状态<Select aria-label="状态" value={status} disabled={batch.mutation.isPending} onChange={(value) => updateFilter("status", value)} options={[{ value: "all", label: "全部状态" }, ...Object.entries(labels).map(([value, label]) => ({ value, label }))]} /></label>
        <label>级别<Select aria-label="级别" value={severity || "all"} disabled={batch.mutation.isPending} onChange={(value) => updateFilter("severity", value === "all" ? "" : value)} options={[{ value: "all", label: "全部级别" }, ...["critical", "high", "medium", "low"].map((value) => ({ value, label: formatSeverity(value) }))]} /></label>
        <form className="issue-search" onSubmit={(event) => { event.preventDefault(); updateFilter("q", keyword.trim()); }}><label>搜索问题<Input value={keyword} onChange={(event) => setKeyword(event.target.value)} maxLength={200} placeholder="搜索摘要、文件路径或编号" /></label><Button htmlType="submit" disabled={batch.mutation.isPending}>搜索</Button></form>
      </div>
    </Card>
    <QueryState loading={issues.isLoading} error={issues.error || repositories.error} onRetry={refresh} />
    {canEdit && <IssueBatchBar count={batch.targets.length} allSelected={batch.allSelected}
      disabled={issues.isFetching || Boolean(issues.error) || batch.selectableCount === 0} pending={batch.mutation.isPending}
      note={batch.note} onNote={batch.setNote} onSelectAll={batch.selectAll} onClear={() => batch.selectAll(false)} onSubmit={batch.submit} />}
    {batch.mutation.error && <p className="form-error" role="alert">{batch.mutation.error.message}；勾选和处理说明已保留，可刷新列表后重新确认。</p>}
    {batch.mutation.data && <p className="form-success" role="status">批量处理完成：更新 {batch.mutation.data.updated} 条，状态未变化 {batch.mutation.data.unchanged} 条。</p>}
    <Card className="issue-table-card" size="small" title={`问题记录 · ${issues.data?.total ?? "—"} 条`}>
      <p className="issue-table-note">“提交人”是最近一次出现记录中的 Git 作者，不代表问题责任人；标记“已修复”是人工处理状态，不代表系统已验证修复。</p>
      <Table rowKey="id" size="middle" columns={columns} dataSource={issues.data?.items ?? []} loading={issues.isFetching} locale={{ emptyText: issues.error ? "无法读取问题" : "当前筛选下没有问题" }} scroll={{ x: 1120 }} pagination={{ current: page, pageSize: issues.data?.page_size ?? 25, total: issues.data?.total ?? 0, showSizeChanger: true, pageSizeOptions: [25, 50, 100], locale: { items_per_page: "条/页", prev_page: "上一页", next_page: "下一页", page: "页", jump_to: "跳至", page_size: "每页条数" }, showTotal: (total, range) => `${range[0]}-${range[1]} / ${total} 条`, disabled: issues.isFetching || batch.mutation.isPending || Boolean(issues.error), onChange: (nextPage, size) => { if (size !== (issues.data?.page_size ?? 25)) updateFilter("page_size", String(size)); else changePage(nextPage); } }} />
    </Card>
    {selectedId !== null && <IssueDetailDrawer key={selectedId} token={token} id={selectedId} canEdit={canEdit} batchPending={batch.mutation.isPending} onSelect={selectIssue} />}
  </div>;
}
