/**
 * @description 展示连接测试命令与 Worker 保存的最近结果。
 *
 * 测试请求只入队；状态以服务端记录为准，飞书测试会向目标群发送消息。
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity } from "lucide-react";

import { apiRequest } from "../api/client";
import type { ConnectionCheck } from "../api/types";
import { formatTime } from "./format";
import { Status } from "./Status";

type CheckKind = ConnectionCheck["kind"];

const labels: Record<CheckKind, string> = {
  git: "Git",
  gitlab: "GitLab API",
  model: "模型",
  feishu: "飞书",
};

interface ConnectionChecksProps {
  /** 内存中的管理口令，只用于同源 API 请求。 */
  token: string;
  /** 要展示的诊断类型。 */
  kinds: readonly CheckKind[];
  /** 模型测试留空，项目测试须指定已接入仓库。 */
  repositoryId?: number;
  /** 配置尚未保存时禁止发起测试。 */
  enabled?: boolean;
}

/** 创建测试任务并轮询未完成的服务端状态。 */
export function ConnectionChecks({ token, kinds, repositoryId, enabled = true }: ConnectionChecksProps) {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["connection-checks"],
    queryFn: () => apiRequest<ConnectionCheck[]>(token, "/api/connection-checks"),
    refetchInterval: (current) => current.state.data?.some((check) => check.status === "queued" || check.status === "running") ? 2000 : false,
  });
  const create = useMutation({
    mutationFn: (kind: CheckKind) => apiRequest<{ id: number; status: string }>(token, "/api/connection-checks", {
      method: "POST",
      body: JSON.stringify({ kind, repository_id: repositoryId ?? null }),
    }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["connection-checks"] }),
  });

  return <div className="connection-checks">
    <div className="connection-checks-heading">连接测试 · 最近结果</div>
    {kinds.map((kind) => {
      const latest = query.data?.find((check) => check.kind === kind && check.repository_id === (repositoryId ?? null));
      const busy = latest?.status === "queued" || latest?.status === "running";
      return <div className="connection-check-row" key={kind}>
        <button className="button button-secondary" type="button" disabled={!enabled || busy || create.isPending} onClick={() => create.mutate(kind)}><Activity size={15} />测试 {labels[kind]}</button>
        {latest ? <span className="connection-check-result" aria-live="polite"><Status value={latest.status} /><span>{formatTime(latest.finished_at ?? latest.created_at)}</span>{latest.error && <span className="connection-check-error">{latest.error}</span>}</span> : <span className="connection-check-muted">尚未测试</span>}
      </div>;
    })}
    {query.error && <p className="form-error" role="alert">{query.error.message}</p>}
    {create.error && <p className="form-error" role="alert">{create.error.message}</p>}
  </div>;
}
