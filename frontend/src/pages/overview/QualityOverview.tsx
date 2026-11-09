/** @description 首页默认展示价值反馈；问题处置单独查看，不与问题个数混算。 */
import { Segmented } from "antd";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import type { EffectivenessSnapshot } from "../../api/effectiveness";

import { IssueTrend } from "./IssueTrend";
import { DispositionTrend } from "./DispositionTrend";
import { QualityTrend } from "./QualityTrend";
import { dispositionSeries, feedbackSeries, qualityRatio, qualitySampleHref } from "./qualityView";

/** 沿用项目范围；当前处置不受日期裁剪，旧 API 明确待升级而非补零。 */
export function QualityOverview({ data, days, repositoryId }: {
  /** 同一业务读取快照。 */ data: EffectivenessSnapshot;
  /** 当前 UTC 窗口。 */ days: number;
  /** 当前项目，可为空。 */ repositoryId: string;
}) {
  const [mode, setMode] = useState("quality");
  const [params] = useSearchParams();
  const quality = data.quality;
  const counts = quality?.summary;
  const marked = counts ? counts.helpful + counts.false_positive : 0;
  const statuses = data.current_status_counts;
  const current = quality?.dispositions?.summary;
  return <section className="overview-panel quality-overview" aria-label="评审质量与处置">
    <div className="section-head"><h2>评审质量与处置</h2><Segmented aria-label="质量图表视图" value={mode} onChange={setMode} options={[{ value: "current", label: "问题状态" }, { value: "quality", label: "反馈价值" }, { value: "issues", label: "问题变化" }]} /></div>
    {mode === "current" && (quality && current ? <>
      <dl className="quality-facts">{dispositionSeries.map((series) => <div key={series.key}><dt><i className={`quality-color-${series.key}`} />{series.label}</dt><dd><Link to={qualitySampleHref(params, quality, { status: series.key })} aria-label={`查看${series.label} ${current[series.key]} 条发现`}>{current[series.key]}</Link><small>条</small></dd></div>)}</dl>
      <div className="quality-ratios"><Link to={qualitySampleHref(params, quality)}>查看全部 {current.total} 条样本</Link>{current.unknown > 0 && <Link to={qualitySampleHref(params, quality, { status: "unknown" })}>状态待核实 {current.unknown} 条</Link>}</div>
      <DispositionTrend quality={quality} days={days} />
    </> : <p className="overview-empty">当前服务尚未提供独立误报及处置统计，请升级 API；不能用历史评价替代或补零。</p>)}
    {mode === "quality" && (quality && counts ? <>
      <dl className="quality-facts">{feedbackSeries.map((series) => <div key={series.key}><dt><i className={`quality-color-${series.key}`} />{series.label}</dt><dd><Link to={qualitySampleHref(params, quality, { feedback: series.feedback })} aria-label={`查看${series.label} ${counts[series.key]} 条发现`}>{counts[series.key]}</Link><small>条</small></dd></div>)}</dl>
      <div className="quality-ratios"><span>有效评价占比 <strong>{qualityRatio(marked, counts.total)}</strong></span><span>误报占已评价 <strong>{qualityRatio(counts.false_positive, marked, 5)}</strong></span><Link to={qualitySampleHref(params, quality)}>查看全部 {counts.total} 条样本</Link></div>
      {counts.total > 0 && marked === 0 && <p className="quality-caption">本期发现尚无有帮助或误报评价，不能据此判断评审没有帮助。</p>}
      <QualityTrend quality={quality} days={days} />
    </> : <p className="overview-empty">当前服务暂不提供反馈质量统计，请升级 API；缺失不代表零反馈。</p>)}
    {quality && quality.unavailable_sources > 0 && <p role="alert">另有 {quality.unavailable_sources} 个来源记录待核实，当前质量统计可能不完整。</p>}
    <div className="quality-dispositions" aria-label="当前问题处置"><span>当前问题 · 不限时间</span>{statuses ? <>{dispositionSeries.map(({ key, label }) => statuses[key] === undefined ? <span key={key}>{label}待升级</span> : <Link key={key} to={`/issues?status=${key}${repositoryId ? `&repository_id=${encodeURIComponent(repositoryId)}` : ""}`}>{label} <strong>{statuses[key]}</strong> 个</Link>)}<span>已合并 {statuses.merged} 个</span></> : <span>当前处置汇总待升级，不能用本期忽略数代替。</span>}</div>
    {mode === "issues" && <IssueTrend rows={data.trend} days={days} />}
    <p className="quality-caption">反馈按发现条数，问题处置按唯一编号。忽略是不采纳，不算误报；未评价与明确忽略分开。误报占比仅以有帮助 + 误报为分母，少于 5 条不显示比例，不代表模型准确率。反馈不自动改变问题状态。</p>
  </section>;
}
