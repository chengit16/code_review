/** @description 平台问题与改进契约及请求；独立于 OCR 发现，不执行部署或推断验证结果。 */
import { apiRequest } from "./client";

/** 归档独立于处理状态；恢复清空当前元数据，但历史保留操作事实。 */
export interface ArchiveMetadata {
  /** null 表示未归档。 */ archived_at: string | null;
  /** 当前归档操作者；恢复后为空。 */ archived_by: string;
  /** 当前归档原因；恢复原因保存在历史说明。 */ archive_reason: string;
}

/** 每版历史动作；不通过说明文字推断归档或解决。 */
export const archiveActionLabels = { create: "建立", update: "追加进展", archive: "归档", restore: "恢复" };

/** 当前可编辑摘要；三个交付维度必须分别记录。 */
export interface ImprovementContent {
  title: string;
  kind: "problem" | "improvement";
  category: "stability" | "performance" | "integration" | "deployment" | "experience" | "security" | "other";
  status: "open" | "investigating" | "planned" | "verifying" | "resolved" | "deferred";
  scope: string;
  description: string;
  analysis: string;
  solution: string;
  code_state: "unchanged" | "modified" | "not_applicable";
  verification_state: "not_run" | "passed" | "failed" | "blocked" | "not_applicable";
  validation_evidence: string;
  deployment_state: "not_deployed" | "confirmed" | "unknown" | "not_applicable";
  deployment_evidence: string;
  next_steps: string;
  references: string;
}

/** 服务端持久化记录和并发保存版本。 */
export interface ImprovementRecord extends ImprovementContent, ArchiveMetadata {
  id: number;
  version: number;
  created_at: string;
  updated_at: string;
}

/** 当前查询下的分页结果。 */
export interface ImprovementPage { status_counts?: Record<string, number>; items: ImprovementRecord[]; total: number; page: number; page_size: number }

/** 旧内容完整快照，不以最新结论覆盖。 */
export interface ImprovementRevision extends ArchiveMetadata {
  /** 该次版本的操作类型。 */ action: keyof typeof archiveActionLabels;
  version: number; actor: string; note: string; created_at: string; snapshot: ImprovementContent;
}

/** 历史独立分页，控制长文本返回量。 */
export interface ImprovementHistory { items: ImprovementRevision[]; total: number; page: number; page_size: number }

/** 有序阶段独立记录解决方案与本地、部署证据。 */
export interface ImprovementPhase {
  title: string; goal: string; status: "planned" | "active" | "completed" | "deferred";
  solution: string; code_state: ImprovementContent["code_state"];
  verification_state: ImprovementContent["verification_state"]; validation_evidence: string;
  deployment_state: ImprovementContent["deployment_state"]; deployment_evidence: string; next_steps: string;
}

/** 优化主题描述目标、阶段、结果和后续动作。 */
export interface ImprovementThemeContent {
  title: string; category: ImprovementContent["category"];
  status: "planned" | "active" | "paused" | "completed" | "deferred"; scope: string;
  objective: string; rationale: string; outcome: string; next_steps: string; references: string;
  phases: ImprovementPhase[];
}

/** 主题摘要及显式问题关联编号。 */
export interface ImprovementThemeRecord extends ImprovementThemeContent, ArchiveMetadata {
  id: number; version: number; improvement_ids: number[]; created_at: string; updated_at: string;
}

/** 主题分页查询。 */
export interface ImprovementThemePage { status_counts?: Record<string, number>; items: ImprovementThemeRecord[]; total: number; page: number; page_size: number }

/** 每次保存保留完整主题、阶段和当时的问题关联。 */
export interface ImprovementThemeRevision extends ArchiveMetadata {
  /** 该次版本的操作类型。 */ action: keyof typeof archiveActionLabels;
  version: number; actor: string; note: string; created_at: string;
  snapshot: ImprovementThemeContent; improvement_ids: number[];
}

