/** @description 运行概览中的评审效果区块；读取服务端统计，人工状态不代表已验证代码修复。 */

import { useQuery } from "@tanstack/react-query";
import { Button } from "antd";
import { BarChart3, RefreshCw } from "lucide-react";
import { useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { apiRequest } from "../api/client";
import type { Repository } from "../api/types";
import { ListSelect as SelectField } from "../ui/ListControls";
import { ListTable } from "../ui/ListTable";
import { QueryState } from "../ui/QueryState";
import { formatCategory } from "../ui/format";

import { IssueTrend } from "./overview/IssueTrend";
import { ReadStatus } from "./overview/ReadStatus";

interface Snapshot {
  days: number;
  summary: {
    reviews: number; failed_reviews: number; generated: number; published: number;
    new_issues: number; new_still_open: number; fixed: number; ignored: number;
    open_now: number; feedback_marked: number; false_positive: number;
  };
  trend: Array<{ day: string; new: number; fixed: number }>;
  categories: Array<{ category: string; generated: number; issues: number; open_issues: number }>;
  projects: Array<{ id: number; name: string; open_issues: number; new_issues: number; fixed_issues: number; generated: number; published: number }>;
}

/** 展示关键指标与趋势，低频类别和项目报表折叠保留；筛选可刷新和分享。 */
export function ReviewEffectivenessSection({ token }: { /** 内存会话令牌。 */ token: string }) {
  const [refreshing, setRefreshing] = useState(false);
  const [message, setMessage] = useState("");
  const refreshLock = useRef(false);
  const [params, setParams] = useSearchParams();
  const repositoryId = params.get("repository_id") ?? "";
  const days = [7, 30, 90].includes(Number(params.get("days"))) ? Number(params.get("days")) : 30;
  const query = new URLSearchParams({ days: String(days) });
  if (repositoryId) query.set("repository_id", repositoryId);
  const metrics = useQuery({ queryKey: ["review-effectiveness", query.toString()],
    queryFn: ({ signal }) => apiRequest<Snapshot>(token, `/api/review-effectiveness?${query}`, { signal }), refetchInterval: 30000 });
  const repositories = useQuery({ queryKey: ["repositories"],
    queryFn: () => apiRequest<Repository[]>(token, "/api/repositories") });
  function updateFilter(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    setParams(next);
  }
  const summary = metrics.data?.summary;
  async function handleRefresh() {
    if (refreshLock.current) return;
    refreshLock.current = true;
    setRefreshing(true);
    setMessage("");
    try {
      const result = await metrics.refetch({ cancelRefetch: false });
      setMessage(result.isError ? "统计读取失败，成功的旧数据仍保留。" : "统计读取完成");
    } finally { refreshLock.current = false; setRefreshing(false); }
  }
  return <section className="section overview-effectiveness" aria-labelledby="effectiveness-heading">
    <div className="section-head"><h2 id="effectiveness-heading">评审效果</h2><Button icon={<RefreshCw size={16} />} loading={refreshing} disabled={refreshing} onClick={() => void handleRefresh()}>刷新统计</Button></div>
    <ReadStatus label="效果统计" updatedAt={metrics.dataUpdatedAt} fetching={metrics.isFetching} /><p className="overview-manual-result" role="status">{message}</p>
    <p className="form-note">项目与时间筛选仅作用本区，不改变上方当前工作。</p>
    <div className="effectiveness-filters"><SelectField label="项目" value={repositoryId || "all"} onValueChange={(value) => updateFilter("repository_id", value === "all" ? "" : value)} options={[{ value: "all", label: "全部项目" }, ...(repositories.data ?? []).map((item) => ({ value: String(item.id), label: item.name }))]} /><SelectField label="时间" value={String(days)} onValueChange={(value) => updateFilter("days", value)} options={[{ value: "7", label: "近 7 天" }, { value: "30", label: "近 30 天" }, { value: "90", label: "近 90 天" }]} /></div>
    <QueryState loading={metrics.isLoading} error={(!metrics.data && metrics.error) || repositories.error} onRetry={() => { void metrics.refetch(); void repositories.refetch(); }} />
    {metrics.isError && metrics.data && <p role="alert">效果统计刷新失败，当前显示上次成功读取的数据。请重新读取。</p>}
    {summary && <><section className="metrics effectiveness-metrics" aria-label="评审效果摘要">
      <div className="metric"><span>新问题</span><strong>{summary.new_issues}</strong><small>其中 {summary.new_still_open} 条仍待处理</small></div>
      <div className="metric"><span>人工标记已修复</span><strong>{summary.fixed}</strong><small>当前全部待处理 {summary.open_now} 条</small></div>
      <div className="metric"><span>生成 / 发布</span><strong>{summary.generated} / {summary.published}</strong><small>发布仅指 GitLab 行内评论成功</small></div>
      <div className="metric"><span>人工反馈误报率</span><strong>{summary.feedback_marked >= 5 ? `${Math.round(summary.false_positive / summary.feedback_marked * 100)}%` : "数据不足"}</strong><small>{summary.false_positive} / {summary.feedback_marked} 条已标记反馈</small></div>
    </section><p className="effectiveness-note">本期 {summary.reviews} 次终态评审，其中 {summary.failed_reviews} 次失败；另有 {summary.ignored} 条问题被人工忽略。修复数来自人工标记（含批量操作），不代表系统已验证代码修复。未标记的发现不参与误报率，未再次出现的问题不会自动计为修复。</p>
      <IssueTrend rows={metrics.data?.trend ?? []} days={days} />
      <details className="effectiveness-details"><summary>展开类别与项目统计</summary>
      <section className="section"><div className="section-head"><h2>问题类别</h2><span>按本期发现归类</span></div><ListTable rowKey="category" pagination={false} scroll={{ x: 600 }} dataSource={metrics.data?.categories ?? []} locale={{ emptyText: "本期没有发现记录" }} columns={[
        { title: "类别", key: "category", render: (_, item) => formatCategory(item.category) },
        { title: "出现次数", dataIndex: "generated", key: "generated" },
        { title: "关联问题", dataIndex: "issues", key: "issues" },
        { title: "目前待处理", key: "open", render: (_, item) => <>{item.open_issues}{item.generated < 5 && <span className="list-secondary">样本较少</span>}</> },
      ]} /><p className="effectiveness-note">OCR 当前结果没有稳定规则 ID，因此这里按类别统计，不推断单条审核规则的效果。</p></section>
      <section className="section"><div className="section-head"><h2>项目对比</h2></div><ListTable rowKey="id" pagination={false} scroll={{ x: 650 }} dataSource={metrics.data?.projects ?? []} locale={{ emptyText: "暂无项目" }} columns={[
        { title: "项目", key: "name", render: (_, item) => <Link to={`/issues?repository_id=${item.id}&status=open`}>{item.name}</Link> },
        { title: "本期新问题", dataIndex: "new_issues", key: "new" },
        { title: "本期人工标记修复", dataIndex: "fixed_issues", key: "fixed" },
        { title: "当前待处理", dataIndex: "open_issues", key: "open" },
        { title: "生成 / 发布", key: "publication", render: (_, item) => `${item.generated} / ${item.published}` },
      ]} /></section>
      </details>
    </>}
    {!summary && !metrics.isLoading && !metrics.error && <section className="section empty-inline"><BarChart3 size={18} /> 暂无统计数据</section>}
  </section>;
}
