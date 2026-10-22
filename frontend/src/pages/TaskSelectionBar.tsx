/** @description 按本页显式任务编号重审；服务端逐项检查状态与权限，不扩展到其他页。 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { apiRequest } from "../api/client";

interface Result { id: number; status: string; job_id?: number; error?: string }

/** 确认模型费用影响后提交；失败或部分拒绝逐条保留，不把入队当作评审完成。 */
export function TaskSelectionBar({ token, ids, disabled, onClear }: {
  /** 内存凭据。 */ token: string;
  /** 当前页显式勾选的终态任务。 */ ids: number[];
  /** 页面加载或筛选状态不可靠时禁止提交。 */ disabled: boolean;
  /** 成功接受后清除本页选择。 */ onClear: () => void;
}) {
  const client = useQueryClient();
  const retry = useMutation({
    mutationFn: (targets: number[]) => apiRequest<Result[]>(token, "/api/jobs/batch-retry", { method: "POST", body: JSON.stringify({ ids: targets }) }),
    onSuccess: () => {
      onClear();
      for (const key of ["jobs", "overview", "job", "job-neighbors"]) void client.invalidateQueries({ queryKey: [key] });
    },
  });
  function submit() {
    if (disabled || retry.isPending || !ids.length) return;
    if (window.confirm(`确认重新评审当前页勾选的 ${ids.length} 个任务？\n将按当前配置重新排队，可能再次产生模型费用；不会自动修改代码。`)) retry.mutate([...ids]);
  }
  return <div className="task-selection-bar" aria-label="任务批量操作" role="region">
    <span>已选 <strong>{ids.length}</strong> 个任务 <small>仅当前页终态任务</small></span>
    <button className="button button-secondary" disabled={!ids.length || disabled || retry.isPending} onClick={submit}>重审所选任务</button>
    <button className="text-link" disabled={!ids.length || retry.isPending} onClick={onClear}>清空选择</button>
    {retry.error && <p role="alert" className="form-error">{retry.error.message}；所选任务已保留。</p>}
    {retry.data && <ul aria-live="polite">{retry.data.map((item) => <li key={item.id}>#{item.id}：{item.status === "queued" ? <Link to={`/jobs/${item.job_id}`}>已入队 #{item.job_id}</Link> : item.error ?? "当前状态不允许重审，请刷新核对"}</li>)}</ul>}
  </div>;
}
