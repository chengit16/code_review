/** @description 全平台运行摘要是业务图表的辅助入口；不同异常类型不相加为唯一待办。 */
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import type { Overview } from "../../api/overview";

/** 所有运行入口保持原有精确范围，与项目及时间筛选明确分离。 */
export function RuntimeSummary({ data, workerStatus, readStatus }: {
  /** 全平台运行快照，尚无结果时不补零。 */ data?: Overview;
  /** 健康状态独立读取，不因运行数据失败消失。 */ workerStatus: ReactNode;
  /** 运行摘要独立成功读取时间。 */ readStatus: ReactNode;
}) {
  const rows = data ? [
    { label: "评审执行异常", count: data.summary.attention, path: "/jobs?view=attention" },
    { label: "飞书通知失败", count: data.summary.notification_failed, path: "/jobs?view=notification_failed" },
    { label: "合并事件需要恢复", count: data.todo.events_attention, path: "/events?status=needs_attention&actionable_only=true" },
    { label: "合并前审查失败", count: data.todo.premerge_failed, path: "/premerge?status=failed&latest_only=true&actionable_only=true" },
    { label: "合并前审查覆盖不完整", count: data.todo.premerge_partial, path: "/premerge?status=partial&latest_only=true&actionable_only=true" },
  ].filter((row) => row.count > 0) : [];
  return <section className="overview-runtime" aria-label="全平台运行摘要">
    <div className="overview-runtime-head">{workerStatus}<span className="overview-scope">全平台 · 不随项目和时间筛选变化</span></div>
    {data && <div className="overview-runtime-links"><Link to="/jobs?view=active">{data.activity ? <>活动任务 <strong>{data.activity.total}</strong>（排队 {data.activity.queued} · 运行 {data.activity.running}）</> : "活动任务汇总暂不可用"}</Link>
      {rows.map((row) => <Link key={row.path} to={row.path} aria-label={`查看${row.label} ${row.count}`}>{row.label} <strong>{row.count}</strong></Link>)}
      {!rows.length && <span>当前未发现运行异常</span>}
    </div>}
    <div className="overview-runtime-foot">{readStatus}{rows.length > 0 && <span>各类异常可能关联同一链路，不相加；事件及合并前入口限定当前启用范围。</span>}</div>
  </section>;
}
