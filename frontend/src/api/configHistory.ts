/** @description 配置历史查询与恢复协议；只返回脱敏差异，恢复目标由调用方冻结。 */
import { apiRequest } from "./client";

/** 持久化配置版本；凭据字段只包含是否配置，不含密文或明文。 */
export interface ConfigRevision {
  /** 版本编号。 */ id: number;
  /** 所属配置对象。 */ object_id: number;
  /** 新增、修改、删除或迁移基线。 */ action: string;
  /** 已保存的操作人。 */ actor: string;
  /** 记录时间。 */ created_at: string;
  /** 版本是否包含可恢复快照；还需核对对象仍存在。 */ restorable: boolean;
  /** 脱敏字段差异。 */ changes: { field: string; secret: boolean; before: unknown; after: unknown }[];
}

/** 查询完整配置历史，支持 URL 筛选分页和卸载取消；失败不转换为空列表。 */
export function searchConfigHistory(token: string, query: URLSearchParams, signal?: AbortSignal) {
  return apiRequest<{ items: ConfigRevision[]; total: number }>(token, `/api/config-history-search?${query}`, { signal });
}

/** 恢复明确的历史目标；服务端仍校验管理权限和当前业务保护条件。 */
export function restoreConfigRevision(token: string, kind: string, objectId: number, revisionId: number) {
  return apiRequest(token, `/api/config-history/${kind}/${objectId}/${revisionId}/restore`, { method: "POST" });
}
