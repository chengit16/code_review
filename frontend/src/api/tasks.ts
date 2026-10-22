/** @description 任务检索与脱敏报告下载，管理口令仅随同源请求发送。 */

import { apiRequest } from "./client";
import type { TaskPage } from "./types";

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
