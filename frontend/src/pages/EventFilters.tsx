/** @description 事件检索与范围补审；筛选参数保存在地址栏，补审由 Worker 处理。 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Search, Send } from "lucide-react";
import { useState } from "react";
import type { FormEvent } from "react";

import { apiRequest } from "../api/client";
import type { Repository } from "../api/types";
import { SelectField } from "../ui/SelectField";

/** 查询和补审使用同一项目选择，补审时间限定在 31 天。 */
export function EventFilters({ token, params, onApply, repositories }: {
  /** 内存口令。 */ token: string;
  /** 已生效的地址栏筛选。 */ params: URLSearchParams;
  /** 更改地址栏筛选。 */ onApply: (params: URLSearchParams) => void;
  /** 可选择的项目。 */ repositories: Repository[];
}) {
  const [repository, setRepository] = useState(params.get("repository_id") ?? "all");
  const [status, setStatus] = useState(params.get("status") ?? "all");
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");
  const client = useQueryClient();
  const backfills = useQuery({ queryKey: ["mr-backfills"], queryFn: () => apiRequest<Array<{ id: number; status: string; scanned: number; enqueued: number; error: string | null }>>(token, "/api/mr-backfills"), refetchInterval: 10000 });
  const backfill = useMutation({ mutationFn: () => apiRequest(token, `/api/repositories/${repository}/mrs/backfill`, { method: "POST", body: JSON.stringify({ since: new Date(since).toISOString(), until: new Date(until).toISOString() }) }), onSuccess: () => void client.invalidateQueries({ queryKey: ["mr-backfills"] }) });
  function apply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next = new URLSearchParams();
    if (repository !== "all") next.set("repository_id", repository);
    if (status !== "all") next.set("status", status);
    const fields = new FormData(event.currentTarget);
    for (const name of ["mr_iid", "since", "until"]) {
      const value = fields.get(name);
      if (typeof value === "string" && value) next.set(name, name === "mr_iid" ? value : new Date(value).toISOString());
    }
    onApply(next);
  }
  return <><form className="task-filters" onSubmit={apply}><SelectField label="项目" value={repository} onValueChange={setRepository} options={[{ value: "all", label: "全部项目" }, ...repositories.map((item) => ({ value: String(item.id), label: item.name }))]} /><SelectField label="状态" value={status} onValueChange={setStatus} options={["all", "queued", "running", "done", "needs_attention"].map((value) => ({ value, label: ({ all: "全部状态", queued: "排队中", running: "运行中", done: "已处理", needs_attention: "需要处理" } as Record<string, string>)[value] }))} /><label>MR IID<input name="mr_iid" type="number" min="1" defaultValue={params.get("mr_iid") ?? ""} /></label><label>起始时间<input name="since" type="datetime-local" /></label><label>结束时间<input name="until" type="datetime-local" /></label><button className="button button-secondary"><Search size={16} />查询</button></form><details className="section"><summary>按合并时间补审</summary><div className="filter-bar"><label>开始<input type="datetime-local" value={since} onChange={(event) => setSince(event.target.value)} /></label><label>结束<input type="datetime-local" value={until} onChange={(event) => setUntil(event.target.value)} /></label><button className="button button-secondary" disabled={repository === "all" || !since || !until || backfill.isPending} onClick={() => backfill.mutate()}><Send size={16} />提交补审</button></div>{backfill.error && <p role="alert" className="form-error">{backfill.error.message}</p>}{backfills.data?.slice(0, 5).map((item) => <p key={item.id}>申请 #{item.id} · {item.status} · 扫描 {item.scanned} · 入队 {item.enqueued}{item.error ? ` · ${item.error}` : ""}</p>)}</details></>;
}
