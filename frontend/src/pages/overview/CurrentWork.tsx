/** @description 分开呈现运行异常与代码问题，不相加不同对象或重复任务。 */
import { Link } from "react-router-dom";

import type { Overview } from "../../api/overview";

/** 仅使用持久化聚合，缺少问题摘要时保留列表入口而不补零。 */
export function CurrentWork({ data }: { /** 同一概览读事务的聚合。 */ data: Overview }) {
  const rows = [
    { label: "评审执行异常", count: data.summary.attention, unit: "个任务", path: "/jobs?view=attention", note: "失败或覆盖不完整，未被同一输入的后续完整结果覆盖" },
    { label: "飞书通知失败", count: data.summary.notification_failed, unit: "个任务通知失败", path: "/jobs?view=notification_failed", note: "通知与评审独立处理" },
    { label: "合并事件需要恢复", count: data.todo.events_attention, unit: "个事件", path: "/events?status=needs_attention&actionable_only=true", note: "当前启用项目" },
    { label: "合并前审查失败", count: data.todo.premerge_failed, unit: "个 MR", path: "/premerge?status=failed&latest_only=true&actionable_only=true", note: "当前启用范围 · 最新接收版本" },
    { label: "合并前审查覆盖不完整", count: data.todo.premerge_partial, unit: "个 MR", path: "/premerge?status=partial&latest_only=true&actionable_only=true", note: "当前启用范围 · 最新接收版本" },
  ].filter((row) => row.count > 0);
  const issues = data.issue_todo;
  const levels = [["critical", "严重"], ["high", "高危"], ["medium", "中危"], ["low", "低危"], ["unclassified", "未分级"]] as const;
  return <section className="section overview-work" aria-labelledby="current-work-title">
    <div className="section-head"><h2 id="current-work-title">当前工作</h2><span>全部项目 · 不受下方效果筛选影响</span></div>
    <div className="overview-work-grid">
      <section aria-labelledby="runtime-work-title"><h3 id="runtime-work-title">运行异常</h3>
        {rows.length ? <ul className="overview-exceptions">{rows.map((row) => <li key={row.path}>
          <div><span>{row.label}</span><small>{row.note}</small></div><strong>{row.count} {row.unit}</strong><Link to={row.path} aria-label={`查看${row.label}`}>查看</Link>
        </li>)}</ul> : <p className="overview-empty">当前未发现运行异常；代码问题处置情况请查看代码问题工作区。</p>}
        <p className="form-note">按类型分别计数，可能关联同一链路，不相加为唯一待办数。</p>
      </section>
      <section aria-labelledby="issue-work-title"><h3 id="issue-work-title">代码问题待处置</h3>
        {issues ? <><p className="overview-issue-count">待处置 <strong>{issues.open_count}</strong> 个问题</p>
          {issues.open_count === 0 ? <p>当前记录中没有待处置问题。</p> : <ul className="overview-severities">{levels.map(([key, label]) => <li key={key}>{key === "critical" || key === "high" ? <Link to={`/issues?status=open&severity=${key}`}>{label} {issues.severity_counts[key]}</Link> : <span>{label} {issues.severity_counts[key]}</span>}</li>)}</ul>}
        </> : <p>当前服务暂不提供汇总</p>}
        <Link className="overview-work-link" to="/issues?status=open">查看全部待处置问题</Link>
        <p className="form-note">按问题编号去重，含暂停项目的历史开放问题；人工处置不代表系统验证修复。</p>
      </section>
    </div>
  </section>;
}
