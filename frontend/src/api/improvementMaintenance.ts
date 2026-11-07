/** @description 管理员归档策略与后台执行事实；不传服务器路径，不在浏览器执行归档。 */
import { apiRequest } from "./client";

/** 后台提交的计数与当前候选；保存策略不代表归档已经完成。 */
export interface MaintenanceStatus {
  enabled: boolean;
  archive_after_days: number;
  version: number;
  source_configured: boolean;
  last_checked_at: string | null;
  last_success_at: string | null;
  last_error_code: string;
  last_result: {
    sync: { created: number; updated: number; unchanged: number; conflicts: string[] };
    archived_records: number; archived_themes: number;
  };
  candidate_records: number;
  candidate_themes: number;
}

/** 查询只读状态，失败不降级为未启用或零数据。 */
export function getImprovementMaintenance(token: string, signal?: AbortSignal) {
  return apiRequest<MaintenanceStatus>(token, "/api/improvement-maintenance", { signal });
}

/** 保存版本化策略，冲突由调用方保留草稿；实际执行交给独立 monitor。 */
export function setImprovementMaintenance(token: string, enabled: boolean, days: number, version: number) {
  return apiRequest<MaintenanceStatus>(token, "/api/improvement-maintenance", {
    method: "PUT", body: JSON.stringify({ enabled, archive_after_days: days, expected_version: version }),
  });
}