/** 分页读取主题历史。 */
export interface ImprovementThemeHistory { items: ImprovementThemeRevision[]; total: number; page: number; page_size: number }

/** 列表条件由页面写入 URL；请求取消由查询层控制。 */
export function listImprovements(token: string, params: URLSearchParams, signal?: AbortSignal) {
  return apiRequest<ImprovementPage>(token, `/api/improvements?${params}`, { signal });
}

/** 读取当前摘要，不把查询失败当成新建草稿。 */
export function getImprovement(token: string, id: number, signal?: AbortSignal) {
  return apiRequest<ImprovementRecord>(token, `/api/improvements/${id}`, { signal });
}

/** 读取指定页的完整历史快照。 */
export function getImprovementHistory(token: string, id: number, page: number, signal?: AbortSignal) {
  return apiRequest<ImprovementHistory>(token, `/api/improvements/${id}/history?page=${page}`, { signal });
}

/** 创建键在同一份草稿的重试间保持不变。 */
export function createImprovement(token: string, content: ImprovementContent, clientKey: string) {
  return apiRequest<ImprovementRecord>(token, "/api/improvements", {
    method: "POST", body: JSON.stringify({ ...content, client_key: clientKey }),
  });
}

/** 乐观并发冲突由服务端拒绝，调用方保留草稿供人工核对。 */
export function updateImprovement(token: string, id: number, content: ImprovementContent, version: number, note: string) {
  return apiRequest<ImprovementRecord>(token, `/api/improvements/${id}`, {
    method: "PUT", body: JSON.stringify({ ...content, expected_version: version, progress_note: note }),
  });
}

/** 读取优化主题列表及其有序阶段和关联编号。 */
export function listImprovementThemes(token: string, params: URLSearchParams, signal?: AbortSignal) {
  return apiRequest<ImprovementThemePage>(token, `/api/improvement-themes?${params}`, { signal });
}

/** 读取单个优化主题。 */
export function getImprovementTheme(token: string, id: number, signal?: AbortSignal) {
  return apiRequest<ImprovementThemeRecord>(token, `/api/improvement-themes/${id}`, { signal });
}

/** 读取优化主题历史快照。 */
export function getImprovementThemeHistory(token: string, id: number, page: number, signal?: AbortSignal, pageSize = 25) {
  return apiRequest<ImprovementThemeHistory>(token, `/api/improvement-themes/${id}/history?page=${page}&page_size=${pageSize}`, { signal });
}

/** 创建主题时稳定复用客户端键。 */
export function createImprovementTheme(token: string, content: ImprovementThemeContent,
                                       improvementIds: number[], clientKey: string) {
  return apiRequest<ImprovementThemeRecord>(token, "/api/improvement-themes", {
    method: "POST", body: JSON.stringify({ ...content, improvement_ids: improvementIds, client_key: clientKey }),
  });
}

/** 版本冲突由服务端拒绝，当前编辑草稿保持不变。 */
export function updateImprovementTheme(token: string, id: number, content: ImprovementThemeContent,
                                       improvementIds: number[], version: number, note: string) {
  return apiRequest<ImprovementThemeRecord>(token, `/api/improvement-themes/${id}`, {
    method: "PUT", body: JSON.stringify({ ...content, improvement_ids: improvementIds,
      expected_version: version, progress_note: note }),
  });
}

/** 归档/恢复只接受目标状态、版本与原因；重复请求或并发冲突不追加历史。 */
export function changeImprovementArchive(token: string, resource: "records" | "themes", id: number,
                                         archived: boolean, version: number, reason: string) {
  const endpoint = resource === "themes"
    ? `/api/improvement-themes/${id}/archive` : `/api/improvements/${id}/archive`;
  return apiRequest<ArchiveMetadata & { version: number }>(token, endpoint, {
    method: "POST", body: JSON.stringify({ archived, expected_version: version, reason }),
  });
}
