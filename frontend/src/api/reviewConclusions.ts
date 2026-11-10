/** @description 初审与补审候选的只读类型；来源 ID 不得作为旧反馈或发布接口的评论索引。 */

import { apiRequest } from "./client";
import type { CumulativeUsage } from "./reviewExecution";

/** 覆盖数量来自持久化集合，历史缺失时对象为空而不是补零。 */
export interface ConclusionCoverage {
  selected: number;
  completed: number;
  reused: number;
  failed: number;
  waived: number;
}

/** revision=0 为根尝试，正数为独立补审候选；不改变旧任务状态。 */
export interface ConclusionVersion {
  source_attempt: number;
  revision: number;
  recovery_id: number | null;
  terminal_state: string;
  coverage: ConclusionCoverage | null;
  finding_count: number;
}

/** 各查询共用的摘要；消费者未接通前候选不会提升为平台有效结论。 */
export interface ConclusionOverview {
  consumer_integration_ready: boolean;
  initial: ConclusionVersion | null;
  candidate: ConclusionVersion | null;
  effective?: ConclusionVersion | null;
}

/** 固定到根尝试或补审批次的来源身份，不随聚合中的位置变化。 */
export interface FindingOrigin {
  kind: "attempt" | "recovery";
  source_attempt: number;
  recovery_id: number | null;
  comment_index: number;
}

/** 只读发现：不能把数组下标交给旧反馈接口。 */
export interface ConclusionFinding {
  finding_id: string;
  origin: FindingOrigin;
  also_seen_in: FindingOrigin[];
  path: string;
  content: string;
  start_line: number | null;
  end_line: number | null;
  severity: string | null;
  category: string | null;
}

/** 显式版本读模型；用量仅包括源尝试及截止该候选的批次，不是完整实际账单。 */
export interface ConclusionDocument {
  schema_version: "platform.review-conclusion/v1";
  consumer_integration_ready: boolean;
  job_id: number;
  version: ConclusionVersion;
  role: "initial" | "candidate" | "effective";
  is_current_source: boolean;
  findings: ConclusionFinding[];
  input_filter_excluded_count: number | null;
  execution_usage: CumulativeUsage;
  usage_through_recovery_id: number | null;
}

/** 反馈以稳定主身份持久化；版本参数只校验写入资格，不冻结人工反馈的后续变化。 */
export interface FindingFeedbackVersion {
  source_attempt: number;
  revision: number;
}

/** 新反馈入口要求最新版本，不能用聚合数组下标调用旧接口。 */
export interface FindingFeedbackWrite extends FindingFeedbackVersion {
  verdict: "helpful" | "false_positive" | "ignored";
}

/** 根尝试和补审反馈按同一身份读取；历史可读但不接受旧版本写入。 */
export interface FindingFeedbackRecord {
  finding_id: string;
  verdict: "helpful" | "false_positive" | "ignored" | "fixed";
  actor: string;
  updated_at: string;
}

/** 按稳定主身份写反馈；删除同样要求源版本，不接受聚合数组下标。 */
export function setFindingFeedback(token: string, jobId: number, findingId: string, version: FindingFeedbackVersion, verdict: FindingFeedbackWrite["verdict"] | null) {
  const identifier = encodeURIComponent(findingId);
  return apiRequest(token, `/api/jobs/${jobId}/finding-feedback/${identifier}${verdict ? "" : `?source_attempt=${version.source_attempt}&revision=${version.revision}`}`, verdict ? { method: "PUT", body: JSON.stringify({ ...version, verdict }) } : { method: "DELETE" });
}
