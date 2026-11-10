/** @description 任务 Ant Design 表格；桌面扫描主结论，窄屏使用摘要列，选择范围由父页维护。 */
import { Checkbox, Grid, Table } from "antd";
import type { TableColumnsType } from "antd";
import { Link, useNavigate } from "react-router-dom";

import type { ReviewJob } from "../../api/types";
import { Status } from "../../ui/Status";
import { formatTime, shortSha } from "../../ui/format";
import { detailRowProps } from "../../ui/detailRow";
import { JobTimeFacts } from "../JobExecution";

import { IssueSummary } from "./TaskIssueSummary";

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
  const navigate = useNavigate();
  const compact = !screens.md;
  const cell = (label: string) => ({ className: "jobs-fact-cell", "data-label": label });
  const desktop: TableColumnsType<ReviewJob> = [
    { title: "任务 / 项目", key: "source", width: 185, onCell: () => cell("任务 / 项目"), render: (_, job) => <div className="jobs-source"><Link aria-label={`查看任务 ${job.id}`} title={job.repository_name} to={detailPath(job.id)}>任务 #{job.id} · {job.repository_name}</Link><small title={`${job.target_branch ?? ""} · ${job.commit_sha}`}>{job.mr_iid > 0 ? `MR !${job.mr_iid}` : "Push"} · {job.target_branch} · <span className="mono">{shortSha(job.commit_sha)}</span></small></div> },
    { title: "提交人", dataIndex: "commit_author", width: 90, onCell: () => cell("提交人"), render: (value: string | null) => value?.trim() || "未记录" },
    { title: "评审状态", key: "result", width: 115, onCell: () => cell("评审状态"), render: (_, job) => <ReviewState job={job} /> },
    { title: "发现 / 价值反馈", key: "issues", width: 230, onCell: () => cell("发现 / 价值反馈"), render: (_, job) => <IssueSummary job={job} /> },
    { title: "飞书", key: "notification", width: 90, onCell: () => cell("飞书"), render: (_, job) => <Notification job={job} /> },
    { title: "耗时 / 尝试", key: "timing", width: 160, onCell: () => cell("耗时 / 尝试"), render: (_, job) => <JobTimeFacts job={job} compact /> },
    { title: "创建时间", key: "created", width: 105, onCell: () => cell("创建时间"), render: (_, job) => <time title={formatTime(job.created_at)}>{shortCreatedAt(job.created_at)}</time> },
  ];
  const mobile: TableColumnsType<ReviewJob> = [{ title: "任务与评审摘要", key: "summary", render: (_, job) => <div className="task-mobile-summary jobs-mobile-summary">
    <div className="jobs-mobile-heading"><Link aria-label={`查看任务 ${job.id}`} to={detailPath(job.id)}>任务 #{job.id} · {job.repository_name}</Link><ReviewState job={job} /></div>
    <small>{job.mr_iid > 0 ? `MR !${job.mr_iid}` : "Push"} · {job.target_branch} · {shortSha(job.commit_sha)}</small>
    <IssueSummary job={job} /><details><summary>提交、耗时与通知</summary><span>提交人：{job.commit_author?.trim() || "未记录"}</span><JobTimeFacts job={job} compact /><span>创建：{formatTime(job.created_at)}</span><Notification job={job} /></details>
  </div> }];
  const selection: TableColumnsType<ReviewJob> = canEdit ? [{ key: "selection", width: compact ? 40 : 48,
    title: <Checkbox aria-label="全选本页可重审任务" checked={targets.length > 0 && targets.length === selectable.length} indeterminate={targets.length > 0 && targets.length < selectable.length} disabled={disabled || !selectable.length} onChange={(event) => onSelect(event.target.checked ? selectable : [])} />,
    render: (_, job) => <Checkbox aria-label={`选择任务 ${job.id}`} checked={targets.includes(job.id)} disabled={disabled || !selectable.includes(job.id)} onChange={(event) => onSelect(event.target.checked ? [...targets, job.id] : targets.filter((id) => id !== job.id))} />,
  }] : [];
  return <section aria-label="评审任务列表" className="jobs-table"><Table<ReviewJob> rowKey="id" columns={[...selection, ...(compact ? mobile : desktop)]}
    onRow={(job) => detailRowProps(() => navigate(detailPath(job.id)), `查看任务 ${job.id}`)}
    dataSource={items} loading={loading} pagination={false} size="small" tableLayout="fixed" scroll={compact ? undefined : { x: 1040 }}
    locale={{ emptyText: loading ? "正在读取任务…" : failed ? "任务读取失败，请重新读取，不能据此判断没有任务。" : "当前筛选下没有任务，可清空筛选或检查项目接入。" }} /></section>;
}
function Notification({ job }: { job: ReviewJob }) {
  return <>{job.delivery_status ? <Status value={job.delivery_status} /> : "未创建"}{Boolean(job.recovery_delivery_failed_count) && <small className="table-sub">补充通知失败 {job.recovery_delivery_failed_count} 条</small>}</>;
}

function ReviewState({ job }: { job: ReviewJob }) {
  return <div className="jobs-compact-cell"><Status value={job.list_status ?? job.effective_status ?? job.status} />
    {job.active_recovery_id ? <small>补审{job.active_recovery_status === "queued" ? "排队中" : "运行中"}</small> : job.effective_conclusion && <small>补审 v{job.effective_conclusion.revision}</small>}
    {(job.effective_status ?? job.status) === "partial" && <small>覆盖不完整</small>}
    {job.issue_summary?.coverage_limited && <small>有排除或豁免</small>}
  </div>;
}


function shortCreatedAt(value: string): string {
  const date = new Date(value.includes("T") ? value : `${value.replace(" ", "T")}Z`);
  return Number.isNaN(date.getTime()) ? "时间未知" : date.toLocaleString("zh-CN", {
    year: date.getFullYear() !== new Date().getFullYear() ? "numeric" : undefined,
    month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false,
  });
}
