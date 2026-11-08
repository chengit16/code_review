/** @description 当前页显式重审；弹窗冻结目标，服务端逐项校验状态与权限，不扩展到其他页。 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Modal } from "antd";
import { Link } from "react-router-dom";
import { useEffect, useRef, useState } from "react";

import { apiRequest } from "../api/client";

interface Result { id: number; status: string; job_id?: number; error?: string }

/** 取消不写入；部分拒绝保留选择，入队不等于评审完成，不自动重放付费操作。 */
export function TaskSelectionBar({ token, ids, disabled, onClear, onAccepted, onPendingChange }: {
  /** 内存凭据。 */ token: string;
  /** 当前页显式勾选的终态任务。 */ ids: number[];
  /** 查询不可靠时禁止开始确认。 */ disabled: boolean;
  /** 主动清除本页选择。 */ onClear: () => void;
  /** 仅取消服务端接受项的选择。 */ onAccepted: (ids: number[]) => void;
  /** 弹窗打开及请求期间锁定父列表筛选与选择。 */ onPendingChange: (pending: boolean) => void;
}) {
  const client = useQueryClient();
  const [frozen, setFrozen] = useState<number[] | null>(null);
  const submitting = useRef(false);
  const retry = useMutation({
    retry: false,
    mutationFn: (targets: number[]) => apiRequest<Result[]>(token, "/api/jobs/batch-retry", { method: "POST", body: JSON.stringify({ ids: targets }) }),
    onSuccess: (results) => {
      // HTTP 成功不代表逐项成功；只移除明确接受项，并刷新任务与相邻导航事实。
      onAccepted(results.filter((item) => item.status === "queued").map((item) => item.id));
      for (const key of ["jobs", "overview", "job", "job-neighbors"]) void client.invalidateQueries({ queryKey: [key] });
    },
    onSettled: () => { submitting.current = false; setFrozen(null); },
  });
  const locked = frozen !== null || retry.isPending;
  useEffect(() => { onPendingChange(locked); }, [locked, onPendingChange]);
  function submit() {
    if (!frozen?.length || submitting.current) return;
    submitting.current = true;
    retry.mutate(frozen);
  }
  if (!ids.length && !retry.data && !retry.error && !locked) return null;
  return <><div className="jobs-selection" aria-label="任务批量操作" role="region">
    <span>已选 <strong>{ids.length}</strong> 个任务 <small>仅当前页终态任务</small></span>
    <Button disabled={!ids.length || disabled || locked} onClick={() => { retry.reset(); setFrozen([...ids]); }}>重审所选任务</Button>
    <Button type="text" disabled={!ids.length || locked} onClick={onClear}>清空选择</Button>
    {retry.error && <Alert type="error" showIcon title={`${retry.error.message}；所选任务已保留，请先核对是否已入队。`} />}
    {retry.data && <div aria-live="polite"><p>已入队 {retry.data.filter((item) => item.status === "queued").length} 条，未接受 {retry.data.filter((item) => item.status !== "queued").length} 条；未接受项保留勾选，核对后可重新提交。</p><ul>{retry.data.map((item) => <li key={item.id}>#{item.id}：{item.status === "queued" ? <Link to={`/jobs/${item.job_id}`}>已入队 #{item.job_id}</Link> : item.error ?? "当前状态不允许重审，请刷新核对"}</li>)}</ul></div>}
  </div><Modal title="确认重新评审" open={frozen !== null} onOk={submit} onCancel={() => { if (!submitting.current) setFrozen(null); }}
    okText="确认重审" cancelText="取消" confirmLoading={retry.isPending} okButtonProps={{ disabled: retry.isPending, "aria-label": "确认重审" }} cancelButtonProps={{ disabled: retry.isPending }}
    closable={!retry.isPending} keyboard={!retry.isPending} mask={{ closable: !retry.isPending }}>
    <p>仅重新评审当前页已冻结的 {frozen?.length ?? 0} 个任务：</p><p className="jobs-frozen-ids">{frozen?.map((id) => `#${id}`).join("、")}</p>
    <Alert type="warning" showIcon title="可能再次产生模型费用" description="将按当前配置重新排队，不会自动修改代码。取消不会提交；确认后逐项检查，结果可能部分接受。" />
  </Modal></>;
}
