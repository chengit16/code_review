/** @description 当前有效发现主列表；URL 保存服务端筛选，选择冻结版本，批量写入继承服务端授权。 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { App, Button, Input, Select, Space, Tag } from "antd";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { apiRequest } from "../api/client";
import { batchFindingFeedback, getReviewFindings } from "../api/reviewFindings";
import type { ReviewFinding } from "../api/reviewFindings";
import type { Repository } from "../api/types";
import { ListTime } from "../ui/ListControls";
import { ListTable } from "../ui/ListTable";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { formatSeverity } from "../ui/format";

import { findingFeedbackOptions } from "./FindingActions";
import type { FindingFeedbackChoice } from "./FindingActions";
import { ReviewFindingDrawer } from "./ReviewFindingDrawer";
import { feedbackCacheKeys } from "./findingFeedbackCache";

/** 详情导航保留勾选；条件改变则重新挂载，避免把上一范围的选择混入新列表。 */
export function ReviewFindingsPage({ token, canEdit }: {
  /** 内存会话。 */ token: string;
  /** 操作展示权限；服务端继续授权。 */ canEdit: boolean;
}) {
  const [params] = useSearchParams();
  const scope = new URLSearchParams(params);
  scope.delete("finding");
  return <FindingsContent key={scope.toString()} token={token} canEdit={canEdit} />;
}

