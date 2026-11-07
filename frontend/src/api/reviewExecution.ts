/** @description 评审时间、范围与累计费用的服务端事实类型；缺失字段表示历史未知。 */

/** 时间由服务端按 UTC 计算，累计执行完整性独立于数值。 */
export interface ReviewTiming {
  first_queue_seconds: number | null;
  latest_execution_seconds: number | null;
  cumulative_execution_seconds: number | null;
  execution_complete: boolean;
  known_attempts: number;
  total_attempts: number;
  total_elapsed_seconds: number | null;
  retry_backoff_seconds: number | null;
  retry_ready_wait_seconds: number | null;
  schedule_complete: boolean;
  calculated_at: string;
}

/** 原始范围的严格换行分析，不等于已经从 OCR 输入排除。 */
export interface ScopeAnalysis {
  mode: string;
  status: string;
  original_count: number | null;
  newline_only_count: number;
  /** 详情提供路径，列表为缩小响应省略。 */
  newline_only_paths?: string[];
  excluded_count: number;
  checked_count: number;
  ocr_candidate_count?: number;
  ocr_excluded_count?: number;
  filter_enabled: boolean;
  filter_reason: string;
}

/** 多次尝试的已知用量下限，费用使用逐次历史单价且不同币种不相加。 */
export interface CumulativeUsage {
  known_usage_attempts: number;
  total_attempts: number;
  usage_complete: boolean;
  priced_attempts: number;
  known_tokens: { input_tokens?: number; output_tokens?: number; total_tokens: number } | null;
  known_costs: Array<{ currency: "CNY" | "USD"; total: string }>;
  cost_complete: boolean;
}

/** 近七天按项目、状态、原始规模分组的统计；无样本时分位数为空。 */
export interface PerformanceGroup {
  repository_id: number;
  status: string;
  size_bucket: string;
  count: number;
  execution_samples: number;
  execution_p50_seconds: number | null;
  execution_p95_seconds: number | null;
  queue_samples: number;
  queue_p50_seconds: number | null;
  queue_p95_seconds: number | null;
  timeout_count: number;
  timeout_rate: number;
  retry_count: number;
  unknown_usage_count: number;
  known_tokens: number;
}

/** 执行槽来自受保护的监控接口，不含凭据或代码，过期心跳不授予抢占权。 */
export interface SchedulerSnapshot {
  model_task_concurrency: number;
  applied_concurrency?: number | null;
  applied_version?: number | null;
  config_version?: number;
  running_model_tasks?: number;
  draining?: boolean;
  slots: Array<{ slot_id?: string; slot_index?: number; lane: string; owner: string; generation: number; task_kind: string | null;
    task_id: number | null; repository_id: number | null; state: string;
    heartbeat_at: string; heartbeat_age_seconds: number }>;
}
