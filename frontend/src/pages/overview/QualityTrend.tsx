/** @description 反馈价值数量并排柱与同源数据表；按来源日分组，不冒充反馈事件历史。 */
import { Button, Tooltip } from "antd";
import { useId, useState } from "react";

import type { ReviewQuality } from "../../api/effectiveness";

import { feedbackSeries, qualityBuckets } from "./qualityView";

/** 四类反馈共用零基线；整日区域支持悬停、键盘和触控读取，表格保留精确对照。 */
export function QualityTrend({ quality, days }: {
  /** 与摘要及下钻共用的有效发现集合。 */ quality: ReviewQuality;
  /** UTC 窗口天数。 */ days: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const [activeDay, setActiveDay] = useState<string | null>(null);
  const tableId = useId();
  const rows = qualityBuckets(quality.trend, days);
  const peak = Math.max(1, ...rows.flatMap((row) => feedbackSeries.map((series) => row[series.key])));
  const step = Math.max(1, Math.ceil(peak / 4));
  const max = step * 4;
  return <div className="quality-trend">
    <div className="quality-legend">{feedbackSeries.map((series) => <span key={series.key}><i className={`quality-color-${series.key}`} />{series.label}</span>)}</div>
    <p className="quality-caption">按发现产生日分组，四类并排展示当前反馈；旧版修复标记按未评价处理，后续补标会更新历史柱。{days === 90 ? "从窗口首日起每 7 天汇总，末组按实际天数" : "每日"} · UTC · 悬停、聚焦或点击日期区域查看数量与占比，窄屏可横向滚动</p>
    {quality.summary.total === 0 && <p className="overview-empty">本期暂无有效发现样本</p>}
    <div className="quality-chart-viewport" role="region" aria-label="反馈趋势图，可横向滚动" tabIndex={0}
      onScroll={() => setActiveDay(null)} onKeyDown={(event) => { if (event.key === "Escape") setActiveDay(null); }}>
      <div className="overview-quant-chart quality-chart" style={{ minWidth: `${rows.length * 32 + 34}px` }} role="group" aria-label={`四类反馈按日期并排：有效发现 ${quality.summary.total} 条，有帮助 ${quality.summary.helpful}，误报 ${quality.summary.false_positive}，忽略 ${quality.summary.ignored}，未评价 ${quality.summary.unmarked}；纵轴 0 至 ${max} 条，精确数量可展开数据表`}>
        <div className="overview-chart-axis" aria-hidden="true">{[4, 3, 2, 1, 0].map((tick) => <span key={tick} style={{ top: `${(4 - tick) * 25}%` }}>{tick * step}</span>)}</div>
        <div className="overview-chart-plot">
          {[0, 1, 2, 3, 4].map((tick) => <div className="overview-gridline" aria-hidden="true" key={tick} style={{ top: `${tick * 25}%` }} />)}
          <div className="overview-chart-columns quality-feedback-columns">{rows.map((row, index) => <div className="overview-chart-column quality-day-column" key={row.start}>
            <div className="quality-bar-group" aria-hidden="true">{feedbackSeries.map((series) => <span key={series.key} className={`quality-color-${series.key}`} style={{ height: `${row[series.key] / max * 100}%` }} />)}</div>
            {(rows.length <= 7 || index === 0 || index === rows.length - 1 || (index % Math.ceil(rows.length / 5) === 0 && index < rows.length - 2)) && <small aria-hidden="true">{row.start.slice(5)}</small>}
            {/* 整个日期带命中，零值和柱间留白也能读取；单一活动日期避免多份提示叠加。
                提示由组件库 Portal 渲染，避免横向滚动容器裁切；滚动时关闭旧位置。
                点击只负责打开，避免触屏合成的悬停、聚焦先打开后又被点击切换关闭。 */}
            <Tooltip color="white" placement="top" trigger={["hover", "focus"]} mouseEnterDelay={0} mouseLeaveDelay={0.05}
              motion={{ motionName: "" }}
              open={activeDay === row.start} destroyOnHidden
              onOpenChange={(open) => setActiveDay((current) => open ? row.start : current === row.start ? null : current)}
              title={<div className="quality-tooltip-content">
                <strong>{row.start === row.end ? row.start : `${row.start} 至 ${row.end}`}（UTC）</strong>
                <p className="quality-tooltip-basis">{row.total > 0 ? `占${days === 90 ? "本区间" : "当天"}总发现（含未评价）` : `${days === 90 ? "本区间" : "当天"}暂无发现，占比不适用`}</p>
                <dl>{feedbackSeries.map((series) => <div key={series.key}><dt><i className={`quality-color-${series.key}`} />{series.label}</dt><dd>{row[series.key]} 条<span className="quality-tooltip-share">（{row.total > 0 ? `${(row[series.key] / row.total * 100).toFixed(1)}%` : "—"}）</span></dd></div>)}<div className="quality-tooltip-total"><dt>总发现</dt><dd>{row.total} 条</dd></div></dl>
              </div>}>
              <Button type="text" className="quality-day-hit" aria-label={`查看 ${row.start === row.end ? row.start : `${row.start} 至 ${row.end}`} 反馈数据`}
                onClick={() => setActiveDay(row.start)}
                onFocus={() => setActiveDay(row.start)} onBlur={() => setActiveDay((current) => current === row.start ? null : current)} />
            </Tooltip>
          </div>)}</div>
        </div>
      </div>
    </div>
    <Button aria-expanded={expanded} aria-controls={tableId} onClick={() => setExpanded(!expanded)}>{expanded ? "收起反馈数据" : "查看反馈数据"}</Button>
    <div id={tableId} hidden={!expanded} className="overview-trend-table"><table aria-label="反馈价值数据（UTC）"><thead><tr><th scope="col">{days === 90 ? "起止日期（UTC）" : "日期（UTC）"}</th>{feedbackSeries.map((series) => <th scope="col" key={series.key}>{series.label}</th>)}<th scope="col">总发现</th></tr></thead><tbody>{rows.map((row) => <tr key={row.start}><td>{row.start === row.end ? row.start : `${row.start} 至 ${row.end}`}</td>{feedbackSeries.map((series) => <td key={series.key}>{row[series.key]}</td>)}<td>{row.total}</td></tr>)}</tbody></table></div>
  </div>;
}
