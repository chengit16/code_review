/** @description 管理 API 的稳定前端投影；密文字段不进入浏览器类型。 */
import type { ConclusionDocument, ConclusionOverview, ConclusionVersion } from "./reviewConclusions";
import type { FailureAnalysis } from "./reviewDiagnostics";
import type { CumulativeUsage, ReviewTiming, ScopeAnalysis } from "./reviewExecution";

/** 仓库接入信息与 GitLab 回调地址。 */
export interface Repository {
  id: number;
  name: string;
  gitlab_url: string;
  project_id: number;
  remote_url: string;
  path_with_namespace: string;
  target_branch: string;
  auth_kind: "signing" | "secret";
  enabled: number;
  webhook_id: string | null;
  last_webhook_at: string | null;
  has_feishu_webhook: boolean;
  has_gitlab_token: boolean;
  enable_merge_requests: number;
  enable_default_branch_pushes: number;
  feishu_target_id: number | null;
  webhook_url: string;
  created_at: string;
}

/** API 存活状态与独立 Worker 的文件锁状态。 */
export interface Health {
  status: "ok";
  auth_mode: "dev" | "admin" | "users";
  worker: "running" | "stopped";
}

/** 首页以最新事件和合并前版本统计的运维待办。 */
export interface OverviewSummary {
  events_attention: number;
  premerge_failed: number;
  premerge_partial: number;
}

/** 新仓库表单；Secret token 省略时由服务端生成。 */
export interface RepositoryInput {
  name: string;
  gitlab_url: string;
  project_id: number;
  remote_url: string;
  path_with_namespace: string;
  target_branch: string;
  auth_kind?: "secret";
  webhook_token?: string;
  gitlab_token: string;
  feishu_target_id?: number | null;
  enable_merge_requests: boolean;
  enable_default_branch_pushes: boolean;
}

/** 管理员主动查看单个项目令牌时的响应，不进入仓库列表缓存。 */
export interface WebhookTokenResponse {
  webhook_token: string;
}

/** 仓库可变设置；项目身份有业务历史后冻结，来源修改须等待队列完成。 */
export interface RepositoryUpdateInput {
  name?: string;
  gitlab_url?: string;
  project_id?: number;
  remote_url?: string;
  path_with_namespace?: string;
  target_branch?: string;
  enabled?: boolean;
  auth_kind?: "signing" | "secret";
  webhook_token?: string;
  gitlab_token?: string;
  feishu_target_id?: number | null;
  webhook_id?: string | null;
  enable_merge_requests?: boolean;
  enable_default_branch_pushes?: boolean;
}

/** OCR 原生 rule.json 格式；条目顺序决定同一层内的首次命中。 */
export interface ReviewRuleDocument {
  include: string[];
  exclude: string[];
  rules: { path: string; rule: string; merge_system_rule: boolean }[];
}

export interface ReviewRuleConfiguration {
  repository_id: number | null;
  content: ReviewRuleDocument;
  updated_at: string;
}

/** 规则历史保留删除状态；恢复任一版本会生成新的历史记录。 */
export interface ReviewRuleRevision {
  id: number;
  repository_id: number | null;
  content: ReviewRuleDocument | null;
  action: "saved" | "deleted" | "restored";
  restored_from: number | null;
  created_at: string;
}

/** Worker 在目标分支提交上运行的规则命中预览。 */
export interface RulePreview {
  id: number;
  repository_id: number;
  file_path: string;
  status: "queued" | "running" | "passed" | "failed";
  commit_sha: string | null;
  output: string | null;
  error: string | null;
  created_at: string;
  finished_at: string | null;
}

/** 可供多个仓库引用的飞书通知通道；凭据从不进入列表响应。 */
export interface NotificationTarget {
  id: number;
  name: string;
  repository_count: number;
  has_signing_secret: boolean;
  created_at: string;
  updated_at: string;
}

export interface NotificationTargetInput {
  name: string;
  webhook_url?: string;
  signing_secret?: string;
}

/** OCR 模型配置列表；始终不包含 API Key。 */
export interface ModelConfiguration {
  id: number;
  name: string;
  provider: string;
  model: string;
  base_url: string;
  enabled: number;
  has_api_key: boolean;
  price_currency: "CNY" | "USD";
  input_price_per_million: string | null;
  output_price_per_million: string | null;
  version: number;
}

/** GitLab 合并事件收件箱记录。 */
export interface MergeEvent {
  id: number;
  repository_id: number;
  mr_iid: number;
  delivery_id: string | null;
  correlation_id?: string;
  merge_sha: string | null;
  squash_sha: string | null;
  status: string;
  repository_name?: string;
  error: string | null;
  attempts: number;
  next_run_at: string;
  created_at: string;
  job_count?: number;
  latest_job_id?: number | null;
}

