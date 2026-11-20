/** @description 自建 Agent 能力目录、项目配置及后台检查契约。 */

import { apiRequest } from "./client";

export type AgentNode = "skills" | "read_file" | "mcp";
export interface FileLookup { pattern: string; path: string; start_line: number; lines: number }
export interface McpLookup {
  service_id: number; tool: string; pattern: string; argument: string;
  query: string; failure: "continue" | "stop";
}
export interface SchemeDocument {
  steps: AgentNode[]; skill_ids: number[]; files: FileLookup[]; mcp: McpLookup | null;
}
export interface AgentScheme {
  id: number; name: string; state: "draft" | "published" | "disabled";
  basis_id: number | null;
  document: SchemeDocument; actor: string; created_at: string;
}
export interface AgentSkill {
  id: number; name: string; pattern: string; body: string; actor: string; created_at: string;
}
export interface AgentMcpService {
  id: number; name: string; endpoint: string; enabled: boolean; timeout_seconds: number;
  has_token: boolean;
  tools: Record<string, { arguments: string[]; description: string }>;
  grants: { repository_id: number; tool: string }[];
}
export interface AgentCatalog {
  default_id: number; inheriting_projects: number[]; schemes: AgentScheme[];
  project_bindings: Record<string, number>;
  skills: AgentSkill[]; services: AgentMcpService[];
}
export interface AgentProjectInput {
  version: number; enabled: boolean; scheme_id: number | null; model_profile_id: number | null;
}
export interface AgentProject extends AgentProjectInput {
  manageable: boolean; effective_scheme: AgentScheme; effective_model: string | null;
  unavailable_reason: string | null;
}
export interface AgentCheck {
  id: number; kind: "preview" | "mcp"; status: "queued" | "running" | "complete" | "failed";
  result: {
    message?: string; job_id?: number; attempt?: number; scheme_id?: number; path_count?: number;
    mcp_authorized?: boolean | null;
    rows?: { path: string; skills: string[]; files: string[]; mcp: string | null }[];
    tools?: AgentMcpService["tools"];
  } | null;
}
export interface AgentCapabilityRun {
  scheme_id: number; name: string; trial: boolean; config_mode: "current" | "original";
  steps: AgentNode[]; skills: string[]; mcp: string | null;
  model_profile_id: number | null; model_profile_version: number | null;
}
export interface AgentCapabilityEvent {
  id: number; step: string; path: string; source: string; status: string; created_at: string;
  evidence: {
    path?: string; commit?: string; line?: number; document?: string; version?: string;
    sha256?: string; excerpt?: string; message?: string;
  } | null;
}

export const agentCatalogKey = ["agent-capabilities"] as const;
export const agentNodeLabels: Record<AgentNode, string> = {
  skills: "加载 Skill", read_file: "补查相关文件", mcp: "查询 MCP 规范",
};

/** 获取管理员可选能力。 */
export function getAgentCatalog(token: string, signal?: AbortSignal) {
  return apiRequest<AgentCatalog>(token, "/api/agent-capabilities", { signal });
}

function writeAgent<T>(token: string, path: string, method: string, body?: unknown) {
  return apiRequest<T>(token, path,
    { method, body: body === undefined ? undefined : JSON.stringify(body) });
}

export const saveSkill = (token: string, input: Pick<AgentSkill, "name" | "pattern" | "body">) =>
  writeAgent<{ id: number }>(token, "/api/agent-capabilities/skills", "POST", input);
export const saveScheme = (token: string, input: SchemeDocument & { name: string; basis_id: number | null }) =>
  writeAgent<{ id: number }>(token, "/api/agent-capabilities/schemes", "POST", input);
export const publishScheme = (token: string, id: number, enabled: boolean) =>
  writeAgent<void>(token, `/api/agent-capabilities/schemes/${id}/publication`, "PUT", { enabled });
export const selectDefaultScheme = (token: string, id: number, expected_id: number) =>
  writeAgent<void>(token, `/api/agent-capabilities/schemes/${id}/default`, "PUT", { expected_id });
export const previewScheme = (token: string, id: number, job_id: number) =>
  writeAgent<{ id: number }>(token, `/api/agent-capabilities/schemes/${id}/previews`, "POST", { job_id });
export const getSchemeTrials = (token: string, id: number, signal?: AbortSignal) =>
  apiRequest<{ id: number; job_id: number; status: string; created_at: string }[]>(
    token, `/api/agent-capabilities/schemes/${id}/trials`, { signal });
export const registerMcp = (token: string, input: { name: string; endpoint: string; token?: string; timeout_seconds: number }) =>
  writeAgent<{ id: number }>(token, "/api/agent-capabilities/services", "POST", input);
export const updateMcp = (token: string, id: number, enabled: boolean) =>
  writeAgent<void>(token, `/api/agent-capabilities/services/${id}/enabled`, "PUT", { enabled });
export const checkMcp = (token: string, id: number) =>
  writeAgent<{ id: number }>(token, `/api/agent-capabilities/services/${id}/checks`, "POST");
export const saveGrant = (token: string, id: number, input: AgentMcpService["grants"][number]) =>
  writeAgent<void>(token, `/api/agent-capabilities/services/${id}/grants`, "PUT", input);
export function revokeGrant(token: string, id: number, repositoryId: number, tool: string) {
  const name = encodeURIComponent(tool);
  return writeAgent<void>(token, `/api/agent-capabilities/services/${id}/grants/${repositoryId}/${name}`, "DELETE");
}

/** 轮询 Worker 检查，不重复登记。 */
export function getAgentCheck(token: string, id: number, signal?: AbortSignal) {
  return apiRequest<AgentCheck>(token, `/api/agent-capabilities/checks/${id}`, { signal });
}

/** 读取项目显示值及并发基线。 */
export function getAgentProject(token: string, id: number, signal?: AbortSignal) {
  return apiRequest<AgentProject>(token, `/api/repositories/${id}/agent-settings`, { signal });
}

/** 保存项目选择和共用的仓库试点授权。 */
export function saveAgentProject(token: string, id: number, value: AgentProjectInput) {
  return apiRequest<AgentProject>(token, `/api/repositories/${id}/agent-settings`, {
    method: "PUT", body: JSON.stringify(value),
  });
}
