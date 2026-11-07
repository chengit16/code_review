/** @description 编排平台复盘查询、URL 筛选与明细跳转；不写入业务事实或自动确认部署。 */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { getImprovementSummary } from "../api/improvementSummary";
import type { ImprovementAttentionGroup, ImprovementSummary } from "../api/improvementSummary";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { SelectField } from "../ui/SelectField";
import { formatTime } from "../ui/format";
import { ImprovementActivity, ImprovementBreakdown } from "./ImprovementSummaryCharts";
import { categoryLabels, codeLabels, deploymentLabels, kindLabels, progressLabels, verificationLabels } from "./improvementFields";

const themeLabels = { planned: "待开始", active: "进行中", paused: "已暂停", completed: "已完成", deferred: "暂缓" };
const phaseLabels = { planned: "待开始", active: "进行中", completed: "已完成", deferred: "暂缓" };

/** 读取全量当前累计及独立时间窗活动；筛选包含在查询键中，旧请求不能覆盖新视图。 */
export function ImprovementSummaryPanel({ token }: {
  /** 管理员内存会话，服务端继续承担授权。 */ token: string;
}) {
  const [params, setParams] = useSearchParams();
  const query = new URLSearchParams();
  for (const key of ["start_date", "end_date", "category"]) {
    const value = params.get(`summary_${key}`);
    if (value) query.set(key, value);
  }
  const summary = useQuery({ queryKey: ["improvement-summary", query.toString()],
    queryFn: ({ signal }) => getImprovementSummary(token, query, signal), refetchInterval: 30_000 });
  function apply(values: Record<string, string>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(values)) {
      if (value && value !== "all") next.set(`summary_${key}`, value); else next.delete(`summary_${key}`);
    }
    setParams(next);
  }
  return <section className="improvement-summary" aria-label="复盘汇总">
    <PageHeader title="复盘汇总" headingLevel={2} subtitle="分清累计进展、窗口内活动与仍需跟进的事项" actions={<button className="button button-secondary" type="button" disabled={summary.isFetching} onClick={() => void summary.refetch()}>刷新统计</button>} />
    <SummaryFilters key={query.toString()} params={query} onApply={apply} />
    <QueryState loading={summary.isLoading} error={summary.error} onRetry={() => void summary.refetch()} />
    {summary.isFetching && !summary.isLoading && <p role="status">正在刷新统计，当前仍为上次成功读取的结果。</p>}
    {summary.data && !summary.isError && <SummaryFacts data={summary.data} />}
  </section>;
}

function SummaryFilters({ params, onApply }: { params: URLSearchParams; onApply: (values: Record<string, string>) => void }) {
  const [start, setStart] = useState(params.get("start_date") ?? "");
  const [end, setEnd] = useState(params.get("end_date") ?? "");
  const [category, setCategory] = useState(params.get("category") ?? "all");
  return <form className="summary-filters section" onSubmit={(event) => { event.preventDefault(); onApply({ start_date: start, end_date: end, category }); }}>
    <label>活动开始日期<input type="date" value={start} onChange={(event) => setStart(event.target.value)} /></label>
    <label>活动结束日期<input type="date" value={end} onChange={(event) => setEnd(event.target.value)} /></label>
    <SelectField label="复盘分类" value={category} onValueChange={setCategory} options={[{ value: "all", label: "全部分类" }, ...Object.entries(categoryLabels).map(([value, label]) => ({ value, label }))]} />
    <button type="submit" className="button button-primary">应用复盘条件</button><button type="button" className="button button-secondary" onClick={() => { setStart(""); setEnd(""); setCategory("all"); onApply({ start_date: "", end_date: "", category: "" }); }}>重置条件</button>
    <p className="muted">日期留空默认近 30 天；最多 366 天。日期只影响活动趋势，不裁剪当前累计与待办。分类同时作用于两者。</p>
  </form>;
}

