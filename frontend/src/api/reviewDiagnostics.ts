/** @description 分层失败诊断的安全服务端契约；不包含外部响应、工具参数或推理。 */

/** 单个失败逻辑请求；响应头计时不能冒充整个分组耗时。 */
export interface RequestEvidence {
  /** 固定十六进制摘要；无法验证的原始请求标识不展示。 */
  logical_request_id?: string | null;
  group_id: string | null;
  task_type: "plan_task" | "main_task" | "unknown";
  request_no: number | null;
  attempts: number;
  http_statuses: number[];
  error_classes: string[];
  failure_phases: string[];
  duration_to_headers_ms: number[];
  observed_backoff_ms: number[];
}

/** 版本化安全投影；报告不完整时不能推测请求成功率或根因。 */
export interface FailureAnalysis {
  schema_version: "platform.failure-analysis/v1";
  summary: string;
  selected_count: number;
  completed_count: number;
  failed_count: number;
  failed_group_count: number | null;
  report_state: "available" | "missing" | "unsupported" | "malformed" | "limited";
  groups: Array<{ group_id: string; paths: string[]; failed_count: number }>;
  requests: RequestEvidence[];
  signals: Array<{ code: string; message: string; count: number }>;
  notes: string[];
}
