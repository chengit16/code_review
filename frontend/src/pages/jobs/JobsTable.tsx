/** @description 任务 Ant Design 表格；桌面扫描主结论，窄屏使用摘要列，选择范围由父页维护。 */
import { Checkbox, Collapse, Grid, Table } from "antd";
import type { TableColumnsType } from "antd";
import { Link } from "react-router-dom";

import type { ReviewJob } from "../../api/types";
import { Status } from "../../ui/Status";
import { formatTime, shortSha } from "../../ui/format";
import { JobCostFacts, JobTimeFacts, resultText } from "../JobExecution";

/** 使用同一份服务端事实构造桌面和窄屏，不把费用或缺失耗时改写为零。 */
export function JobsTable({ items, canEdit, selectable, targets, disabled, onSelect, detailPath, loading, failed }: {
  /** 当前页任务。 */ items: ReviewJob[];
  /** 仅控制选择界面，服务端仍负责授权。 */ canEdit: boolean;
  /** 本页允许重审的终态编号。 */ selectable: number[];
  /** 当前显式勾选与允许集合的交集。 */ targets: number[];
  /** 查询或确认期间冻结选择。 */ disabled: boolean;
  /** 更新本页选择，不隐式选择其他页。 */ onSelect: (ids: number[]) => void;
  /** 包含当前筛选 URL 的详情路径。 */ detailPath: (id: number) => string;
  /** 首次加载反馈。 */ loading: boolean;
  /** 查询失败时不展示无任务结论。 */ failed: boolean;
}) {
  const screens = Grid.useBreakpoint();
  const compact = !screens.md;
  const cell = (label: string) => ({ className: "jobs-fact-cell", "data-label": label });
  const desktop: TableColumnsType<ReviewJob> = [
    { title: "任务 / 来源", key: "source", width: 225, onCell: () => cell("任务 / 来源"), render: (_, job) => <div className="jobs-source"><Link to={detailPath(job.id)}>任务 #{job.id}</Link><strong>{job.repository_name}</strong><small>{job.mr_iid > 0 ? `MR !${job.mr_iid}` : "默认分支 Push"} · {job.target_branch}</small><span className="mono">{shortSha(job.commit_sha)}</span></div> },
    { title: "提交人", dataIndex: "commit_author", width: 120, onCell: () => cell("提交人"), render: (value: string | null) => value?.trim() || "未记录" },
    { title: "评审结果", key: "result", width: 240, onCell: () => cell("评审结果"), render: (_, job) => <><Status value={job.effective_status ?? job.status} /><small className="table-sub">{resultText(job)}</small></> },
    { title: "飞书通知", key: "notification", width: 135, onCell: () => cell("飞书通知"), render: (_, job) => <Notification job={job} /> },
    { title: "耗时 / 尝试", key: "timing", width: 230, onCell: () => cell("耗时 / 尝试"), render: (_, job) => <JobTimeFacts job={job} /> },
    { title: "预估费用", key: "cost", width: 150, onCell: () => cell("预估费用"), render: (_, job) => <JobCostFacts job={job} /> },
    { title: "创建时间", key: "created", width: 165, onCell: () => cell("创建时间"), render: (_, job) => formatTime(job.created_at) },
    { title: "操作", key: "action", width: 75, fixed: "right", render: (_, job) => <Link aria-label={`查看任务 ${job.id}`} to={detailPath(job.id)}>详情</Link> },
  ];
  const mobile: TableColumnsType<ReviewJob> = [{ title: "任务与评审摘要", key: "summary", render: (_, job) => <div className="task-mobile-summary jobs-mobile-summary">
    <div className="jobs-mobile-heading"><Link aria-label={`查看任务 ${job.id}`} to={detailPath(job.id)}>任务 #{job.id}</Link><Status value={job.effective_status ?? job.status} /></div>
    <strong>{job.repository_name}</strong><small>{job.mr_iid > 0 ? `MR !${job.mr_iid}` : "默认分支 Push"} · {job.target_branch}</small>
    <span>提交人：{job.commit_author?.trim() || "未记录"}</span><span>{resultText(job)}</span><JobTimeFacts job={job} />
    <Collapse ghost size="small" items={[{ key: "more", label: "更多信息", children: <dl className="jobs-mobile-facts"><div><dt>提交</dt><dd className="mono">{shortSha(job.commit_sha)}</dd></div><div><dt>飞书通知</dt><dd><Notification job={job} /></dd></div><div><dt>预估费用</dt><dd><JobCostFacts job={job} /></dd></div><div><dt>创建时间</dt><dd>{formatTime(job.created_at)}</dd></div></dl> }]} />
  </div> }];
  const selection: TableColumnsType<ReviewJob> = canEdit ? [{ key: "selection", width: compact ? 40 : 48,
    title: <Checkbox aria-label="全选本页可重审任务" checked={targets.length > 0 && targets.length === selectable.length} indeterminate={targets.length > 0 && targets.length < selectable.length} disabled={disabled || !selectable.length} onChange={(event) => onSelect(event.target.checked ? selectable : [])} />,
    render: (_, job) => <Checkbox aria-label={`选择任务 ${job.id}`} checked={targets.includes(job.id)} disabled={disabled || !selectable.includes(job.id)} onChange={(event) => onSelect(event.target.checked ? [...targets, job.id] : targets.filter((id) => id !== job.id))} />,
  }] : [];
  return <section aria-label="评审任务列表" className="jobs-table"><Table<ReviewJob> rowKey="id" columns={[...selection, ...(compact ? mobile : desktop)]}
    dataSource={items} loading={loading} pagination={false} size="small" tableLayout="fixed" scroll={compact ? undefined : { x: 1440 }}
    locale={{ emptyText: loading ? "正在读取任务…" : failed ? "任务读取失败，请重新读取，不能据此判断没有任务。" : "当前筛选下没有任务，可清空筛选或检查项目接入。" }} /></section>;
}
function Notification({ job }: { job: ReviewJob }) {
  return <>{job.delivery_status ? <Status value={job.delivery_status} /> : "未创建"}{Boolean(job.recovery_delivery_failed_count) && <small className="table-sub">补充通知失败 {job.recovery_delivery_failed_count} 条</small>}</>;
}
