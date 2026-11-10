/** @description 按项目跟进评审发现，原始出现记录与人工处理状态分开显示。 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Checkbox, Input, Select, Tag } from "antd";
import type { TableColumnsType } from "antd";
import { RefreshCw } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { apiRequest } from "../api/client";
import type { Repository } from "../api/types";
import { ListConditions, ListExcerpt, ListStatusNav, ListTime } from "../ui/ListControls";
import { ListTable, useNarrowList } from "../ui/ListTable";
import { PageHeader } from "../ui/PageHeader";
import { Pagination } from "../ui/Pagination";
import { QueryState } from "../ui/QueryState";
import { formatSeverity } from "../ui/format";

import { IssueBatchBar } from "./IssueBatchBar";
import { IssueDetailDrawer } from "./IssueDetailDrawer";
import { useIssueBatch } from "./useIssueBatch";

type IssueStatus = "open" | "fixed" | "ignored" | "false_positive" | "merged";

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
  open: "待处理", fixed: "已修复", ignored: "已忽略", false_positive: "误报", merged: "已合并",
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
  const narrow = useNarrowList();
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
    queryFn: ({ signal }) => apiRequest<{ items: ReviewIssue[]; total: number; page_size: number; status_counts?: Record<string, number> }>(token, `/api/review-issues?${query}`, { signal }),
    refetchInterval: 15000,
  });
  const batch = useIssueBatch(token, issues.data?.items ?? []);
  const repositories = useQuery({
    queryKey: ["repositories"], queryFn: () => apiRequest<Repository[]>(token, "/api/repositories"),
  });
  const refresh = () => {
    // 单项修改也可能影响其他任务卡片和统计，不能只刷新当前问题详情。
    for (const key of ["jobs", "job-neighbors", "review-issues", "review-issue", "job", "review-effectiveness", "overview"]) {
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
      title: <Checkbox aria-label="全选当前页" checked={batch.allSelected} disabled={issues.isFetching || Boolean(issues.error) || batch.mutation.isPending || batch.selectableCount === 0} onChange={(event) => batch.selectAll(event.target.checked)}>选择</Checkbox>, key: "select", width: 64,
      render: (_: unknown, item: ReviewIssue) => <Checkbox className="issue-checkbox" aria-label={`选择问题 ${item.id}`} checked={batch.targets.some((target) => target.id === item.id)} disabled={item.status === "merged" || batch.mutation.isPending || issues.isFetching} onChange={(event) => batch.toggle(item, event.target.checked)} />,
    }] : []),
    { title: "问题 / 位置", dataIndex: "content", key: "content", render: (content: string, item) => <><button type="button" aria-label={`查看问题 ${item.id}`} className="issue-summary-button" onClick={() => selectIssue(item.id)}><span className="mono">#{item.id}</span><strong>{content.slice(0, 90)}{content.length > 90 ? "…" : ""}</strong></button><span className="list-secondary"><ListExcerpt text={item.path} limit={65} /></span></> },
    { title: "项目", dataIndex: "repository_name", key: "repository_name", width: 160 },
    { title: "提交人", dataIndex: "commit_author", key: "commit_author", width: 140, render: (value: string | null) => value?.trim() || "未记录" },
    { title: "级别", dataIndex: "severity", key: "severity", width: 90, render: (value: string | null) => formatSeverity(value) },
    { title: "处置状态", dataIndex: "status", key: "status", width: 96, render: (value: IssueStatus) => <Tag color={value === "open" ? "orange" : "default"}>{labels[value]}</Tag> },
    { title: "出现", dataIndex: "occurrence_count", key: "occurrence_count", width: 84, render: (value: number) => `${value} 次` },
    { title: "最近发现", dataIndex: "last_seen_at", key: "last_seen_at", width: 160, render: (value: string) => <ListTime value={value} /> },
  ];
  return <div className="page">
    <PageHeader title="历史问题与修复记录" subtitle="保留原问题编号、独立处置及跨任务出现历史" actions={<button className="icon-button" type="button" title="刷新问题" aria-label="刷新问题" disabled={batch.mutation.isPending} onClick={() => { batch.selectAll(false); batch.mutation.reset(); refresh(); }}><RefreshCw size={18} /></button>} />
    <p>这里保留原问题处置，不代表发现反馈进度。<Link to={`/findings?handling=all${selectedId ? `&issue_id=${selectedId}` : ""}`}>{selectedId ? `查看问题 #${selectedId} 关联的全部当前发现` : "进入评审发现"}</Link>；一个问题可能关联多条发现，请逐条反馈。</p>
    <section className="list-surface"><ListStatusNav label="问题处置状态" value={status} labels={{ all: "全部（不含已合并）", ...labels }} counts={issues.error ? undefined : issues.data?.status_counts} disabled={batch.mutation.isPending} onChange={(value) => updateFilter("status", value)} />
      <div className="issue-filter-grid">
        <label>项目<Select aria-label="项目" value={repositoryId || "all"} disabled={batch.mutation.isPending} onChange={(value) => updateFilter("repository_id", value === "all" ? "" : value)} options={[{ value: "all", label: "全部项目" }, ...(repositories.data ?? []).map((item) => ({ value: String(item.id), label: item.name }))]} /></label>
        <label>级别<Select aria-label="级别" value={severity || "all"} disabled={batch.mutation.isPending} onChange={(value) => updateFilter("severity", value === "all" ? "" : value)} options={[{ value: "all", label: "全部级别" }, ...["critical", "high", "medium", "low"].map((value) => ({ value, label: formatSeverity(value) }))]} /></label>
        <form className="issue-search" onSubmit={(event) => { event.preventDefault(); updateFilter("q", keyword.trim()); }}><label>搜索问题<Input value={keyword} onChange={(event) => setKeyword(event.target.value)} maxLength={200} placeholder="搜索摘要、文件路径或编号" /></label><Button htmlType="submit" disabled={batch.mutation.isPending}>搜索</Button></form><Button disabled={batch.mutation.isPending} onClick={() => { const next = new URLSearchParams(params); for (const key of ["q", "repository_id", "severity", "status", "page", "issue"]) next.delete(key); setParams(next); }}>重置</Button>
      </div>

    <QueryState loading={issues.isLoading} error={issues.error || repositories.error} onRetry={refresh} />
    {canEdit && batch.targets.length > 0 && <IssueBatchBar count={batch.targets.length} allSelected={batch.allSelected}
      disabled={issues.isFetching || Boolean(issues.error) || batch.selectableCount === 0} pending={batch.mutation.isPending}
      note={batch.note} onNote={batch.setNote} onSelectAll={batch.selectAll} onClear={() => batch.selectAll(false)} onSubmit={batch.submit} />}
    {batch.mutation.error && <p className="form-error" role="alert">{batch.mutation.error.message}；勾选和处理说明已保留，可刷新列表后重新确认。</p>}
    {batch.mutation.data && <p className="form-success" role="status">批量处理完成：更新 {batch.mutation.data.updated} 条，状态未变化 {batch.mutation.data.unchanged} 条。</p>}
    <ListConditions disabled={batch.mutation.isPending} items={[{ key: "repository_id", label: "项目", value: repositories.data?.find((item) => String(item.id) === repositoryId)?.name ?? repositoryId }, { key: "severity", label: "级别", value: severity }, { key: "q", label: "搜索", value: params.get("q") ?? "" }]} onClear={(key) => updateFilter(key, "")} />
      <p className="issue-table-note">“提交人”是最近一次出现记录中的 Git 作者，不代表问题责任人；标记“已修复”是人工处理状态，不代表系统已验证修复。</p>
      {canEdit && narrow && <div className="list-mobile-selection"><Checkbox aria-label="全选当前页" checked={batch.allSelected} disabled={issues.isFetching || Boolean(issues.error) || batch.mutation.isPending || batch.selectableCount === 0} onChange={(event) => batch.selectAll(event.target.checked)}>全选当前页可处理问题</Checkbox></div>}
      <ListTable onOpenRow={(item) => selectIssue(item.id)} rowLabel={(item) => `查看问题 ${item.id}`} rowKey="id" columns={columns} dataSource={issues.data?.items ?? []} loading={issues.isFetching} locale={{ emptyText: issues.error ? "无法读取问题" : "当前筛选下没有问题" }} scroll={{ x: 1080 }} pagination={false} />
      <Pagination label="问题分页" total={issues.error ? undefined : issues.data?.total} page={page} pageSize={issues.data?.page_size ?? 25} disabled={issues.isFetching || batch.mutation.isPending || Boolean(issues.error)} onPage={changePage} onPageSize={(size) => updateFilter("page_size", String(size))} />
    </section>
    {selectedId !== null && <IssueDetailDrawer key={selectedId} token={token} id={selectedId} canEdit={canEdit} batchPending={batch.mutation.isPending} onSelect={selectIssue} />}
  </div>;
}
