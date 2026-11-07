/** @description 补审的稳定契约及管理请求；不接受客户端文件范围，不自动重放写请求。 */
import { apiRequest } from "./client";

/** 已核对的调度门槛数字；预估不是实际账单，也不保证整批完成。 */
export interface BudgetGate {
  used_tokens: number; group_estimate_tokens: number; projected_tokens: number; budget_tokens: number;
}
/** 单任务累计批准额度，历史失败和取消也计数；不自动授权或扣减历史。 */
export interface RecoveryBudget {
  max_batches: number; used_batches: number; max_total_tokens: number; committed_tokens: number;
  minimum_start_tokens: number; authorization_version: number; previous_gate: BudgetGate | null;
}
/** 管理员显式调整，版本冲突不得自动重放；原因进入追加审计。 */
export interface BudgetAuthorization {
  expected_version: number; max_batches: number; max_total_tokens: number; reason: string;
}
/** 资格来自 SQLite，执行前 Worker 仍需复核工件、Git 和快照。 */
export interface RecoveryEligibility {
  eligible: boolean; reason_code: string | null; source_attempt: number | null;
  source_revision: number | null; remaining_count: number; remaining_paths: string[];
  max_token_budget: number; max_timeout_seconds: number; remaining_batches: number;
  active_recovery_id: number | null;
  snapshot: { head_sha: string; base_sha: string | null; provider: string; model: string; model_version: number; ocr_version: string | null; rule_digest: string } | null;
  budget?: RecoveryBudget | null;
}
/** 独立批次仅公开白名单状态，不包含令牌或私有工件路径。 */
export interface RecoveryRecord {
  requested_by: string | null;
  id: number; source_attempt: number; source_revision: number; status: string;
  token_budget: number; timeout_seconds: number; cancel_requested: boolean;
  error_code: string | null; created_at: string; started_at: string | null; finished_at: string | null;
  /** 固定中文原因与覆盖数量，不透传模型错误或原始工件。 */ failure_summary?: string | null;
  usage: { total_tokens?: number; input_tokens?: number; output_tokens?: number } | null;
  estimated_cost: { currency: "CNY" | "USD"; total: string } | null;
  budget_gate?: BudgetGate | null;
}
/** HTTP 不确定时保留幂等键和原命令，不能换键盲目重试。 */
export interface RecoveryCreate {
  client_key: string; source_attempt: number; source_revision: number;
  token_budget: number; timeout_seconds: number;
}
/** 独立补充投递，不代表初审通知被替换。 */
export interface RecoveryDelivery {
  id: number; source_attempt: number; revision: number; recovery_id: number;
  status: string; attempts: number; error: string | null; sent_at: string | null;
}

/** 只读资格，无功能开关，来源、预算或并发不满足时显示明确原因。 */
export function getRecoveryEligibility(token: string, jobId: number, signal?: AbortSignal) {
  return apiRequest<RecoveryEligibility>(token, `/api/jobs/${jobId}/recovery-eligibility`, { signal });
}
/** 按稳定 ID 分页读取批次，不把排队成功当作审核完成。 */
export function getRecoveries(token: string, jobId: number, before?: number, signal?: AbortSignal) {
  return apiRequest<RecoveryRecord[]>(token, `/api/jobs/${jobId}/recoveries?limit=50${before ? `&before_id=${before}` : ""}`, { signal });
}
/** 只提交源版本及预算，文件集合由服务端重新确认。 */
export function createRecovery(token: string, jobId: number, command: RecoveryCreate) {
  return apiRequest<RecoveryRecord>(token, `/api/jobs/${jobId}/recoveries`, { method: "POST", body: JSON.stringify(command) });
}
/** 仅追加任务额度授权；不排队、不重置历史、不调用模型。 */
export function setRecoveryBudget(token: string, jobId: number, command: BudgetAuthorization) {
  return apiRequest<{ status: string; version: number }>(token, `/api/jobs/${jobId}/recovery-budget`, { method: "PUT", body: JSON.stringify(command) });
}
/** 取消独立批次，不撤销初审或已保存的有效结论。 */
export function cancelRecovery(token: string, recoveryId: number) {
  return apiRequest(token, `/api/review-recoveries/${recoveryId}/cancel`, { method: "POST" });
}
/** 读取版本隔离的通知状态。 */
export function getRecoveryDeliveries(token: string, jobId: number, before?: number, signal?: AbortSignal) {
  return apiRequest<RecoveryDelivery[]>(token, `/api/jobs/${jobId}/recovery-deliveries?limit=50${before ? `&before_id=${before}` : ""}`, { signal });
}
/** 仅重试失败的补充通知，不重新评审。 */
export function retryRecoveryDelivery(token: string, deliveryId: number) {
  return apiRequest(token, `/api/recovery-deliveries/${deliveryId}/retry`, { method: "POST" });
}