/** Webhook 投递元数据；项目和分支在鉴权前只是请求自称值。 */
export interface WebhookDiagnostic {
  id: number;
  repository_id: number | null;
  claimed_project_id: number | null;
  claimed_branch: string | null;
  event_kind: "merge_request" | "push" | "other";
  outcome: "queued" | "duplicate" | "ignored" | "rejected";
  reason: string;
  http_status: number;
  created_at: string;
}

/** 单提交或 Push 范围评审任务列表数据。 */
export interface ReviewJob {
  /** 初审/候选并列，不把候选状态写成旧任务执行状态。 */
  conclusions?: ConclusionOverview | null;
  /** 有效结论与初审执行状态独立；旧后端缺失时回退初审。 */ effective_status?: string;
  /** 当前已验证有效版本。 */ effective_conclusion?: ConclusionVersion | null;
  /** 完整有效发现仅在详情返回。 */ effective_document?: ConclusionDocument | null;
  /** 全任务费用包含的实际开始补审次数。 */ recovery_execution_count?: number;
  /** 活动补审期间禁止全量重审。 */ active_recovery_id?: number | null;
  /** 当前源尝试的失败补充通知数量。 */ recovery_delivery_failed_count?: number;
  /** 初审尝试累计费用，便于与全任务累计复核。 */ initial_cumulative_usage?: CumulativeUsage;
  /** 已持久化摘要；历史未保存时不回填。 */ failure_summary?: string | null;
  /** 详情提供，列表省略请求和分组明细。 */ failure_analysis?: FailureAnalysis | null;
  /** 独立历史诊断导入时间，不代表重跑模型。 */ failure_analysis_imported_at?: string | null;
  /** 旧记录可缺失，不能由前端猜测累计时间。 */ timing?: ReviewTiming;
  /** 稳定原因码与安全中文文案，不含原始模型响应。 */ reason?: { code: string; message: string };
  /** 仅分析不排除时必须如实说明。 */ scope_analysis?: ScopeAnalysis | null;
  /** 各次历史单价和已知用量的累计，未知部分不作为零。 */ cumulative_usage?: CumulativeUsage;
  /** 当前尝试已持久化的发现数量；不代表完整覆盖。 */ finding_count?: number;
  /** 当前尝试发现的最高严重级别。 */ highest_severity?: string | null;
  /** 活动补审优先的列表状态，筛选和分面数量使用同一口径。 */ list_status?: string | null;
  /** 当前补审排队或执行状态，不改变初审事实。 */ active_recovery_status?: "queued" | "running" | null;
  /** 当前有效发现关联问题的去重处理摘要；缺失表示旧服务端或无法核实。 */ issue_summary?: {
    open_count: number; fixed_count: number; ignored_count: number; false_positive_count?: number; unknown_count: number;
    finding_count: number | null; highest_severity: string | null; complete: boolean; no_findings: boolean;
    available: boolean; coverage_complete: boolean; coverage_limited: boolean;
  };
  /** 飞书发送状态，与评审状态相互独立。 */ delivery_status?: string | null;
  /** 当前有效发现的价值反馈条数；缺失不回退问题处置，历史修复归未评价。 */ feedback_summary?: {
    available: boolean; total: number | null; helpful: number; false_positive: number;
    ignored: number; unmarked: number;
  };
  id: number;
  repository_id: number;
  event_id: number;
  correlation_id?: string;
  mr_iid: number;
  commit_sha: string;
  /** 固定提交的 Git 作者姓名；旧任务或尚未读取 Git 时可能缺失，不代表问题处理人。 */
  commit_author?: string | null;
  base_sha?: string | null;
  ordinal: number;
  status: string;
  error: string | null;
  attempts: number;
  created_at: string;
  finished_at: string | null;
  target_branch?: string;
  repository_name?: string;
  failure_stage?: string | null;
  started_at?: string | null;
  usage?: { input_tokens?: number; output_tokens?: number; total_tokens?: number } | null;
  estimated_cost?: {
    currency: "CNY" | "USD";
    input: string;
    output: string;
    total: string;
  } | null;
}

/** 服务端筛选后的任务总量与单页结果，不受旧版最近 200 条限制。 */
export interface TaskPage {
  items: ReviewJob[];
  total: number;
  page: number;
  page_size: number;
  /** 忽略分页和状态导航自身条件，保留其余筛选的全量分面计数。 */ status_counts?: Record<string, number>;
  /** 忽略反馈条件自身和分页，保留评审状态等条件的任务数，不是发现条数。 */ feedback_counts?: Record<string, number>;
}

/** OCR 发现；行号为 0 时代表文件级问题。 */
export interface ReviewComment {
  path: string;
  content: string;
  start_line?: number;
  end_line?: number;
  severity?: string;
  category?: string;
}

