/** @description 问题批量处理契约及同源请求；只提交显式勾选项，不处理页面提示或授权。 */
import { apiRequest } from "./client";

/** 人工可修改的问题状态，不包含已合并的只读来源项。 */
export type IssueActionStatus = "open" | "fixed" | "ignored";

/** 显式目标与勾选时的状态快照，用于服务端并发校验。 */
export interface IssueBatchTarget {
  /** 关联问题的持久化编号。 */ id: number;
  /** 勾选时状态；其他入口后续更改会导致整批冲突。 */ expected_status: IssueActionStatus;
}

/** 同事务提交后的计数；未变化项不会重复写处理记录。 */
export interface IssueBatchResult {
  /** 已确认的目标状态。 */ status: IssueActionStatus;
  /** 实际改变状态的问题数。 */ updated: number;
  /** 已处于目标状态的问题数。 */ unchanged: number;
}

/** 批量修改至多 100 条显式目标；401、403、404、409 均保留为统一请求错误。 */
export function updateReviewIssues(token: string, targets: IssueBatchTarget[], status: IssueActionStatus, note: string) {
  return apiRequest<IssueBatchResult>(token, "/api/review-issues/batch-update", {
    method: "POST", body: JSON.stringify({ targets, status, note: note.trim() || null }),
  });
}