/** 领域冲突给出可操作解释，不泄露底层异常或外部响应。 */
export function recoveryReason(code: string | null): string {
  const budgets: Record<string, string> = { budget_insufficient: "预算低于已知启动门槛，未排队或调用模型", execution_budget_insufficient: "执行前发现预算低于启动门槛，未调用模型", budget_authorization_changed: "额度版本已变化，请核对最新额度后重新确认", budget_below_committed: "额度不能低于已使用的历史批次与累计批准 Token" };
  if (code && budgets[code]) return budgets[code];
  return ({ active_recovery: "已有补审排队或执行中", nothing_remaining: "选中范围已无剩余失败文件", configuration_changed: "模型或规则快照已变化，不能沿用原快照补审", configuration_unavailable: "无法读取当前模型配置，请先核对配置", source_not_partial: "当前初审不满足补审条件", source_evidence_missing: "缺少可信初审结果或工件", source_evidence_invalid: "初审覆盖或快照证据校验未通过", recovery_limit: "补审批次数或累计预算已达上限", source_changed: "源版本已变化，请刷新并重新确认", source_expired: "源批次已超过领取期限", feedback_version_changed: "发现版本已变化，请刷新后处理", child_not_usable: "本批未形成可合并的评审结果，初审结论未改变", no_progress: "本批没有新增完成文件，初审结论未改变", budget_unconfirmed: "本批触发预算限制，结果不能确认为有效结论", budget_exceeds_source: "本批预算超过原评审快照允许的范围", source_artifact_invalid: "初审工件缺失或校验失败，未继续执行", git_input_changed: "固定提交或仓库规则校验失败，未继续执行", subset_mismatch: "补审实际范围与批准的失败子集不一致", execution_timeout: "本批执行超时，未自动重试", execution_interrupted: "Worker 中断，执行结果未确认，未自动重试", cancelled: "本批已取消，已发生的费用不会撤销" } as Record<string, string>)[code ?? ""] ?? "当前不满足补审条件，请核对初审状态和诊断";
}

/** 解释资格阻塞的下一步；仅提供配置指引，不修改服务配置或绕过后端核验。 */
export function recoveryGuidance(code: string | null): string {
  if (code === "configuration_unavailable") return "请先在模型配置中确认可用模型与凭据；补审无需配置开关或项目白名单。配置修复后刷新资格，再确认本批范围与预算。";
  if (code === "configuration_changed") return "当前模型或规则已不同于初审快照，不能放宽来源校验强行补审。请核对配置变更；若使用当前配置全量重新评审，会再次调用模型并产生费用。";
  if (code === "active_recovery") return "请查看下方活动批次，等待完成或显式停止，不要重复创建补审或全量重新评审。";
  if (["source_evidence_missing", "source_evidence_invalid", "source_expired"].includes(code ?? "")) return "请先核对原始结果、工件保留情况和来源完整性；仅重启服务不能恢复缺失证据，不要直接修改数据库绕过校验。";
  if (["recovery_limit", "budget_insufficient"].includes(code ?? "")) return "请核对下方任务额度和历史预算诊断；失败和取消也占用额度。管理员可显式调整本任务额度，再单独确认补审；保存额度不会排队，不会重置历史或绕过源快照上限。";
  return "请核对初审状态、当前资格与历史记录；不要通过重复提交或修改数据库绕过限制。";
}
