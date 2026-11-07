/** @description 补审确认、历史和独立通知；保持原结论可读，写请求失败保留原幂等命令。 */
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ApiError } from "../api/client";
import { createCommandId } from "../api/commandId";
import { cancelRecovery, createRecovery, getRecoveries, getRecoveryDeliveries, getRecoveryEligibility, recoveryGuidance, recoveryReason, retryRecoveryDelivery } from "../api/reviewRecovery";
import type { RecoveryCreate, RecoveryEligibility } from "../api/reviewRecovery";
import type { ReviewJobDetail } from "../api/types";
import { Modal } from "../ui/Modal";
import { QueryState } from "../ui/QueryState";
import { Status } from "../ui/Status";
import { formatCost, formatTime } from "../ui/format";
import { BudgetGateNote, RecoveryBudgetPanel } from "./RecoveryBudgetPanel";

/** 部分任务默认可补审，始终可查看历史，只读角色没有任何写入口。 */
export function ReviewRecoveryPanel({ token, job, canEdit }: {
  /** 内存管理凭据。 */ token: string;
  /** 初审事实与当前有效结论并列。 */ job: ReviewJobDetail;
  /** 显示权限不代替服务端鉴权。 */ canEdit: boolean;
}) {
  const client = useQueryClient();
  const [confirmation, setConfirmation] = useState<RecoveryEligibility | null>(null);
  const [tokens, setTokens] = useState("");
  const [timeout, setTimeout] = useState("");
  const [command, setCommand] = useState<RecoveryCreate | null>(null);
  const [commandError, setCommandError] = useState<string | null>(null);
  const eligibility = useQuery({ queryKey: ["recovery-eligibility", job.id], queryFn: ({ signal }) => getRecoveryEligibility(token, job.id, signal), refetchInterval: 5000 });
  const history = useInfiniteQuery({ queryKey: ["recoveries", job.id], initialPageParam: undefined as number | undefined, queryFn: ({ pageParam, signal }) => getRecoveries(token, job.id, pageParam, signal), getNextPageParam: (page) => page.length === 50 ? page.at(-1)?.id : undefined, refetchInterval: 5000 });
  const deliveries = useInfiniteQuery({ queryKey: ["recovery-deliveries", job.id], initialPageParam: undefined as number | undefined, queryFn: ({ pageParam, signal }) => getRecoveryDeliveries(token, job.id, pageParam, signal), getNextPageParam: (page) => page.length === 50 ? page.at(-1)?.id : undefined, refetchInterval: 5000 });
  const refresh = async () => { await Promise.all(["job", "jobs", "overview", "operations", "recoveries", "recovery-eligibility", "recovery-deliveries", "job-neighbors"].map((key) => client.invalidateQueries({ queryKey: [key] }))); };
  const create = useMutation({ mutationFn: (payload: RecoveryCreate) => createRecovery(token, job.id, payload), onSuccess: async () => { setConfirmation(null); setCommand(null); await refresh(); } });
  const cancel = useMutation({ mutationFn: (id: number) => cancelRecovery(token, id), onSuccess: refresh });
  const resend = useMutation({ mutationFn: (id: number) => retryRecoveryDelivery(token, id), onSuccess: refresh });
  const state = eligibility.data;
  const busy = create.isPending || cancel.isPending || resend.isPending;
  const blocked = !state?.eligible;
  const eligibilityMessage = eligibility.isPending ? "正在核对补审资格，请稍候" : eligibility.isError ? "补审资格查询失败，请重新加载；未确认资格前不能排队" : blocked ? `当前无法补审：${recoveryReason(state?.reason_code ?? null)}` : null;
  const eligibilityHintId = `recovery-eligibility-${job.id}`;
  const valid = confirmation && Number.isInteger(Number(tokens)) && Number(tokens) >= Math.max(1, confirmation.budget?.minimum_start_tokens ?? 0) && Number(tokens) <= confirmation.max_token_budget && Number.isInteger(Number(timeout)) && Number(timeout) > 0 && Number(timeout) <= confirmation.max_timeout_seconds;
  const error = create.error || cancel.error || resend.error;
  function begin() {
    if (!state?.eligible) return;
    setConfirmation(state);
    // 上次门槛不等于本次充足预算；禁止预填边界值让用户误以为可以完成整批。
    setTokens("");
    setTimeout(String(state.max_timeout_seconds));
    setCommand(null); setCommandError(null); create.reset();
  }
  function submit() {
    if (!confirmation || !valid) return;
    try {
      // 标识只生成一次；响应未知时保留原命令，不能换键重试造成重复收费。
      const payload = command ?? { client_key: createCommandId(), source_attempt: confirmation.source_attempt ?? 0, source_revision: confirmation.source_revision ?? 0, token_budget: Number(tokens), timeout_seconds: Number(timeout) };
      setCommandError(null); setCommand(payload); create.mutate(payload);
    } catch {
      setCommandError("无法生成安全的请求标识，请更换浏览器或通过 HTTPS 访问；未提交补审。");
    }
  }
  if (job.status !== "partial" && !history.data?.pages.flat().length && !deliveries.data?.pages.flat().length) return null;
  return <section className="section recovery-panel" aria-label="继续审核与补审历史">
    <div className="section-head"><h2>继续审核剩余部分</h2>{canEdit && job.status === "partial" && <button className="button button-primary" disabled={blocked || eligibility.isError || busy} aria-describedby={eligibilityMessage ? eligibilityHintId : undefined} title={eligibilityMessage ?? "先确认冻结范围和预算，再提交补审"} onClick={begin}>继续审核剩余部分</button>}</div>
    {eligibilityMessage && <div id={eligibilityHintId} role="status" className="coverage-note"><strong>{eligibilityMessage}</strong>{!eligibility.isPending && !eligibility.isError && blocked && <><p>{recoveryGuidance(state?.reason_code ?? null)}</p>{state?.reason_code && <p>资格原因码：<code>{state.reason_code}</code>。解除这一限制后仍会继续检查快照、范围、来源和预算，不保证立即可补审。</p>}</>}</div>}
    <QueryState loading={eligibility.isLoading || history.isLoading || deliveries.isLoading} error={eligibility.error || history.error || deliveries.error} onRetry={() => void refresh()} />
    {state?.budget && <RecoveryBudgetPanel token={token} jobId={job.id} budget={state.budget} canEdit={canEdit} />}
    <p>{state?.eligible && `剩余 ${state.remaining_count} 个文件 · 还可补审 ${state.remaining_batches} 批。`}仅审核冻结失败子集，不修改代码，不删除初审记录。</p>
    <p>初审 <Status value={job.status} /> → 当前有效结论 <Status value={job.effective_status ?? job.status} />。费用未知时不表示零费用；全量重新评审与活动补审互斥。</p>
    {error && <p role="alert" className="form-error">{error instanceof ApiError && error.code ? recoveryReason(error.code) : error.message}。请刷新核对后再操作。</p>}
    <div className="recovery-history">{history.data?.pages.flat().map((item) => <article className="attempt-evidence" key={item.id}><h3>补审 #{item.id} <Status value={item.status} /></h3><p>操作者 {item.requested_by ?? "未记录"} · 源尝试 {item.source_attempt} · 源版本 {item.source_revision} · Token 上限 {item.token_budget} · {item.timeout_seconds} 秒</p><p>本批实际 Token {item.usage?.total_tokens ?? "未知"} · 费用估算 {item.estimated_cost ? formatCost(item.estimated_cost) : "未知"}（非账单）</p><p>开始 {formatTime(item.started_at)} · 结束 {formatTime(item.finished_at)}</p><p>创建 {formatTime(item.created_at)}{item.error_code && ` · ${recoveryReason(item.error_code)}`}</p>{item.error_code && <p>批次原因码：<code>{item.error_code}</code></p>}{item.status === "stale" && ["child_not_usable", "budget_unconfirmed", "no_progress"].includes(item.error_code ?? "") && <p className="coverage-note">旧版本将本批执行失败记为已失效，历史状态原样保留；实际原因见下方说明。</p>}{item.failure_summary && <p className="coverage-note">{item.failure_summary}</p>}{item.budget_gate && <BudgetGateNote gate={item.budget_gate} />}{canEdit && ["queued", "running"].includes(item.status) && <button className="button button-secondary" disabled={busy || item.cancel_requested} onClick={() => { if (window.confirm(`停止补审 #${item.id}？已发生的模型费用不会撤销。`)) cancel.mutate(item.id); }}>{item.cancel_requested ? "正在停止" : "停止补审"}</button>}</article>)}</div>
    {history.hasNextPage && <button className="text-link" disabled={history.isFetchingNextPage} onClick={() => void history.fetchNextPage()}>加载更早补审</button>}
    <h3>独立补充通知</h3><p>不替换初审消息。网络响应丢失时外部可能重复，请核对后再重发。</p>
    {deliveries.data?.pages.flat().map((item) => <article className="attempt-evidence" key={item.id}><p>补审 #{item.recovery_id} · 版本 {item.revision} · <Status value={item.status} /> · 尝试 {item.attempts} 次</p>{item.error && <p>{item.error}</p>}{canEdit && item.status === "failed" && <button className="button button-secondary" disabled={busy} onClick={() => { if (window.confirm("仅重新发送这份补充通知？不会再次调用模型，外部消息可能重复。")) resend.mutate(item.id); }}>仅重发补充通知</button>}</article>)}
    {deliveries.hasNextPage && <button className="text-link" disabled={deliveries.isFetchingNextPage} onClick={() => void deliveries.fetchNextPage()}>加载更早补充通知</button>}
    {confirmation && <Modal className="recovery-confirm" titleId="recovery-confirm-title" onClose={() => { if (!create.isPending) setConfirmation(null); }}>
      <h2 id="recovery-confirm-title">确认补审范围与预算</h2><p>固定提交 <code>{confirmation.snapshot?.head_sha ?? job.commit_sha}</code>；源尝试 {confirmation.source_attempt}，源版本 {confirmation.source_revision}。模型与规则必须保持初审快照一致，Worker 执行前复核，漂移即拒绝。</p>
      {confirmation.snapshot && <p>模型 {confirmation.snapshot.provider} / {confirmation.snapshot.model}（版本 {confirmation.snapshot.model_version}）· OCR {confirmation.snapshot.ocr_version ?? "版本未知"} · 规则摘要 <code>{confirmation.snapshot.rule_digest}</code> · Base <code>{confirmation.snapshot.base_sha ?? "提交模式由固定 SHA 确定"}</code></p>}
      <p>失败子集 {confirmation.remaining_count} 个文件；跨文件上下文保留。预估费用未知，Token 上限不等于已确认的实际账单。</p>
      <p className="coverage-note">预算需覆盖计划和正式审核，预算不足可能没有任何文件完成。最低启动参考 {confirmation.budget?.minimum_start_tokens || "未知，请显式填写预算"} Token，不保证整批完成。请按需确认，系统不会自动增加额度。超时沿用源快照上限，可人工下调。</p>
      <details><summary>查看冻结失败文件</summary><ul>{confirmation.remaining_paths.map((path) => <li className="mono file-path" key={path}>{path}</li>)}</ul></details>
      <label>本批 Token 上限<input type="number" min={1} max={confirmation.max_token_budget} value={tokens} disabled={Boolean(command)} onChange={(event) => setTokens(event.target.value)} /></label>
      <label>本批超时秒数<input type="number" min={1} max={confirmation.max_timeout_seconds} value={timeout} disabled={Boolean(command)} onChange={(event) => setTimeout(event.target.value)} /></label>
      <p>可批准 Token 上限 {confirmation.max_token_budget}；超时上限 {confirmation.max_timeout_seconds} 秒。{command && "上次请求结果可能不确定，再提交将重用同一幂等命令；如源版本冲突，请关闭并刷新。"}</p>
      {create.error && <p role="alert" className="form-error">{create.error.message}。请求未自动重放；请核对版本后重试同一命令。</p>}
      {commandError && <p role="alert" className="form-error">{commandError}</p>}
      <div className="issue-action-buttons"><button className="button button-secondary" disabled={create.isPending} onClick={() => setConfirmation(null)}>暂不补审</button><button className="button button-primary" disabled={!valid || create.isPending} onClick={submit}>{create.isPending ? "正在排队" : command ? "重试同一补审请求" : "确认并排队"}</button></div>
    </Modal>}
  </section>;
}
