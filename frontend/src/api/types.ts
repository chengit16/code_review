/** @description 管理 API 的稳定前端投影；密文字段不进入浏览器类型。 */

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
  version: number;
}

/** GitLab 合并事件收件箱记录。 */
export interface MergeEvent {
  id: number;
  repository_id: number;
  mr_iid: number;
  delivery_id: string | null;
  merge_sha: string | null;
  squash_sha: string | null;
  status: string;
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

/** 逐提交评审任务列表数据。 */
export interface ReviewJob {
  id: number;
  repository_id: number;
  event_id: number;
  mr_iid: number;
  commit_sha: string;
  ordinal: number;
  status: string;
  error: string | null;
  attempts: number;
  created_at: string;
  finished_at: string | null;
  target_branch?: string;
  repository_name?: string;
  failure_stage?: string | null;
}

/** 服务端筛选后的任务总量与单页结果，不受旧版最近 200 条限制。 */
export interface TaskPage {
  items: ReviewJob[];
  total: number;
  page: number;
  page_size: number;
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
    usage?: { input_tokens?: number; output_tokens?: number; total_tokens?: number };
    summary?: { budget_exceeded?: boolean };
    message?: string;
  } | null;
  result_path: string | null;
  notification_min_severity: "critical" | "high" | "medium" | "low";
  feedback: Record<number, "helpful" | "false_positive" | "fixed">;
  changed_files?: string | null;
  attempt_history: Array<{
    id: number;
    attempt_number: number;
    status: string;
    error: string | null;
    finished_at: string;
    failure_stage?: string | null;
  }>;
  delivery: {
    id: number;
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
  fixed: number;
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
