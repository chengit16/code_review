/** @description 接入辅助只访问同源管理 API；外部请求由 Worker 执行，不在查询键或 URL 保存令牌。 */
import { apiRequest } from "../client";

/** 仓库白名单元数据，不含凭据或上游完整响应。 */
export interface RepositoryMetadata {
  name: string;
  project_id: number;
  path_with_namespace: string;
  target_branch: string;
  remote_url: string;
  gitlab_url: string;
}

/** 生效配置用于说明后续任务；历史任务仍以自己的快照为准。 */
export interface EffectiveConfiguration {
  repository_id: number;
  model: { id: number | null; name: string | null; model: string | null; complete: boolean; source: "project" | "global" };
  timeout_seconds: { value: number; source: "project" | "process" };
  max_files: number | null;
  max_tokens_budget: number | null;
  newline_filter_enabled: boolean;
  rules: { global_configured: boolean; project_configured: boolean; repository_file: string };
  repository_change: { id: number; created_at: string } | null;
  latest_job: { id: number; status: string; finished_at: string | null } | null;
}

/** 显式创建资料请求；不复用其他项目保存的令牌，取消只停止尚未完成的本次请求。 */
export async function discoverRepository(token: string, remoteUrl: string, gitlabToken: string, signal: AbortSignal): Promise<RepositoryMetadata> {
  const queued = await apiRequest<{ id: number }>(token, "/api/repository-discoveries", { method: "POST", body: JSON.stringify({ remote_url: remoteUrl, gitlab_token: gitlabToken }), signal });
  try {
    for (let attempt = 0; attempt < 60; attempt++) {
      await new Promise<void>((resolve, reject) => {
        const cancel = () => { clearTimeout(timer); reject(new DOMException("已取消", "AbortError")); };
        const timer = setTimeout(() => { signal.removeEventListener("abort", cancel); resolve(); }, 1000);
        if (signal.aborted) cancel(); else signal.addEventListener("abort", cancel, { once: true });
      });
      const result = await apiRequest<{ status: string; error: string | null; result: RepositoryMetadata | null }>(token, `/api/repository-discoveries/${queued.id}`, { signal });
      if (result.status === "failed") throw new Error(result.error ?? "读取失败，请手动填写");
      if (result.status === "passed" && result.result) return result.result;
    }
    throw new Error("等待 Worker 超时；可重新获取或继续手动填写");
  } finally {
    void apiRequest(token, `/api/repository-discoveries/${queued.id}`, { method: "DELETE" }).catch(() => undefined);
  }
}

/** 读取保存事实，取消或旧响应不应覆盖编辑草稿。 */
export function getEffectiveConfiguration(token: string, repositoryId: number, signal?: AbortSignal) {
  return apiRequest<EffectiveConfiguration>(token, `/api/repositories/${repositoryId}/effective-configuration`, { signal });
}

/** 查询引用仅用于当前草稿，凭据不进入 URL 或缓存键。 */
export interface RepositoryQuerySession { session_id: string; id: number }

/** 分页分支响应，服务端搜索完整远端集合。 */
export interface RepositoryBranches { items: { name: string; default: boolean }[]; next_page: number | null }

/** 等待 Worker 的单次只读查询；放弃时清理未完成请求。 */
export async function waitRepositoryQuery<T>(token: string, id: number, signal: AbortSignal): Promise<T> {
  try {
    for (let attempt = 0; attempt < 120; attempt++) {
      if (signal.aborted) throw new DOMException("已取消", "AbortError");
      const result = await apiRequest<{ status: string; error: string | null; result: T | null }>(token, `/api/repository-discoveries/${id}`, { signal });
      if (result.status === "passed" && result.result) return result.result;
      if (result.status === "failed") throw new Error(result.error ?? "远程读取失败，请重试");
      await new Promise<void>((resolve, reject) => {
        const abort = () => { clearTimeout(timer); reject(new DOMException("已取消", "AbortError")); };
        const timer = setTimeout(() => { signal.removeEventListener("abort", abort); resolve(); }, 1000);
        signal.addEventListener("abort", abort, { once: true });
        if (signal.aborted) abort();
      });
    }
    throw new Error("等待 Worker 超时，请确认 Worker 正在运行后重试");
  } finally {
    void apiRequest(token, `/api/repository-discoveries/${id}`, { method: "DELETE" }).catch(() => undefined);
  }
}

/** 创建绑定当前管理员会话的短期查询，不读取其他主机的已存 Token。 */
export function createRepositoryQuery(token: string, remoteUrl: string, gitlabToken: string, repositoryId: number | undefined, signal: AbortSignal) {
  return apiRequest<RepositoryQuerySession>(token, "/api/repository-query-sessions", { method: "POST", body: JSON.stringify({ remote_url: remoteUrl, gitlab_token: gitlabToken, repository_id: repositoryId }), signal });
}

/** 远程分页搜索由 Worker 执行，取消后旧结果不得覆盖当前草稿。 */
export async function queryRepositoryBranches(token: string, session: string, search: string, page: number, signal: AbortSignal) {
  const queued = await apiRequest<{ id: number }>(token, `/api/repository-query-sessions/${session}/branches`, { method: "POST", body: JSON.stringify({ search, page }), signal });
  return waitRepositoryQuery<RepositoryBranches>(token, queued.id, signal);
}
