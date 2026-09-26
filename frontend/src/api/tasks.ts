/** @description 任务检索与脱敏报告下载，管理口令仅随同源请求发送。 */

import { apiRequest } from "./client";
import type { TaskPage } from "./types";

/** 筛选和页码是查询键的一部分，取消离开的请求，防止旧结果覆盖新视图。 */
export function searchTasks(token: string, params: URLSearchParams, signal?: AbortSignal) {
  return apiRequest<TaskPage>(token, `/api/task-search?${params}`, { signal });
}

/** 下载服务器白名单报告，浏览器对象地址用完即释放，令牌不进入下载 URL。 */
export async function downloadTaskReport(token: string, id: number) {
  const report = await apiRequest<unknown>(token, `/api/jobs/${id}/report`);
  const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `review-${id}.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
