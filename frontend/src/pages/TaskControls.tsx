/** @description 任务停止和批量重审命令；停止确认与评审结论由服务端决定。 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { RotateCcw, Square } from "lucide-react";
import { useState } from "react";

import { apiRequest } from "../api/client";

/** 排队取消立即生效，运行任务等待 Worker 确认。 */
export function TaskStop({ token, id, status, stopping }: {
  /** 内存中的口令。 */ token: string;
  /** 任务标识。 */ id: number;
  /** 服务端状态。 */ status: string;
  /** 停止请求是否已持久化。 */ stopping: boolean;
}) {
  const client = useQueryClient();
  const mutation = useMutation({
    mutationFn: () => apiRequest(token, `/api/jobs/${id}/cancel`, { method: "POST" }),
    onSuccess: () => { void client.invalidateQueries({ queryKey: ["job"] }); void client.invalidateQueries({ queryKey: ["jobs"] }); },
  });
  if (!["queued", "running"].includes(status)) return null;
  return <div className="detail-line"><button className="button button-secondary" disabled={stopping || mutation.isPending} onClick={() => { if (window.confirm(`停止任务 #${id}？已发生的模型调用可能仍产生费用。`)) mutation.mutate(); }}><Square size={16} />{stopping ? "正在停止" : status === "queued" ? "取消任务" : "停止评审"}</button>{mutation.error && <p role="alert">{mutation.error.message}</p>}</div>;
}

/** 批量操作逐项回显，部分冲突不会被成功提示掩盖。 */
export function BatchTaskRetry({ token }: { /** 内存中的口令。 */ token: string }) {
  const [input, setInput] = useState("");
  const client = useQueryClient();
  const mutation = useMutation({
    mutationFn: (ids: number[]) => apiRequest<{ id: number; status: string; job_id?: number; error?: string }[]>(token, "/api/jobs/batch-retry", { method: "POST", body: JSON.stringify({ ids }) }),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["jobs"] }),
  });
  return <details className="section"><summary>批量重新评审</summary><form className="filter-bar" onSubmit={(event) => { event.preventDefault(); mutation.mutate(input.split(/[\s,，]+/).filter(Boolean).map(Number)); }}><label>任务 ID<input value={input} onChange={(event) => setInput(event.target.value)} placeholder="1, 2, 3" required /></label><button className="button button-secondary" disabled={mutation.isPending}><RotateCcw size={16} />批量重审</button></form>{mutation.error && <p role="alert" className="form-error">{mutation.error.message}</p>}{mutation.data && <ul aria-live="polite">{mutation.data.map((item) => <li key={item.id}>#{item.id}：{item.status === "queued" ? `已排队 #${item.job_id}` : item.error ?? "任务当前无法重审"}</li>)}</ul>}</details>;
}
