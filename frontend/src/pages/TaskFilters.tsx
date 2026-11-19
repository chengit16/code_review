/** @description Ant Design 任务查询表单；未提交输入留在本页，提交后才更新 URL，不接管任务状态。 */
import { Button, DatePicker, Select } from "antd";
import dayjs from "dayjs";
import { Search, X } from "lucide-react";
import { useState } from "react";
import type { FormEvent } from "react";

import type { Repository } from "../api/types";
import { localDateInput, utcDateInput } from "../ui/listDates";

/** 集中提交条件，显式传递禁用状态以保护 Portal 选择器和批量冻结范围。 */
export function TaskFilters({ params, repositories, disabled = false, repositoriesKnown = true, onApply }: {
  /** 地址栏中已生效的条件。 */ params: URLSearchParams;
  /** 可选项目；读取失败时不冒充完整列表。 */ repositories: Repository[];
  /** 确认或写入期间锁定所有筛选。 */ disabled?: boolean;
  /** 辅助查询已成功，失败时仍允许按其他条件查询。 */ repositoriesKnown?: boolean;
  /** 提交完整筛选并重置页码。 */ onApply: (params: URLSearchParams) => void;
}) {
  const [source, setSource] = useState(params.get("source") || "all");
  const [repository, setRepository] = useState(params.get("repository_id") || "all");
  const [feedbackState, setFeedbackState] = useState(params.get("feedback_state") || "all");
  const start = localDateInput(params.get("since")), end = localDateInput(params.get("until"));
  const sameDay = Boolean(start && end && start === end);
  const [date, setDate] = useState(sameDay ? start : "");
  const [dateChanged, setDateChanged] = useState(false);
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (disabled) return;
    // 旧链接的 MR、SHA、分支及通知条件继续生效并显示为可移除标签，不因精简控件丢失范围。
    const next = new URLSearchParams(params);
    for (const key of ["page", "source", "repository_id", "feedback_state"]) next.delete(key);
    if (source !== "all") next.set("source", source);
    if (repository !== "all") next.set("repository_id", repository);
    if (feedbackState !== "all") next.set("feedback_state", feedbackState);
    // 单日期查询包含本地整天；未操作日期时保留旧范围，避免刷新旧链接改变查询语义。
    if (dateChanged) {
      next.delete("since"); next.delete("until");
      if (date) {
        next.set("since", utcDateInput(date, "start"));
        next.set("until", utcDateInput(date, "end"));
      }
    }
    onApply(next);
  }
  const names: Record<string, string> = { source: "来源", repository_id: "项目", issue_state: "历史处置", feedback_state: "发现反馈", notification_failed: "通知失败", status: "状态", mr_iid: "MR", sha: "提交", target_branch: "分支", since: "创建日期从", until: "创建日期至", view: "快捷视图" };
  const stateNames: Record<string, string> = { queued: "排队中", running: "运行中", complete: "已完成", partial: "部分完成", failed: "失败", skipped: "已跳过", cancelled: "已取消", active: "排队与运行", attention: "待关注", notification_failed: "飞书失败" };
  const conditions = Array.from(params).filter(([key]) => key in names && !(sameDay && key === "until"));
  return <><form className="jobs-filter-form" onSubmit={submit}>
    <div className="jobs-filter-main">
      <Select aria-label="评审来源" value={source} onChange={setSource} disabled={disabled} options={[{ value: "all", label: "全部来源" }, { value: "premerge", label: "合并前 MR" }, { value: "mr", label: "合并后 MR" }, { value: "push", label: "目标分支 Push" }]} />
      <Select aria-label="项目" virtual={false} value={repository} onChange={setRepository} disabled={disabled || !repositoriesKnown} options={[{ value: "all", label: "全部项目" }, ...repositories.map((r) => ({ value: String(r.id), label: r.name })), ...(!repositories.some((r) => String(r.id) === repository) && repository !== "all" ? [{ value: repository, label: `项目 #${repository}` }] : [])]} />
      <Select aria-label="发现反馈" virtual={false} value={feedbackState} onChange={setFeedbackState} disabled={disabled} options={[{ value: "all", label: "全部发现反馈" }, { value: "pending", label: "有待反馈发现" }, { value: "handled", label: "发现全部已处理" }]} />
      <DatePicker className="jobs-created-date" aria-label="创建日期" value={date ? dayjs(date) : null} placeholder="创建日期" format="YYYY-MM-DD" disabled={disabled} onChange={(value) => { setDate(value?.format("YYYY-MM-DD") ?? ""); setDateChanged(true); }} onBlur={(event) => { if (date && !(event.target as HTMLInputElement).value.trim()) { setDate(""); setDateChanged(true); } }} />
      <div className="jobs-filter-actions"><Button type="primary" htmlType="submit" icon={<Search size={16} />} disabled={disabled}>查询</Button><Button aria-label="清空筛选" title="清空筛选" icon={<X size={16} />} disabled={disabled} onClick={() => { const next = new URLSearchParams(); if (params.has("page_size")) next.set("page_size", params.get("page_size") ?? "25"); onApply(next); }} /></div>
    </div>
  </form>{conditions.length > 0 && <div className="jobs-active-filters" aria-label="已生效筛选">{conditions.map(([key, value]) => <Button key={key} size="small" aria-label={`移除${sameDay && key === "since" ? "创建日期" : names[key]}筛选`} disabled={disabled} onClick={() => { const next = new URLSearchParams(params); next.delete(key); if (sameDay && key === "since") next.delete("until"); next.delete("page"); onApply(next); }}>{sameDay && key === "since" ? "创建日期" : names[key]}：{key === "repository_id" ? repositories.find((item) => String(item.id) === value)?.name ?? value : key === "issue_state" ? ({ open: "有待处理问题", resolved: "全部已处置", none: "未发现问题", unknown: "状态待核实" } as Record<string, string>)[value] ?? value : key === "feedback_state" ? ({ pending: "有待反馈发现", handled: "发现全部已处理" } as Record<string, string>)[value] ?? value : key === "since" || key === "until" ? localDateInput(value) : stateNames[value] ?? value} ×</Button>)}</div>}</>;
}
