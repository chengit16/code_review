/** @description 统一发现列表和批量反馈服务；会话、取消与错误沿用统一 Client，服务端负责授权和版本校验。 */
import { apiRequest } from "./client";
import type { QualityFinding } from "./effectiveness";
import type { FindingFeedbackVersion } from "./reviewConclusions";

/** 当前有效发现的列表投影。 */
export interface ReviewFinding extends QualityFinding {
  /** 原提交作者，不代表责任人。 */ commit_author: string | null;
  /** 只由当前三类反馈决定。 */ handling: "pending" | "handled";
}
/** 详情正文与行号，只在用户打开时加载。 */
export interface ReviewFindingDetail extends ReviewFinding {
  /** 已落库的发现描述与建议。 */ content: string;
  /** 零或空表示文件级发现。 */ start_line: number | null;
}
/** 冻结选择，不跟随后台刷新替换来源版本。 */
export interface FeedbackTarget extends FindingFeedbackVersion {
  /** 所属任务。 */ job_id: number;
  /** 主发现稳定身份。 */ finding_id: string;
}
/** 逐项结果，失败不代表其他项回滚。 */
export interface BatchFeedbackResult {
  /** 成功条数。 */ updated: number;
  /** 冻结目标的逐项结果。 */ results: Array<{ finding_id: string; status: "updated" | "conflict" | "not_found"; code?: string }>;
}
/** 服务端先筛选后分页，支持显式窗口与取消。 */
export function getReviewFindings(token: string, query: string, signal?: AbortSignal) {
  return apiRequest<{ items: ReviewFinding[]; total: number; page: number; page_size: number; since: string; until: string }>(token, `/api/review-findings?${query}`, { signal });
}
/** 只读主身份详情；旧版本消失时返回错误，不能偷偷选择另一条。 */
export function getReviewFinding(token: string, findingId: string, signal?: AbortSignal) {
  return apiRequest<ReviewFindingDetail>(token, `/api/review-findings/${encodeURIComponent(findingId)}`, { signal });
}
/** 显式提交冻结目标，不自动重试版本冲突或失败项。 */
export function batchFindingFeedback(token: string, targets: FeedbackTarget[], verdict: "helpful" | "false_positive" | "ignored") {
  return apiRequest<BatchFeedbackResult>(token, "/api/review-findings/batch-feedback", { method: "POST", body: JSON.stringify({ targets, verdict }) });
}
