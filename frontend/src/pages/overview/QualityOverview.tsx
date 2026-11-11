/** @description 首页呈现同一服务端快照的反馈数量、全部发现占比和处理进度；不写入反馈或推断代码修复。 */
import { Collapse } from "antd";
import { Link, useSearchParams } from "react-router-dom";

import type { EffectivenessSnapshot } from "../../api/effectiveness";

import { QualityTrend } from "./QualityTrend";
import { feedbackSeries, qualityRatio, qualitySampleHref } from "./qualityView";

/** 同一 UTC 窗口下按当前反馈判断处理，不推断代码已经修复。 */
export function QualityOverview({ data, days }: {
  /** 同一业务读取快照。 */ data: EffectivenessSnapshot;
  /** 当前 UTC 窗口。 */ days: number;
  /** 兼容父页范围，实际范围由 URL 和显式窗口沿用。 */ repositoryId: string;
}) {
  const [params] = useSearchParams();
  const quality = data.quality;
  const counts = quality?.summary;
  const evaluated = counts ? counts.helpful + counts.false_positive : 0;
  return <section className="overview-panel quality-overview" aria-label="评审反馈">
    <div className="section-head"><h2>评审反馈</h2><span>当前有效发现 · 近 {days} 天</span></div>
    {quality && counts ? <>
      <dl className="quality-facts">{feedbackSeries.map((series) => <div key={series.key}>
        <dt><i className={`quality-color-${series.key}`} />{series.label}</dt>
        <dd><Link to={qualitySampleHref(params, quality, { feedback: series.feedback })} aria-label={`查看${series.label} ${counts[series.key]} 条发现`}>{counts[series.key]}</Link><small>条</small>
          <span className="quality-fact-share">{counts.total > 0 ? `占 ${(counts[series.key] / counts.total * 100).toFixed(1)}%` : "—（无样本）"}</span>
        </dd>
      </div>)}</dl>
      <p className="quality-share-caption">占比以当前筛选范围内全部 {counts.total} 条有效发现为分母（含未评价），四舍五入保留 1 位小数。</p>
      <div className="quality-ratios"><Link to={qualitySampleHref(params, quality, { handling: "handled" })}>已处理 {counts.total - counts.unmarked} 条</Link><Link to={qualitySampleHref(params, quality, { handling: "pending" })}>待处理 {counts.unmarked} 条</Link><span>处理完成率 <strong>{qualityRatio(counts.total - counts.unmarked, counts.total)}</strong></span><Link to={qualitySampleHref(params, quality)}>查看全部 {counts.total} 条发现</Link></div>
      <QualityTrend quality={quality} days={days} />
      <Collapse ghost items={[{ key: "method", label: "反馈统计口径", children: <><p>有效评价占比 {qualityRatio(evaluated, counts.total)}；误报占已评价 {qualityRatio(counts.false_positive, evaluated, 5)}。</p><p>有帮助、误报和忽略均表示已处理，撤销后回到未评价。忽略不参与有效评价及误报占比分母，历史修复反馈按未评价处理；已处理不代表代码已修复。误报评价少于 5 条不展示比例，不代表模型准确率。</p></> }]} />
    </> : <p className="overview-empty">当前服务暂不提供反馈统计，请升级 API；缺失不代表零反馈。</p>}
    {quality && quality.unavailable_sources > 0 && <p role="alert">另有 {quality.unavailable_sources} 个来源记录待核实，当前反馈统计可能不完整。</p>}
  </section>;
}
