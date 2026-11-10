/**
 * @description 展示连接测试命令与 Worker 保存的最近结果。
 *
 * 测试请求只入队；状态以服务端记录为准，飞书测试会向目标群发送消息。
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { App, Button } from "antd";
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
  /** 指定保存的模型，测试不改变全局默认。 */
  modelProfileId?: number;
  /** 独立通知通道，无须先关联仓库。 */
  notificationTargetId?: number;
  /** 配置尚未保存时禁止发起测试。 */
  enabled?: boolean;
  /** 列表省略重复标题，保留测试状态和时间。 */
  compact?: boolean;
}

/** 创建测试任务并轮询未完成的服务端状态。 */
export function ConnectionChecks({ token, kinds, repositoryId, modelProfileId, notificationTargetId, enabled = true, compact = false }: ConnectionChecksProps) {
  const { modal } = App.useApp();
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["connection-checks"],
    queryFn: () => apiRequest<ConnectionCheck[]>(token, "/api/connection-checks"),
    refetchInterval: (current) => current.state.data?.some((check) => check.status === "queued" || check.status === "running") ? 2000 : false,
  });
  const create = useMutation({
    mutationFn: (kind: CheckKind) => apiRequest<{ id: number; status: string }>(token, "/api/connection-checks", {
      method: "POST",
      body: JSON.stringify({ kind, repository_id: repositoryId ?? null, model_profile_id: modelProfileId, notification_target_id: notificationTargetId }),
    }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["connection-checks"] }),
  });
  function requestCheck(kind: CheckKind) {
    if (kind === "model" || kind === "feishu") {
      modal.confirm({ title: kind === "model" ? "测试已保存的模型？" : "向真实群发送测试消息？", content: kind === "model" ? "将调用该模型服务，可能产生费用；不会改变全局默认模型。" : "将向此已保存的通知目标发送一条真实测试消息，不会触发评审。", okText: "确认测试", cancelText: "取消", onOk: () => create.mutateAsync(kind) });
    } else create.mutate(kind);
  }

  return <div className="connection-checks">
    {!compact && <div className="connection-checks-heading">连接测试 · 最近结果</div>}
    {kinds.map((kind) => {
      const latest = query.data?.find((check) => check.kind === kind && check.repository_id === (repositoryId ?? null) && (modelProfileId == null || check.model_profile_id === modelProfileId) && (notificationTargetId == null || check.notification_target_id === notificationTargetId));
      const busy = latest?.status === "queued" || latest?.status === "running";
      return <div className="connection-check-row" key={kind}>
        <Button icon={<Activity size={15} />} disabled={!enabled || busy || create.isPending} onClick={() => requestCheck(kind)}>测试 {labels[kind]}</Button>
        {latest ? <span className="connection-check-result" aria-live="polite"><Status value={latest.status} /><span>{latest.config_current ? "当前连接配置" : "历史配置，需重新测试"} · {formatTime(latest.finished_at ?? latest.created_at)}</span>{latest.error && <span className="connection-check-error">{latest.error}</span>}</span> : <span className="connection-check-muted">尚未测试</span>}
      </div>;
    })}
    {query.error && <p className="form-error" role="alert">{query.error.message}</p>}
    {create.error && <p className="form-error" role="alert">{create.error.message}</p>}
  </div>;
}