function FindingsContent({ token, canEdit }: { token: string; canEdit: boolean }) {
  const [params, setParams] = useSearchParams();
  const { modal } = App.useApp();
  const client = useQueryClient();
  const [targets, setTargets] = useState<ReviewFinding[]>([]);
  const [keyword, setKeyword] = useState(params.get("q") ?? "");
  const [verdict, setVerdict] = useState<FindingFeedbackChoice>("helpful");
  const [confirming, setConfirming] = useState(false);
  const [needsReview, setNeedsReview] = useState(false);
  const query = new URLSearchParams(params);
  query.delete("finding");
  if (!query.has("handling")) query.set("handling", "pending");
  const page = Math.max(1, Number(params.get("page")) || 1);
  const pageSize = Math.max(1, Number(params.get("page_size")) || 25);
  const findings = useQuery({ queryKey: ["review-findings", query.toString()], queryFn: ({ signal }) => getReviewFindings(token, query.toString(), signal), refetchInterval: targets.length ? false : 15000 });
  const repositories = useQuery({ queryKey: ["repositories"], queryFn: ({ signal }) => apiRequest<Repository[]>(token, "/api/repositories", { signal }) });
  const batch = useMutation({
    mutationFn: (frozen: ReviewFinding[]) => batchFindingFeedback(token, frozen.map(({ job_id, finding_id, source_attempt, revision }) => ({ job_id, finding_id, source_attempt, revision })), verdict),
    onSuccess: async (result) => {
      // 仅移除明确成功项；失败身份和版本保持原样，须显式重新核对后才能提交。
      setTargets((current) => current.filter((item) => !result.results.some((row) => row.finding_id === item.finding_id && row.status === "updated")));
      setNeedsReview(result.updated !== result.results.length);
      await Promise.all(feedbackCacheKeys.map((key) => client.invalidateQueries({ queryKey: [key] })));
    },
    onError: () => setNeedsReview(true),
  });
  const locked = batch.isPending || confirming;
  function change(key: string, value: string) {
    const next = new URLSearchParams(params);
    next.delete("page");
    next.delete("finding");
    if (value) next.set(key, value); else next.delete(key);
    setParams(next);
  }
  function selectDetail(value: string | null) {
    const next = new URLSearchParams(params);
    if (value) next.set("finding", value); else next.delete("finding");
    setParams(next);
  }
  function submit() {
    const frozen = targets.map((item) => ({ ...item }));
    setConfirming(true);
    modal.confirm({ title: `确认将 ${frozen.length} 条发现反馈为“${findingFeedbackOptions.find((item) => item.value === verdict)?.label}”？`,
      content: <><p>仅处理下列勾选发现，替换其价值反馈，不更改代码修复记录。切换筛选或分页会清除勾选。</p><ul>{frozen.map((item) => <li key={item.finding_id}>任务 #{item.job_id} · {item.path} · {item.finding_id} · 版本 {item.source_attempt}/{item.revision}</li>)}</ul></>,
      okText: "确认反馈", cancelText: "返回核对", onOk: async () => {
        try { await batch.mutateAsync(frozen); }
        catch { /* Mutation 已保留失败与冻结目标，在列表中继续核对，不留可重复提交的旧确认框。 */ }
        finally { setConfirming(false); }
      }, onCancel: () => setConfirming(false), afterClose: () => setConfirming(false) });
  }
  return <div className="page"><PageHeader title="评审发现" subtitle="有帮助、误报或忽略均表示已处理；撤销后回到待处理" actions={<Space><Link to="/issues?status=all">历史问题与修复记录</Link><Button disabled={locked} onClick={() => void findings.refetch()}>刷新发现</Button></Space>} />
    <section className="list-surface">
      <Space wrap className="finding-list-filters">
        <label>处理状态<Select virtual={false} aria-label="发现处理状态" disabled={locked} value={query.get("handling")} onChange={(value) => change("handling", value)} options={[{ value: "all", label: "全部发现" }, { value: "pending", label: "待处理" }, { value: "handled", label: "已处理" }]} /></label>
        <label>反馈<Select virtual={false} aria-label="发现价值反馈" disabled={locked} value={params.get("feedback") ?? "all"} onChange={(value) => change("feedback", value === "all" ? "" : value)} options={[{ value: "all", label: "全部反馈" }, { value: "unmarked", label: "未评价" }, ...findingFeedbackOptions.map(({ value, label }) => ({ value, label }))]} /></label>
        <label>项目<Select virtual={false} aria-label="发现项目" disabled={locked} value={params.get("repository_id") ?? "all"} onChange={(value) => change("repository_id", value === "all" ? "" : value)} options={[{ value: "all", label: "全部项目" }, ...(repositories.data ?? []).map((item) => ({ value: String(item.id), label: item.name }))]} /></label>
        <label>级别<Select virtual={false} aria-label="发现级别" disabled={locked} value={params.get("severity") ?? "all"} onChange={(value) => change("severity", value === "all" ? "" : value)} options={[{ value: "all", label: "全部级别" }, ...["critical", "high", "medium", "low", "unclassified"].map((value) => ({ value, label: formatSeverity(value) }))]} /></label>
        <form onSubmit={(event) => { event.preventDefault(); change("q", keyword.trim()); }}><Space><Input aria-label="搜索发现" placeholder="搜索描述或文件" value={keyword} maxLength={200} disabled={locked} onChange={(event) => setKeyword(event.target.value)} /><Button htmlType="submit" disabled={locked}>搜索</Button></Space></form>
        <Button disabled={locked} onClick={() => setParams({ handling: "pending" })}>重置筛选</Button>
      </Space>
      <p>{params.has("since") ? `来源窗口：${params.get("since")} 至 ${params.get("until")}（不含终点，UTC）` : "全部时间 · 仅当前有效发现"}{params.get("category") && ` · 类别 ${params.get("category")}`}{params.get("issue_id") && ` · 原问题 #${params.get("issue_id")} 的关联发现，各条分别反馈`}</p>
      <QueryState loading={findings.isLoading} error={findings.error || repositories.error} onRetry={() => void findings.refetch()} />
      {targets.length > 0 && <div className="finding-list-batch"><Space wrap><strong>已选 {targets.length} 条</strong><Select aria-label="批量价值反馈" disabled={locked || needsReview} value={verdict} onChange={setVerdict} options={findingFeedbackOptions.map(({ value, label }) => ({ value, label }))} /><Button type="primary" disabled={locked || needsReview || findings.isFetching || Boolean(findings.error)} onClick={submit}>批量反馈</Button><Button disabled={locked} onClick={() => { setTargets([]); setNeedsReview(false); batch.reset(); }}>清除选择</Button></Space></div>}
      {(batch.error || needsReview) && <div role="alert"><p>{batch.error?.message ?? "部分发现未写入，失败项与原版本已保留。"}请核对失败目标，刷新并重新勾选后提交。</p><ul>{targets.map((item) => <li key={item.finding_id}>{item.finding_id} · 版本 {item.source_attempt}/{item.revision}</li>)}</ul><Button disabled={locked} onClick={async () => { await findings.refetch(); setTargets([]); setNeedsReview(false); batch.reset(); }}>刷新并重新选择</Button></div>}
      {batch.data && <p role="status">批量反馈成功 {batch.data.updated} 条，失败 {batch.data.results.length - batch.data.updated} 条。</p>}
      <p role="status">{findings.data ? `共 ${findings.data.total} 条发现` : "正在读取发现"}</p>
      <ListTable rowKey="finding_id" dataSource={findings.data?.items ?? []} loading={findings.isFetching} onOpenRow={(item) => selectDetail(item.finding_id)} rowLabel={(item) => `查看发现 ${item.finding_id}`} scroll={{ x: 1100 }} locale={{ emptyText: "当前条件没有评审发现" }} rowSelection={canEdit ? { selectedRowKeys: targets.map((item) => item.finding_id), preserveSelectedRowKeys: true, getCheckboxProps: () => ({ disabled: locked || needsReview || findings.isFetching || Boolean(findings.error) }), onChange: (_, rows) => setTargets((current) => rows.map((item) => current.find((target) => target.finding_id === item.finding_id) ?? { ...item })) } : undefined}
        pagination={{ current: page, pageSize, total: findings.data?.total, showSizeChanger: true, pageSizeOptions: [10, 25, 50, 100], disabled: locked, onChange: (value, size) => { const next = new URLSearchParams(params); next.delete("finding"); next.set("page", String(size !== pageSize ? 1 : value)); next.set("page_size", String(size)); setParams(next); } }} columns={[
          { title: "发现 / 文件", key: "finding", render: (_, item) => <><Button type="link" className="finding-list-summary" onClick={() => selectDetail(item.finding_id)}>{item.excerpt}</Button><p className="mono file-path">{item.path}</p></> },
          { title: "任务 / 项目", key: "job", width: 150, render: (_, item) => <><Link to={`/jobs/${item.job_id}#job-result`}>任务 #{item.job_id}</Link><p>{item.repository_name}</p></> },
          { title: "提交人", dataIndex: "commit_author", width: 120, render: (value: string | null) => value?.trim() || "未记录" },
          { title: "严重级别", dataIndex: "severity", width: 90, render: (value: string) => formatSeverity(value) },
          { title: "处理状态", key: "handling", width: 100, render: (_, item) => <Tag color={item.handling === "handled" ? "green" : "orange"}>{item.handling === "handled" ? "已处理" : "待处理"}</Tag> },
          { title: "价值反馈", key: "feedback", width: 100, render: (_, item) => findingFeedbackOptions.find((option) => option.value === item.feedback)?.label ?? "未评价" },
          { title: "发现时间", dataIndex: "generated_at", width: 160, render: (value: string) => <ListTime value={value} /> },
        ]} />
    </section>
    {params.get("finding") && <ReviewFindingDrawer key={params.get("finding")} token={token} findingId={params.get("finding") ?? ""} canEdit={canEdit} onClose={() => selectDetail(null)} />}
  </div>;
}
