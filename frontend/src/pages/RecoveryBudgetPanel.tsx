/** @description 单任务补审额度与人工授权；只保存额度审计，不创建评审或自动付费重试。 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ApiError } from "../api/client";
import { recoveryReason, setRecoveryBudget } from "../api/reviewRecovery";
import type { BudgetAuthorization, BudgetGate, RecoveryBudget } from "../api/reviewRecovery";
import { Modal } from "../ui/Modal";

/** 安全数值解释预算前瞻保护；不展示外部 warnings 正文。 */
export function BudgetGateNote({ gate }: {
  /** 已核对的整数诊断，不含原始响应。 */ gate: BudgetGate;
}) {
  return <p className="coverage-note">预算保护：已用 {gate.used_tokens} + 下一组预估 {gate.group_estimate_tokens} = {gate.projected_tokens} Token，超过本批批准 {gate.budget_tokens}。预估不是实际消耗；即使实际用量未到上限，调度也会提前停止。</p>;
}

/** 管理员按冻结版本调整额度；冲突保留草稿，刷新后必须关闭并重新核对。 */
export function RecoveryBudgetPanel({ token, jobId, budget, canEdit }: {
  /** 仅内存会话凭据。 */ token: string;
  /** 累计额度对应的任务。 */ jobId: number;
  /** 服务端累计批准事实。 */ budget: RecoveryBudget;
  /** 仅控制入口，后端仍验证管理员。 */ canEdit: boolean;
}) {
  const client = useQueryClient();
  const [draft, setDraft] = useState<BudgetAuthorization | null>(null);
  const [saved, setSaved] = useState(false);
  // 授权与付费命令分离：仅失效资格查询，不创建补审；冲突保留原版本草稿供人工核对。
  const save = useMutation({ mutationFn: (payload: BudgetAuthorization) => setRecoveryBudget(token, jobId, payload), onSuccess: async () => {
    setDraft(null); setSaved(true);
    await client.invalidateQueries({ queryKey: ["recovery-eligibility", jobId] });
  } });
  const valid = draft && Number.isInteger(draft.max_batches) && draft.max_batches >= Math.max(1, budget.used_batches) && draft.max_batches <= 100 && Number.isInteger(draft.max_total_tokens) && draft.max_total_tokens >= Math.max(1, budget.committed_tokens) && draft.max_total_tokens <= 100_000_000 && draft.reason.trim().length > 0 && draft.reason.length <= 500;
  return <div className="coverage-note">
    <h3>本任务补审额度</h3>
    <p>已用 {budget.used_batches}/{budget.max_batches} 批；累计批准 {budget.committed_tokens}/{budget.max_total_tokens} Token（不是实际账单）。失败和取消不退还批准额度。</p>
    <p>最低启动参考 {budget.minimum_start_tokens || "未知"} Token；不保证剩余全部文件完成。来源快照仍可能有更低的单批上限。</p>
    {budget.previous_gate && <BudgetGateNote gate={budget.previous_gate} />}
    {canEdit && <button className="button button-secondary" onClick={() => { setDraft({ expected_version: budget.authorization_version, max_batches: budget.max_batches, max_total_tokens: budget.max_total_tokens, reason: "" }); setSaved(false); save.reset(); }}>调整本任务补审额度</button>}
    {saved && <p role="status">额度已保存，未排队或调用模型；请重新核对资格，再单独确认补审。</p>}
    {draft && <Modal className="recovery-budget-modal" titleId="recovery-budget-title" onClose={() => { if (!save.isPending) setDraft(null); }}>
      <div className="modal-heading"><h2 id="recovery-budget-title">确认调整任务额度</h2></div>
      <div className="recovery-budget-body">
      <p>仅修改任务 #{jobId} 的累计上限，版本 {draft.expected_version}。不改变历史，不自动补审。请自行决定费用边界，系统不会自动提高额度。</p>
      <div className="recovery-budget-fields">
      <label>累计补审批次上限<input type="number" min={Math.max(1, budget.used_batches)} max={100} value={draft.max_batches || ""} onChange={(event) => setDraft({ ...draft, max_batches: Number(event.target.value) })} disabled={save.isPending} /></label>
      <label>累计批准 Token 上限<input type="number" min={Math.max(1, budget.committed_tokens)} max={100_000_000} value={draft.max_total_tokens || ""} onChange={(event) => setDraft({ ...draft, max_total_tokens: Number(event.target.value) })} disabled={save.isPending} /></label>
      <label className="recovery-budget-reason">调整原因<textarea rows={4} maxLength={500} value={draft.reason} onChange={(event) => setDraft({ ...draft, reason: event.target.value })} disabled={save.isPending} /></label>
      </div>
      {save.error && <p className="form-error" role="alert">{save.error instanceof ApiError && save.error.code ? recoveryReason(save.error.code) : save.error.message}。草稿已保留；请刷新资格并关闭此框后重新核对，不会自动重放。</p>}
      </div>
      <div className="issue-action-buttons"><button className="button button-secondary" disabled={save.isPending} onClick={() => setDraft(null)}>取消调整</button><button className="button button-primary" disabled={!valid || save.isPending || (save.error instanceof ApiError && save.error.status === 409)} onClick={() => { if (valid) save.mutate(draft); }}>确认保存额度（不排队）</button></div>
    </Modal>}
  </div>;
}
