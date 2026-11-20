/** @description 双评审读写契约。HTTP 访问沿用管理会话，裁定和重跑分别提交。 */

import { apiRequest } from "./client";
import type { AgentCapabilityEvent, AgentCapabilityRun } from "./agentCapabilities";

export type Verdict = "valid" | "invalid" | "insufficient";
export type EvidenceSide = "base" | "head";
export type RunStatus = "queued" | "running" | "complete" | "partial" | "failed" | "skipped" | "cancelled";
export interface ComparisonSummary {
  id: number;
  source_attempt: number;
  previous_id: number | null;
  status: RunStatus;
  created_at: string;
  finished_at: string | null;
  trial?: boolean;
  capability_recorded?: boolean;
}
/** 任务所属仓库的当前授权；管理资格还需叠加管理员权限。 */
export interface ComparisonPilot {
  repository_name: string;
  enabled: boolean;
  manageable: boolean;
}
export interface ComparisonIndex {
  current_source_attempt: number | null;
  previous_id: number | null;
  active_id: number | null;
  pilot: ComparisonPilot;
  unavailable_reason: string | null;
  items: ComparisonSummary[];
  next_before_id: number | null;
  current_scheme_id?: number | null;
  current_scheme_name?: string | null;
}
export interface ComparisonFinding {
  id: string;
  path: string;
  line: number | null;
  side: EvidenceSide | null;
  title: string;
  content: string;
  impact: string;
  excerpt: string;
  capability_refs?: number[];
}
export interface ComparisonUsage {
  model: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  unknown_calls: number;
  cost: string | null;
  currency: string | null;
}
export interface Evaluation {
  finding_id: string;
  verdict: Verdict;
  worth_fixing: boolean | null;
  note: string;
}
export interface FindingMatch { id: string; label: string; ocr_ids: string[]; agent_ids: string[] }
export interface MissedFinding {
  id: string;
  title: string;
  path: string;
  line: number | null;
  side: EvidenceSide | null;
  note: string;
}
export interface CurationDocument { evaluations: Evaluation[]; matches: FindingMatch[]; missed: MissedFinding[] }
export interface CurationSnapshot {
  version: number;
  actor: string | null;
  created_at: string | null;
  document: CurationDocument;
}
export interface AgentComparison extends ComparisonSummary {
  base_sha: string;
  head_sha: string;
  ocr: {
    status: string;
    coverage: { selected: number; completed: number; reused: number; failed: number; waived: number } | null;
    findings: ComparisonFinding[];
    usage: ComparisonUsage;
  };
  agent: {
    reason: string | null;
    files: {
      path: string;
      delivered: number;
      reviewed: number;
      total: number;
      rule?: { source: string; pattern: string; sha256: string } | null;
    }[] | null;
    excluded_paths: string[];
    findings: ComparisonFinding[];
    usage: ComparisonUsage;
    capabilities?: AgentCapabilityRun | null;
    capability_events?: AgentCapabilityEvent[];
    workflow_steps?: string[];
  };
  suggestions: FindingMatch[];
  curation: CurationSnapshot;
  latest_curation_version: number;
}
export interface ComparisonCreate {
  source_attempt: number; previous_id: number | null; request_key: string;
  config_mode?: "current" | "original"; trial_scheme_id?: number; expected_scheme_id?: number;
  original_run_id?: number;
}

/** 按稳定版本号读取历史页及当前运行资格。 */
export function getAgentComparisons(token: string, jobId: number, beforeId: number | null, signal?: AbortSignal) {
  return apiRequest<ComparisonIndex>(token, `/api/jobs/${jobId}/agent-comparisons${beforeId ? `?before_id=${beforeId}` : ""}`, { signal });
}

/** 不指定裁定修订时读取该比较的最新人工记录。 */
export function getAgentComparison(token: string, jobId: number, id: number, version: number | null, signal?: AbortSignal) {
  return apiRequest<AgentComparison>(token, `/api/jobs/${jobId}/agent-comparisons/${id}${version === null ? "" : `?curation_version=${version}`}`, { signal });
}

/** 同一确认草稿沿用请求键，丢失响应后可以找回已排队的尝试。 */
export function createAgentComparison(token: string, jobId: number, body: ComparisonCreate) {
  return apiRequest<{ id: number }>(token, `/api/jobs/${jobId}/agent-comparisons`, {
    method: "POST", body: JSON.stringify(body),
  });
}

/** 保存任务所属仓库的试点授权，模型任务需要另行确认。 */
export function updateAgentPilot(token: string, jobId: number, enabled: boolean) {
  return apiRequest<void>(token, `/api/jobs/${jobId}/agent-comparisons/pilot`, {
    method: "PUT", body: JSON.stringify({ enabled }),
  });
}

/** 根据编辑起始版本追加人审记录，冲突不会自动重试。 */
export function saveComparisonCuration(token: string, jobId: number, id: number, basis: number, document: CurationDocument) {
  return apiRequest<CurationSnapshot>(token, `/api/jobs/${jobId}/agent-comparisons/${id}/curation`, {
    method: "PUT", body: JSON.stringify({ expected_version: basis, document }),
  });
}
