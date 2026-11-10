/** @description Ant Design 任务查询表单；未提交输入留在本页，提交后才更新 URL，不接管任务状态。 */
import { Button, Collapse, Input, Select } from "antd";
import { Search, X } from "lucide-react";
import { useId, useState } from "react";
import type { FormEvent } from "react";

import type { Repository } from "../api/types";

/** 集中提交条件，显式传递禁用状态以保护 Portal 选择器和批量冻结范围。 */
export function TaskFilters({ params, repositories, disabled = false, repositoriesKnown = true, onApply }: {
  /** 地址栏中已生效的条件。 */ params: URLSearchParams;
  /** 可选项目；读取失败时不冒充完整列表。 */ repositories: Repository[];
  /** 确认或写入期间锁定所有筛选。 */ disabled?: boolean;
  /** 辅助查询已成功，失败时仍允许按其他条件查询。 */ repositoriesKnown?: boolean;
  /** 提交完整筛选并重置页码。 */ onApply: (params: URLSearchParams) => void;
}) {
  const id = useId();
  const [repository, setRepository] = useState(params.get("repository_id") || "all");
  const [feedbackState, setFeedbackState] = useState(params.get("feedback_state") || "all");
  const [notificationFailed, setNotificationFailed] = useState(params.get("notification_failed") === "true" || params.get("view") === "notification_failed");
  const advanced = ["mr_iid", "sha", "target_branch", "since", "until", "notification_failed"];
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (disabled) return;
    const next = new URLSearchParams();
    if (params.has("page_size")) next.set("page_size", params.get("page_size") ?? "25");
    if (params.get("view")) next.set("view", params.get("view") ?? "");
    if (params.get("status")) next.set("status", params.get("status") ?? "");
    // Select 不参与原生 FormData，显式合并才能保留已选项目和状态。
    if (repository !== "all") next.set("repository_id", repository);
    if (feedbackState !== "all") next.set("feedback_state", feedbackState);
    if (params.has("issue_state")) next.set("issue_state", params.get("issue_state") ?? "");
    if (notificationFailed) next.set("notification_failed", "true");
    if (params.get("view") === "notification_failed") next.delete("view");
    for (const [key, value] of new FormData(event.currentTarget)) {
      if (typeof value !== "string" || !value.trim()) continue;
      next.set(key, key === "since" || key === "until" ? new Date(value).toISOString() : value.trim());
    }
    onApply(next);
  }
  const localTime = (key: string) => {
    const raw = params.get(key);
    if (!raw) return "";
    const date = new Date(raw);
    if (Number.isNaN(date.getTime())) return "";
    return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  };
  const names: Record<string, string> = { repository_id: "项目", issue_state: "历史处置", feedback_state: "发现反馈", notification_failed: "通知失败", status: "状态", mr_iid: "MR", sha: "提交", target_branch: "分支", since: "起始", until: "结束", view: "快捷视图" };
  const stateNames: Record<string, string> = { queued: "排队中", running: "运行中", complete: "已完成", partial: "部分完成", failed: "失败", skipped: "已跳过", cancelled: "已取消", active: "排队与运行", attention: "待关注", notification_failed: "飞书失败" };
  return <><form className="jobs-filter-form" onSubmit={submit}>
    <div className="jobs-filter-main">
      <div className="jobs-filter-field"><label htmlFor={`${id}-repo`}>项目</label><Select virtual={false} id={`${id}-repo`} value={repository} onChange={setRepository} disabled={disabled || !repositoriesKnown} options={[{ value: "all", label: "全部项目" }, ...repositories.map((r) => ({ value: String(r.id), label: r.name })), ...(!repositories.some((r) => String(r.id) === repository) && repository !== "all" ? [{ value: repository, label: `项目 #${repository}` }] : [])]} /></div>
      <div className="jobs-filter-field"><label htmlFor={`${id}-issue-state`}>发现反馈</label><Select virtual={false} id={`${id}-issue-state`} value={feedbackState} onChange={setFeedbackState} disabled={disabled} options={[{ value: "all", label: "全部发现反馈" }, { value: "pending", label: "有待反馈发现" }, { value: "handled", label: "发现全部已处理" }]} /></div>
      <div className="jobs-filter-actions"><Button type="primary" htmlType="submit" icon={<Search size={16} />} disabled={disabled}>查询</Button><Button aria-label="清空筛选" title="清空筛选" icon={<X size={16} />} disabled={disabled} onClick={() => { const next = new URLSearchParams(); if (params.has("page_size")) next.set("page_size", params.get("page_size") ?? "25"); onApply(next); }} /></div>
    </div>
    <Collapse ghost defaultActiveKey={advanced.some((key) => params.has(key)) ? ["advanced"] : []} items={[{ key: "advanced", forceRender: true, label: "更多筛选（提交、分支、时间）", children: <div className="jobs-filter-advanced">
      <label className="jobs-filter-field">MR IID<Input name="mr_iid" type="number" min="1" defaultValue={params.get("mr_iid") ?? ""} placeholder="例如 27" disabled={disabled} /></label>
      <label className="jobs-filter-field">飞书通知<Select aria-label="飞书通知筛选" virtual={false} value={notificationFailed ? "failed" : "all"} onChange={(value) => setNotificationFailed(value === "failed")} disabled={disabled} options={[{ value: "all", label: "全部通知" }, { value: "failed", label: "发送失败（含补充通知）" }]} /></label>
      <label className="jobs-filter-field">提交 SHA<Input name="sha" defaultValue={params.get("sha") ?? ""} pattern="[0-9a-fA-F]{4,40}" placeholder="至少 4 位" disabled={disabled} /></label>
      <label className="jobs-filter-field">分支<Input name="target_branch" defaultValue={params.get("target_branch") ?? ""} maxLength={200} placeholder="全部分支" disabled={disabled} /></label>
      <label className="jobs-filter-field">起始时间<Input name="since" type="datetime-local" defaultValue={localTime("since")} disabled={disabled} /></label>
      <label className="jobs-filter-field">结束时间<Input name="until" type="datetime-local" defaultValue={localTime("until")} disabled={disabled} /></label>
    </div> }]} />
  </form><div className="jobs-active-filters" aria-label="已生效筛选">{Array.from(params).filter(([key]) => key in names).map(([key, value]) => <Button key={key} size="small" aria-label={`移除${names[key]}筛选`} disabled={disabled} onClick={() => { const next = new URLSearchParams(params); next.delete(key); next.delete("page"); onApply(next); }}>{names[key]}：{key === "repository_id" ? repositories.find((item) => String(item.id) === value)?.name ?? value : key === "issue_state" ? ({ open: "有待处理问题", resolved: "全部已处置", none: "未发现问题", unknown: "状态待核实" } as Record<string, string>)[value] ?? value : key === "feedback_state" ? ({ pending: "有待反馈发现", handled: "发现全部已处理" } as Record<string, string>)[value] ?? value : stateNames[value] ?? value} ×</Button>)}</div></>;
}
