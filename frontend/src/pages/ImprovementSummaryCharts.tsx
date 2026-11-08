/** @description 复盘分布与活动图表；同时提供文字数值和逐日表格，不只依赖颜色传达事实。 */
import { Link } from "react-router-dom";

import type { ImprovementActivityDay } from "../api/improvementSummary";
import { ListTable } from "../ui/ListTable";

/** 横向分布条；点击回到明确筛选的列表，零分母不生成百分比。 */
export function ImprovementBreakdown({ title, counts, labels, href }: {
  /** 分组名称，也是区域可访问名称。 */ title: string;
  /** 固定状态分组计数。 */ counts: Record<string, number>;
  /** 与业务契约一致的中文标签。 */ labels: Record<string, string>;
  /** 可选的只读明细跳转，参数是当前状态键。 */ href?: (key: string) => string;
}) {
  const max = Math.max(1, ...Object.values(counts));
  return <section className="summary-breakdown" aria-label={title}><h3>{title}</h3><ul>
    {Object.entries(labels).map(([key, label]) => <li key={key}><div>{href ? <Link to={href(key)}>{label}</Link> : <span>{label}</span>}<strong>{counts[key] ?? 0}</strong></div>
      <span className="summary-meter" aria-hidden="true"><span style={{ width: `${((counts[key] ?? 0) / max) * 100}%` }} /></span></li>)}
  </ul></section>;
}

/** 活动柱图不代表解决趋势；逐日表格保留新增与追加两种口径的原始数值。 */
export function ImprovementActivity({ days }: {
  /** 服务端填零并按北京时间日期升序排列的数据。 */ days: ImprovementActivityDay[];
}) {
  const max = Math.max(1, ...days.flatMap((day) => [day.records_created + day.themes_created, day.record_updates + day.theme_updates]));
  const totals = days.reduce((sum, day) => ({
    records: sum.records + day.records_created, recordUpdates: sum.recordUpdates + day.record_updates,
    themes: sum.themes + day.themes_created, themeUpdates: sum.themeUpdates + day.theme_updates,
  }), { records: 0, recordUpdates: 0, themes: 0, themeUpdates: 0 });
  return <section className="section" aria-label="窗口内活动"><h3>窗口内活动</h3>
    <p>新增记录 {totals.records} 条 · 记录追加进展 {totals.recordUpdates} 次 · 新增主题 {totals.themes} 个 · 主题追加进展 {totals.themeUpdates} 次</p>
    <p className="muted">绿色为新增记录与主题，棕色为追加进展。追加次数包含归档与恢复；一次保存不是解决一次；初始版本不重复计为追加。分类按当前归属统计，不是历史分类回放。</p>
    <div className="summary-chart-scroll" tabIndex={0} role="region" aria-label="活动柱图，可横向滚动">
      <div className="summary-activity-chart" style={{ minWidth: Math.max(280, days.length * 8) }} role="img" aria-label={`按日活动柱图，共 ${days.length} 天；精确数值见逐日活动明细表`}>
        {days.map((day) => <div className="summary-day" key={day.date} title={`${day.date}：新增 ${day.records_created + day.themes_created}，追加 ${day.record_updates + day.theme_updates}`}>
          <span style={{ height: `${((day.records_created + day.themes_created) / max) * 100}%` }} />
          <span className="summary-day-updates" style={{ height: `${((day.record_updates + day.theme_updates) / max) * 100}%` }} />
        </div>)}
      </div>
    </div>
    <div className="summary-chart-axis"><span>{days[0]?.date}</span><span>{days.at(-1)?.date}</span></div>
    <details><summary>逐日活动明细</summary><p>北京时间自然日的新增与追加进展</p><ListTable rowKey="date" pagination={false} scroll={{ x: 600 }} dataSource={days} columns={[
      { title: "日期", dataIndex: "date", key: "date" }, { title: "新增记录", dataIndex: "records_created", key: "records" },
      { title: "记录追加", dataIndex: "record_updates", key: "updates" }, { title: "新增主题", dataIndex: "themes_created", key: "themes" },
      { title: "主题追加", dataIndex: "theme_updates", key: "theme_updates" },
    ]} /></details>
  </section>;
}
