/** @description GitLab 事件收件箱与按时间补审请求；所有外部查询均由 Worker 执行。 */

import { apiRequest } from "./client";
import type { MergeEvent } from "./types";

/** 一页事件及其关联任务数量，事件记录以 SQLite 为准。 */
export interface EventPage {
  items: MergeEvent[];
  total: number;
  page: number;
  page_size: number;
}

/** 最近一次补审申请的持久化状态，不代表其中 MR 已完成评审。 */
export interface MrBackfill {
  id: number;
  repository_id: number;
  repository_name: string;
  since: string;
  until: string;
  status: "queued" | "running" | "done" | "failed";
  scanned: number;
  enqueued: number;
  error: string | null;
  created_at: string;
  finished_at: string | null;
}

/** 查询事件收件箱；参数包含筛选和分页并支持取消过期查询。 */
export function searchEvents(token: string, params: URLSearchParams, signal?: AbortSignal) {
  return apiRequest<EventPage>(token, `/api/event-search?${params}`, { signal });
}

/** 读取近期按时间补审申请及 Worker 扫描进度。 */
export function listMrBackfills(token: string, signal?: AbortSignal) {
  return apiRequest<MrBackfill[]>(token, "/api/mr-backfills", { signal });
}

/** 仅创建补审申请；具体 GitLab 分页和 MR 入队由 Worker 完成。 */
export function enqueueMrBackfill(
  token: string,
  repositoryId: number,
  since: string,
  until: string,
) {
  return apiRequest<{ id: number }>(token, `/api/repositories/${repositoryId}/mrs/backfill`, {
    method: "POST",
    body: JSON.stringify({ since, until }),
  });
}

/** 仅将需要人工处理的异常事件重置为待消费状态。 */
export function retryEvent(token: string, eventId: number) {
  return apiRequest<{ status: string }>(token, `/api/events/${eventId}/retry`, {
    method: "POST",
  });
}