function SummaryFacts({ data }: { data: ImprovementSummary }) {
  const records = data.records;
  const link = (view: "records" | "themes", key: string, value: string) => {
    const search = new URLSearchParams();
    search.set(view === "themes" ? "theme_archive" : "archive", "all");
    if (view === "themes") search.set("view", "themes");
    if (data.category) search.set(view === "themes" ? "theme_category" : "category", data.category);
    search.set(view === "themes" ? `theme_${key}` : key, value);
    return `/improvements?${search}`;
  };
  const metrics = [
    { label: "当前台账记录", value: records.total, note: `问题 ${records.by_kind.problem} 条 · 阶段改进 ${records.by_kind.improvement} 条` },
    { label: "未解决记录（含暂缓）", value: data.unresolved.total, note: "不等同于验证待办或部署待确认" },
    { label: "已解决占比", value: records.total ? `${((records.by_status.resolved / records.total) * 100).toFixed(1)}%` : "—", note: `${records.by_status.resolved} / ${records.total} 条；不是期间解决率` },
    { label: "已关联主题的记录", value: records.linked_records, note: `按记录去重 · 未关联 ${records.total - records.linked_records} 条` },
    { label: "优化主题", value: data.themes.total, note: `已完成 ${data.themes.by_status.completed} 个 · 完成不代表已部署` },
    { label: "实施阶段", value: data.themes.phases.total, note: `已完成 ${data.themes.phases.by_status.completed} 个 · 分母是阶段而非主题` },
  ];
  return <>
    <div className="summary-scope"><p><strong>当前累计：</strong>{data.category ? categoryLabels[data.category] : "全部分类"} · 截至 {formatTime(data.generated_at)}</p><p><strong>活动窗口：</strong>{data.start_date} 至 {data.end_date}（{data.timezone}，含首尾日期）</p><p>累计与待办包含已归档内容（记录 {data.archived_records} 条、主题 {data.archived_themes} 个），归档不消除未解决事项。状态均来自人工持久化记录，不代表系统实际执行测试或核验部署。主题、阶段、台账分别计数；不推断复发率或平均解决时长。</p></div>
    {records.total === 0 && data.themes.total === 0 && <p className="empty-row">当前分类暂无台账或主题，统计为零不表示项目没有问题。</p>}
    <div className="summary-metrics">{metrics.map((metric) => <article aria-label={metric.label} key={metric.label}><h3>{metric.label}</h3><strong>{metric.value}</strong><p>{metric.note}</p></article>)}</div>
    <section className="section"><h3>当前记录分布</h3><div className="summary-distributions">
      <ImprovementBreakdown title="处理进展" counts={records.by_status} labels={progressLabels} href={(key) => link("records", "status", key)} />
      <ImprovementBreakdown title="记录分类" counts={records.by_category} labels={categoryLabels} href={(key) => link("records", "category", key)} />
      <ImprovementBreakdown title="记录类型" counts={records.by_kind} labels={kindLabels} href={(key) => link("records", "kind", key)} />
      <ImprovementBreakdown title="代码修改" counts={records.by_code_state} labels={codeLabels} />
      <ImprovementBreakdown title="本地验证" counts={records.by_verification_state} labels={verificationLabels} />
      <ImprovementBreakdown title="部署生效" counts={records.by_deployment_state} labels={deploymentLabels} />
    </div></section>
    <section className="section"><h3>当前主题与阶段分布</h3><div className="summary-distributions">
      <ImprovementBreakdown title="主题进展" counts={data.themes.by_status} labels={themeLabels} href={(key) => link("themes", "status", key)} />
      <ImprovementBreakdown title="主题分类" counts={data.themes.by_category} labels={categoryLabels} href={(key) => link("themes", "category", key)} />
      <ImprovementBreakdown title="阶段进展" counts={data.themes.phases.by_status} labels={phaseLabels} />
      <ImprovementBreakdown title="阶段代码修改" counts={data.themes.phases.by_code_state} labels={codeLabels} />
      <ImprovementBreakdown title="阶段本地验证" counts={data.themes.phases.by_verification_state} labels={verificationLabels} />
      <ImprovementBreakdown title="阶段部署生效" counts={data.themes.phases.by_deployment_state} labels={deploymentLabels} />
    </div></section>
    <ImprovementActivity days={data.activity} />
    <section className="section"><h3>当前跟进清单</h3><p className="muted">每组显示最久未更新的前 10 条；各组可能重叠，不可相加为独立问题数。所有待办均为当前分类累计，不受活动日期影响。</p><div className="summary-attention-grid">
      <Attention title="未解决记录（含暂缓）" group={data.unresolved} hint="当前状态不是已解决" />
      <Attention title="验证待跟进" group={data.verification_attention} hint="验证失败、受阻，或代码已修改但未运行验证" />
      <Attention title="部署待确认" group={data.deployment_pending} hint="本地验证通过，部署为未部署或无法确认；不含不适用" />
      <Attention title="未完成主题" group={data.unfinished_themes} hint="包含待开始、进行中、暂停和暂缓" themes />
    </div></section>
  </>;
}

function Attention({ title, group, hint, themes = false }: { title: string; group: ImprovementAttentionGroup; hint: string; themes?: boolean }) {
  const labels: Record<string, string> = themes ? themeLabels : progressLabels;
  return <section className="summary-attention" aria-label={title}><h4>{title}（{group.total}）</h4><p className="muted">{hint}</p><ul>{group.items.map((item) => <li key={item.id}>
    <Link to={themes ? `/improvements/themes/${item.id}` : `/improvements/${item.id}`}>#{item.id} · {item.title}</Link>
    <small>{item.archived_at ? "已归档 · " : ""}{labels[item.status] ?? item.status} · 更新于 {formatTime(item.updated_at)}</small>
  </li>)}</ul>{group.total === 0 ? <p className="muted">当前没有符合条件的事项。</p> : <p className="muted">显示 {group.items.length} / {group.total} 条，打开详情查看证据与追加进展。</p>}</section>;
}
