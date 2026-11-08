/** @description 概览只读契约；新增汇总可缺失，不用零掩盖旧服务不支持。 */
import { apiRequest } from "./client";
import type { ReviewJob } from "./types";

/** 全局运行事实与问题摘要；效果区筛选不改变本范围。 */
export interface Overview {
  /** 兼容原有任务历史口径。 */
  summary: { repositories: number; queued: number; running: number; complete: number;
    attention: number; historical_failed: number; notification_failed: number; total: number };
  /** 启用范围内的最新异常。 */
  todo: { events_attention: number; premerge_failed: number; premerge_partial: number };
  /** 全部项目的去重开放问题，旧服务可能缺失。 */
  issue_todo?: { open_count: number; severity_counts: Record<"critical" | "high" | "medium" | "low" | "unclassified", number> };
  /** 包含活动补审的去重任务数，旧服务可能缺失。 */
  activity?: { queued: number; running: number; total: number };
  /** 最近八个任务，不代表全量。 */
  recent: ReviewJob[];
}

/** 读取概览；取消与鉴权沿用统一 Client。 */
export function getOverview(token: string, signal?: AbortSignal) {
  return apiRequest<Overview>(token, "/api/overview", { signal });
}