/** OCR 覆盖 manifest；页面只使用安全投影字段。 */
export interface ReviewManifest {
  terminal_state: string;
  coverage: {
    selected: unknown[];
    completed: unknown[];
    reused: unknown[];
    failed: unknown[];
    waived: unknown[];
  };
}

/** OCR 范围预览；排除原因用于解释跳过结论。 */
export interface ReviewPreview {
  total_files: number;
  reviewable_count: number;
  excluded_count: number;
  files: Array<{
    path: string;
    will_review: boolean;
    exclude_reason?: string;
  }>;
}

/** 评审详情包含 OCR 的机器可读发现与覆盖情况。 */
export interface ReviewJobDetail extends ReviewJob {
  /** 当前有效发现解析到最终合并目标，缺失项保持未知，不由反馈推断。 */ resolved_finding_issues?: Record<string, { id: number; status: "open" | "fixed" | "ignored" | "false_positive" }>;
  /** 稳定主身份的当前人工反馈。 */ finding_feedback?: Record<string, "helpful" | "false_positive" | "ignored" | "fixed">;
  /** 稳定主身份的问题关联，不与初审下标混用。 */ finding_issues?: Record<string, { id: number; status: "open" | "fixed" | "ignored" | "false_positive" | "merged" }>;
  /** 与飞书通知相互独立的 MR 行内发布记录。 */
  publications?: Array<{ id: number; comment_index: number; attempt_number: number; status: string; attempts: number; error: string | null; discussion_id: string | null }>;
  /** Worker 确认停止前保持 running 状态。 */
  cancel_requested?: number;
  mr_url?: string;
  commit_url?: string;
  result: {
    comments?: ReviewComment[];
    manifest?: ReviewManifest;
    preview?: ReviewPreview;
    /** 策略排除独立于 OCR 选中覆盖，不代表模型已审查这些文件。 */
    input_filter?: { excluded_count: number } | null;
    usage?: { input_tokens?: number; output_tokens?: number; total_tokens?: number };
    estimated_cost?: { currency: "CNY" | "USD"; input: string; output: string; total: string } | null;
    summary?: { budget_exceeded?: boolean };
    message?: string;
    /** 错误是否可重试与是否实际安排重试分别记录，达到上限时不再排队。 */
    diagnostic?: {
      category: string;
      http_status: number | null;
      retryable: boolean;
      retry_scheduled: boolean;
    } | null;
    /** OCR 内部请求计数，不等同于平台整批尝试次数。 */
    retry_summary?: {
      total_requests?: number;
      total_retries?: number;
      failed_requests?: number;
    } | null;
  } | null;
  result_path: string | null;
  notification_min_severity: "critical" | "high" | "medium" | "low";
  feedback: Record<number, "helpful" | "false_positive" | "ignored" | "fixed">;
  /** 当前尝试中每条发现关联的跨评审问题。 */
  issue_ids: Record<number, number>;
  /** 关联问题的持久化处理状态，不由反馈标记推断。 */
  issue_statuses?: Record<number, "open" | "fixed" | "ignored" | "false_positive" | "merged">;
  changed_files?: string | null;
  attempt_history: Array<{
    id: number;
    attempt_number: number;
    status: string;
    error: string | null;
    finished_at: string;
    failure_stage?: string | null;
    started_at?: string | null;
    scheduled_at?: string | null;
    retry_ready_at?: string | null;
    reason_code?: string | null;
  }>;
  /** 逐阶段实际开始和结束时间，旧记录不会回填。 */
  stage_timings?: Array<{ attempt_number: number; stage: string; started_at: string; finished_at: string | null }>;
  delivery: {
    id: number;
    correlation_id?: string;
    status: string;
    attempts: number;
    error: string | null;
    sent_at: string | null;
  } | null;
}

/** 项目级人工反馈统计；误报率仅以已标记发现为分母。 */
export interface ReviewFeedbackSummary {
  repository_id: number;
  repository_name: string;
  minimum_severity: "critical" | "high" | "medium" | "low";
  total: number;
  helpful: number;
  false_positive: number;
  /** 明确忽略的价值反馈，不是问题已忽略数量。 */ ignored?: number;
}

/** 由 Worker 异步执行的外部连接测试，不包含凭据或原始响应。 */
export interface ConnectionCheck {
  id: number;
  kind: "git" | "gitlab" | "model" | "feishu";
  repository_id: number | null;
  status: "queued" | "running" | "passed" | "failed";
  error: string | null;
  created_at: string;
  finished_at: string | null;
}

/** 管理写操作的路由级审计记录，不包含请求体或密钥。 */
export interface AuditEntry {
  id: number;
  actor_id: number | null;
  actor_name: string | null;
  action: string;
  object_type: string;
  object_id: number | null;
  outcome: string;
  created_at: string;
}

/** 管理操作分页结果；审计内容不包含请求体或密钥。 */
export interface AuditPage {
  items: AuditEntry[];
  total: number;
  page: number;
  page_size: number;
}
