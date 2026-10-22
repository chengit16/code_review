/** @description 任务查询表单，未提交输入保留在本页，提交后由地址栏保存。 */

import { Search, X } from "lucide-react";
import { useState } from "react";
import type { FormEvent } from "react";

import type { Repository } from "../api/types";
import { SelectField } from "../ui/SelectField";

/** 项目、状态和时间条件集中提交，避免每次输入触发检索。 */
export function TaskFilters({ params, repositories, onApply }: {
  /** 地址栏中已生效的条件。 */ params: URLSearchParams;
  /** 可选项目。 */ repositories: Repository[];
  /** 提交完整筛选并重置页码。 */ onApply: (params: URLSearchParams) => void;
}) {
  const [status, setStatus] = useState(params.get("status") || "all");
  const [repository, setRepository] = useState(params.get("repository_id") || "all");
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next = new URLSearchParams();
    if (params.get("view")) next.set("view", params.get("view") ?? "");
    for (const [key, value] of new FormData(event.currentTarget)) {
      if (typeof value !== "string" || !value.trim() || value === "all") continue;
      // 本地时间转换为 UTC，地址栏始终保留明确的时区。
      next.set(key, key === "since" || key === "until" ? new Date(value).toISOString() : value.trim());
    }
    if (next.has("status")) next.delete("view");
    onApply(next);
  }
  const localTime = (key: string) => {
    const raw = params.get(key);
    if (!raw) return "";
    const date = new Date(raw);
    if (Number.isNaN(date.getTime())) return "";
    return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  };
  return <form className="task-filters" onSubmit={submit}>
    <SelectField name="repository_id" label="项目" value={repository} onValueChange={setRepository} options={[{ value: "all", label: "全部项目" }, ...repositories.map((r) => ({ value: String(r.id), label: r.name }))]} />
    <SelectField name="status" label="状态" value={status} onValueChange={setStatus} options={[{ value: "all", label: "全部状态" }, ...["queued", "running", "complete", "partial", "failed", "skipped", "cancelled"].map((value, index) => ({ value, label: ["排队中", "运行中", "已完成", "部分完成", "失败", "已跳过", "已取消"][index] }))]} />
    <label>MR IID<input name="mr_iid" type="number" min="1" defaultValue={params.get("mr_iid") ?? ""} placeholder="例如 27" /></label>
    <label>提交 SHA<input name="sha" defaultValue={params.get("sha") ?? ""} pattern="[0-9a-fA-F]{4,40}" placeholder="至少 4 位" /></label>
    <label>分支<input name="target_branch" defaultValue={params.get("target_branch") ?? ""} maxLength={200} placeholder="全部分支" /></label>
    <label>起始时间<input name="since" type="datetime-local" defaultValue={localTime("since")} /></label>
    <label>结束时间<input name="until" type="datetime-local" defaultValue={localTime("until")} /></label>
    <div className="filter-actions"><button className="button button-primary" type="submit"><Search size={16} />查询</button><button className="icon-button" type="button" title="清空筛选" aria-label="清空筛选" onClick={() => onApply(new URLSearchParams())}><X size={16} /></button></div>
  </form>;
}
