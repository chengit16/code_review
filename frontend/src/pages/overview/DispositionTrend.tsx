/** @description 当前处置数量并排柱与同源数据表；按来源日分组，不冒充反馈事件历史。 */
import { Button } from "antd";
import { useId, useState } from "react";

import type { ReviewQuality } from "../../api/effectiveness";

import { dispositionSeries } from "./qualityView";

/** 四种状态共用零基线并排比较；键盘和触控通过表格读取精确值。 */
export function DispositionTrend({ quality, }: {
  /** 与摘要及下钻共用的有效发现集合。 */ quality: ReviewQuality;
  /** 当前窗口，保留调用契约。 */ days: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const tableId = useId();
  const current = quality.dispositions;
  if (!current) return null;
  const rows = current.trend.map((row) => ({ ...row, start: row.day, end: row.day }));
  const peak = Math.max(1, ...rows.flatMap((row) => dispositionSeries.map((series) => row[series.key])));
  const step = Math.max(1, Math.ceil(peak / 4));
  const max = step * 4;
  return <div className="quality-trend">
    <div className="quality-legend">{dispositionSeries.map((series) => <span key={series.key}><i className={`quality-color-${series.key}`} />{series.label}</span>)}</div>
    <p className="quality-caption">按发现产生日分组，四种状态并排展示当前状态；后续处置会更新历史柱。每日 · UTC · 窄屏可横向滚动</p>
    {current.summary.total === 0 && <p className="overview-empty">本期暂无有效发现样本</p>}
    <div className="quality-chart-viewport" role="region" aria-label="状态趋势图，可横向滚动" tabIndex={0}>
      <div className="overview-quant-chart quality-chart" style={{ minWidth: `${rows.length * 32 + 34}px` }} role="img" aria-label={`四种状态按日期并排：有效发现 ${current.summary.total} 条，待处理 ${current.summary.open}，已修复 ${current.summary.fixed}，已忽略 ${current.summary.ignored}，误报 ${current.summary.false_positive}，待核实 ${current.summary.unknown}；纵轴 0 至 ${max} 条，精确数量可展开数据表`}>
        <div className="overview-chart-axis" aria-hidden="true">{[4, 3, 2, 1, 0].map((tick) => <span key={tick} style={{ top: `${(4 - tick) * 25}%` }}>{tick * step}</span>)}</div>
        <div className="overview-chart-plot" aria-hidden="true">
          {[0, 1, 2, 3, 4].map((tick) => <div className="overview-gridline" key={tick} style={{ top: `${tick * 25}%` }} />)}
          <div className="overview-chart-columns">{rows.map((row, index) => <div className="overview-chart-column" key={row.start} title={`${row.start} 至 ${row.end}：${dispositionSeries.map((series) => `${series.label} ${row[series.key]}`).join("，")}；总计 ${row.total}`}>
            <div className="quality-bar-group">{dispositionSeries.map((series) => <span key={series.key} className={`quality-color-${series.key}`} style={{ height: `${row[series.key] / max * 100}%` }} />)}</div>
            {(rows.length <= 7 || index === 0 || index === rows.length - 1 || (index % Math.ceil(rows.length / 5) === 0 && index < rows.length - 2)) && <small>{row.start.slice(5)}</small>}
          </div>)}</div>
        </div>
      </div>
    </div>
    <Button aria-expanded={expanded} aria-controls={tableId} onClick={() => setExpanded(!expanded)}>{expanded ? "收起状态数据" : "查看状态数据"}</Button>
    <div id={tableId} hidden={!expanded} className="overview-trend-table"><table aria-label="当前处置数据（UTC）"><thead><tr><th scope="col">日期（UTC）</th>{dispositionSeries.map((series) => <th scope="col" key={series.key}>{series.label}</th>)}<th scope="col">待核实</th><th scope="col">总发现</th></tr></thead><tbody>{rows.map((row) => <tr key={row.start}><td>{row.start === row.end ? row.start : `${row.start} 至 ${row.end}`}</td>{dispositionSeries.map((series) => <td key={series.key}>{row[series.key]}</td>)}<td>{row.unknown}</td><td>{row.total}</td></tr>)}</tbody></table></div>
  </div>;
}
