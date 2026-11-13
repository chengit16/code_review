/** @description 任务检索与脱敏报告下载，管理口令仅随同源请求发送。 */

import { apiRequest } from "./client";
import type { ReviewJob, TaskPage } from "./types";

/** 删除确认时冻结的终态版本；后台变化须由服务端返回冲突。 */
export type TaskDeletionTarget = Pick<ReviewJob, "id" | "status" | "attempts" | "finished_at">;

/** 删除单条已结束任务及其统计来源，不撤回已发通知或清理工件。 */
export function deleteTask(token: string, target: TaskDeletionTarget) {
  return apiRequest<{ status: "deleted"; job_id: number; deleted_findings: number; deleted_issues: number }>(token, `/api/jobs/${target.id}`, {
    method: "DELETE",
    body: JSON.stringify({ expected_status: target.status, expected_attempts: target.attempts, expected_finished_at: target.finished_at }),
  });
}

/** 单个 MR 补触发请求的入队结果。 */
export interface MrEnqueueResult {
  /** MR IID。 */
  id: number;
  /** queued 表示已创建后台事件，其他状态表示重复或拒绝。 */
  status: string;
}

/** 筛选和页码是查询键的一部分，取消离开的请求，防止旧结果覆盖新视图。 */
export function searchTasks(token: string, params: URLSearchParams, signal?: AbortSignal) {
  return apiRequest<TaskPage>(token, `/api/task-search?${params}`, { signal });
}

/** 按仓库和 IID 补触发已合并 MR；请求只创建后台事件，不在页面请求内访问 GitLab。 */
export function enqueueMergedMrs(token: string, repositoryId: string, ids: number[]) {
  return apiRequest<MrEnqueueResult[]>(token, `/api/repositories/${repositoryId}/mrs/batch-enqueue`, {
    method: "POST",
    body: JSON.stringify({ ids }),
  });
}

/** 按列表筛选获取邻项，页码不限制导航范围；仅返回编号且支持取消旧请求。 */
export function getTaskNeighbors(token: string, id: number, params: URLSearchParams, signal?: AbortSignal) {
  const filters = new URLSearchParams(params);
  filters.delete("page");
  filters.delete("page_size");
  return apiRequest<{ previous_id: number | null; next_id: number | null }>(token, `/api/jobs/${id}/neighbors?${filters}`, { signal });
}

/** 下载服务器白名单报告，浏览器对象地址用完即释放，令牌不进入下载 URL。 */
export async function downloadTaskReport(token: string, id: number, attempt?: number) {
  const report = await apiRequest<unknown>(token, `/api/jobs/${id}/report${attempt ? `?attempt=${attempt}` : ""}`);
  const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `review-${id}${attempt ? `-attempt-${attempt}` : ""}.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
