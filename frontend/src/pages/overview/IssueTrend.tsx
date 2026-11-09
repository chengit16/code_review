/** @description 趋势柱图与等价语义表共享数据；UTC 聚合不伪装本地日期。 */
import { Button } from "antd";
import { useId, useState } from "react";

/** 后端按 UTC 日期生成的趋势行。 */
export interface TrendRow {
  /** UTC 日历日期。 */ day: string;
  /** 新增问题数。 */ new: number;
  /** 人工标记修复数。 */ fixed: number;
}

/** 90 天每七行一桶，保留真实起止日期，末桶不补造日期。 */
export function trendBuckets(rows: TrendRow[], days: number) {
  const size = days === 90 ? 7 : 1;
  const buckets = [];
  for (let index = 0; index < rows.length; index += size) {
    const group = rows.slice(index, index + size);
    buckets.push({ start: group[0].day, end: group[group.length - 1].day,
      new: group.reduce((sum, item) => sum + item.new, 0),
      fixed: group.reduce((sum, item) => sum + item.fixed, 0) });
  }
  return buckets;
}

/** 触控与键盘可展开精确数据；柱图无需逐柱进入 Tab 顺序。 */
export function IssueTrend({ rows, days }: {
  /** 与表格共用的服务端趋势。 */ rows: TrendRow[];
  /** 7、30 或 90 天。 */ days: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const tableId = useId();
  const buckets = trendBuckets(rows, days);
  const peak = Math.max(1, ...buckets.map((item) => Math.max(item.new, item.fixed)));
  const unit = 10 ** Math.floor(Math.log10(peak));
  const step = Math.max(1, Math.ceil(peak / unit / 4) * unit);
  const max = step * 4;
  const summary = `本期新问题 ${buckets.reduce((sum, item) => sum + item.new, 0)} 个，人工标记修复 ${buckets.reduce((sum, item) => sum + item.fixed, 0)} 个`;
  return <section className="overview-panel overview-trend" aria-label="问题变化">
    <div className="section-head"><h2>问题变化</h2><span>{days === 90 ? "每 7 天汇总" : "每日"} · UTC</span></div>
    <div className="trend-legend"><span className="trend-key trend-key-new" />新问题 <span className="trend-key trend-key-fixed" />人工标记修复</div>
    <div className="overview-quant-chart" role="img" aria-label={`${days} 天问题趋势（UTC）：${summary}；纵轴 0 至 ${max} 个，每格 ${step} 个`}>
      <div className="overview-chart-axis" aria-hidden="true">{[4, 3, 2, 1, 0].map((tick) => <span key={tick} style={{ top: `${(4 - tick) * 25}%` }}>{tick * step}</span>)}</div>
      <div className="overview-chart-plot" aria-hidden="true">
        {[0, 1, 2, 3, 4].map((tick) => <div className="overview-gridline" key={tick} style={{ top: `${tick * 25}%` }} />)}
        <div className="overview-chart-columns">{buckets.map((item, index) => <div className="overview-chart-column" key={item.start} title={`${item.start} 至 ${item.end}：新增 ${item.new}，人工标记修复 ${item.fixed}`}>
          <div className="overview-chart-bars"><span className="trend-bar-new" style={{ height: `${item.new / max * 100}%` }} /><span className="trend-bar-fixed" style={{ height: `${item.fixed / max * 100}%` }} /></div>
          {(index === 0 || index === buckets.length - 1 || (index % Math.ceil((buckets.length - 1) / 4) === 0 && index < buckets.length - 2)) && <small>{item.start.slice(5)}</small>}
        </div>)}</div>
      </div>
    </div>
    <Button aria-expanded={expanded} aria-controls={tableId} onClick={() => setExpanded(!expanded)}>{expanded ? "收起趋势数据" : "查看趋势数据"}</Button>
    <div id={tableId} hidden={!expanded} className="overview-trend-table"><table aria-label="问题变化数据（UTC）"><thead><tr><th scope="col">{days === 90 ? "起止日期（UTC）" : "日期（UTC）"}</th><th scope="col">新问题</th><th scope="col">人工标记修复</th></tr></thead><tbody>{buckets.map((item) => <tr key={item.start}><td>{item.start === item.end ? item.start : `${item.start} 至 ${item.end}`}</td><td>{item.new}</td><td>{item.fixed}</td></tr>)}</tbody></table>{!buckets.length && <p>本期没有趋势记录</p>}</div>
  </section>;
}
