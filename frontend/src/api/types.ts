/** @description 管理 API 的稳定前端投影；密文字段不进入浏览器类型。 */

/** 仓库接入信息与 GitLab 回调地址。 */
export interface Repository {
  id: number;
  name: string;
  gitlab_url: string;
  project_id: number;
  remote_url: string;
  target_branch: string;
  auth_kind: "signing" | "secret";
  enabled: number;
  webhook_id: string | null;
  last_webhook_at: string | null;
  has_feishu_webhook: boolean;
  webhook_url: string;
  created_at: string;
}

/** API 存活状态与独立 Worker 的文件锁状态。 */
export interface Health {
  status: "ok";
  auth_mode: "dev" | "admin";
  worker: "running" | "stopped";
}

/** 新仓库表单；密钥只在创建请求中提交，不在响应中回显。 */
export interface RepositoryInput {
  name: string;
  gitlab_url: string;
  project_id: number;
  remote_url: string;
  target_branch: string;
  auth_kind: "signing" | "secret";
  webhook_token: string;
  feishu_webhook?: string;
}

/** 仓库可变设置；GitLab 项目身份和 Git remote 保持不可变。 */
export interface RepositoryUpdateInput {
  name?: string;
  enabled?: boolean;
  auth_kind?: "signing" | "secret";
  webhook_token?: string;
  feishu_webhook?: string;
  webhook_id?: string | null;
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
  mr_url?: string;
  commit_url?: string;
  result: {
    comments?: ReviewComment[];
    manifest?: ReviewManifest;
    preview?: ReviewPreview;
    message?: string;
  } | null;
  result_path: string | null;
  attempt_history: Array<{
    id: number;
    attempt_number: number;
    status: string;
    error: string | null;
    finished_at: string;
  }>;
  delivery: {
    id: number;
    status: string;
    attempts: number;
    error: string | null;
    sent_at: string | null;
  } | null;
}

/** 全局 OCR 模型的安全投影；密钥仅可单向更新。 */
export interface ModelProfile {
  provider: string;
  model: string;
  has_api_key: boolean;
  version: number;
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
  action: string;
  object_type: string;
  object_id: number | null;
  outcome: string;
  created_at: string;
}
