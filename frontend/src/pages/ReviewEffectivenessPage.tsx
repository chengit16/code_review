/** @description 区分生成、发布与人工反馈，按项目和时间检查评审效果。 */

import { useQuery } from "@tanstack/react-query";
import { BarChart3, RefreshCw } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";

import { apiRequest } from "../api/client";
import type { Repository } from "../api/types";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { SelectField } from "../ui/SelectField";

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

/** 90 天按周聚合，短时间范围按天显示，保持图表可扫描。 */
function trendBuckets(rows: Snapshot["trend"], days: number) {
  const size = days === 90 ? 7 : 1;
  const buckets: Array<{ label: string; new: number; fixed: number }> = [];
  for (let index = 0; index < rows.length; index += size) {
    const group = rows.slice(index, index + size);
    buckets.push({ label: group[0].day.slice(5),
      new: group.reduce((sum, item) => sum + item.new, 0),
      fixed: group.reduce((sum, item) => sum + item.fixed, 0) });
  }
  return buckets;
}

export function ReviewEffectivenessPage({ token }: { /** 内存会话令牌。 */ token: string }) {
  const [params, setParams] = useSearchParams();
  const repositoryId = params.get("repository_id") ?? "";
  const days = [7, 30, 90].includes(Number(params.get("days"))) ? Number(params.get("days")) : 30;
  const query = new URLSearchParams({ days: String(days) });
  if (repositoryId) query.set("repository_id", repositoryId);
  const metrics = useQuery({ queryKey: ["review-effectiveness", query.toString()],
    queryFn: () => apiRequest<Snapshot>(token, `/api/review-effectiveness?${query}`), refetchInterval: 30000 });
  const repositories = useQuery({ queryKey: ["repositories"],
    queryFn: () => apiRequest<Repository[]>(token, "/api/repositories") });
  function updateFilter(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    setParams(next);
  }
  const summary = metrics.data?.summary;
  const buckets = trendBuckets(metrics.data?.trend ?? [], days);
  const max = Math.max(1, ...buckets.map((item) => Math.max(item.new, item.fixed)));
  return <div className="page">
    <PageHeader title="评审效果" subtitle="问题、发布与人工反馈" actions={<button className="icon-button" type="button" title="刷新统计" aria-label="刷新统计" onClick={() => void metrics.refetch()}><RefreshCw size={18} /></button>} />
    <div className="filter-bar issue-filters"><SelectField label="项目" value={repositoryId} onValueChange={(value) => updateFilter("repository_id", value)} options={[{ value: "", label: "全部项目" }, ...(repositories.data ?? []).map((item) => ({ value: String(item.id), label: item.name }))]} /><SelectField label="时间" value={String(days)} onValueChange={(value) => updateFilter("days", value)} options={[{ value: "7", label: "近 7 天" }, { value: "30", label: "近 30 天" }, { value: "90", label: "近 90 天" }]} /></div>
    <QueryState loading={metrics.isLoading} error={metrics.error || repositories.error} />
    {summary && <><section className="metrics effectiveness-metrics" aria-label="评审效果摘要">
      <div className="metric"><span>新问题</span><strong>{summary.new_issues}</strong><small>其中 {summary.new_still_open} 条仍待处理</small></div>
      <div className="metric"><span>已确认修复</span><strong>{summary.fixed}</strong><small>当前全部待处理 {summary.open_now} 条</small></div>
      <div className="metric"><span>生成 / 发布</span><strong>{summary.generated} / {summary.published}</strong><small>发布仅指 GitLab 行内评论成功</small></div>
      <div className="metric"><span>人工反馈误报率</span><strong>{summary.feedback_marked >= 5 ? `${Math.round(summary.false_positive / summary.feedback_marked * 100)}%` : "数据不足"}</strong><small>{summary.false_positive} / {summary.feedback_marked} 条已标记反馈</small></div>
    </section><p className="effectiveness-note">本期 {summary.reviews} 次终态评审，其中 {summary.failed_reviews} 次失败；另有 {summary.ignored} 条问题被人工忽略。未标记的发现不参与误报率，未再次出现的问题不会自动计为修复。</p>
      <section className="section"><div className="section-head"><h2>问题变化</h2><span>{days === 90 ? "每周" : "每日"}</span></div><div className="trend-legend"><span className="trend-key trend-key-new" />新问题 <span className="trend-key trend-key-fixed" />确认修复</div><div className="trend-chart" role="img" aria-label={`${days} 天内每日或每周新增与修复问题趋势`}>
        {buckets.map((item) => <div className="trend-column" key={item.label} title={`${item.label}：新增 ${item.new}，修复 ${item.fixed}`}><div className="trend-bars"><span className="trend-bar trend-bar-new" style={{ height: `${Math.max(item.new ? 6 : 0, item.new / max * 100)}%` }} /><span className="trend-bar trend-bar-fixed" style={{ height: `${Math.max(item.fixed ? 6 : 0, item.fixed / max * 100)}%` }} /></div><small>{item.label}</small></div>)}
      </div></section>
      <section className="section"><div className="section-head"><h2>问题类别</h2><span>按本期发现归类</span></div><div className="table-scroll"><table><thead><tr><th>类别</th><th>出现次数</th><th>关联问题</th><th>目前待处理</th></tr></thead><tbody>{metrics.data?.categories.map((item) => <tr key={item.category}><td>{item.category}</td><td>{item.generated}</td><td>{item.issues}</td><td>{item.open_issues}{item.generated < 5 && <small className="table-sub">样本较少</small>}</td></tr>)}{metrics.data?.categories.length === 0 && <tr><td colSpan={4} className="empty-row">本期没有发现记录</td></tr>}</tbody></table></div><p className="effectiveness-note">OCR 当前结果没有稳定规则 ID，因此这里按类别统计，不推断单条审核规则的效果。</p></section>
      <section className="section"><div className="section-head"><h2>项目对比</h2></div><div className="table-scroll"><table><thead><tr><th>项目</th><th>本期新问题</th><th>本期确认修复</th><th>当前待处理</th><th>生成 / 发布</th></tr></thead><tbody>{metrics.data?.projects.map((item) => <tr key={item.id}><td><Link to={`/issues?repository_id=${item.id}&status=open`}>{item.name}</Link></td><td>{item.new_issues}</td><td>{item.fixed_issues}</td><td>{item.open_issues}</td><td>{item.generated} / {item.published}</td></tr>)}{metrics.data?.projects.length === 0 && <tr><td colSpan={5} className="empty-row">暂无项目</td></tr>}</tbody></table></div></section>
    </>}
    {!summary && !metrics.isLoading && !metrics.error && <section className="section empty-inline"><BarChart3 size={18} /> 暂无统计数据</section>}
  </div>;
}
