/** @description 统一管理 GitLab Webhook 地址、Secret 与订阅事件。 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, RotateCcw } from "lucide-react";
import { useState } from "react";

import { apiRequest } from "../api/client";
import type { Repository } from "../api/types";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { formatTime } from "../ui/format";
import { WebhookTokenCell } from "./WebhookTokenCell";

export function WebhooksPage({ token }: { /** 内存中的管理口令。 */ token: string }) {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["repositories"], queryFn: () => apiRequest<Repository[]>(token, "/api/repositories") });
  const [copied, setCopied] = useState<number | null>(null);
  const [revision, setRevision] = useState(0);
  const rotate = useMutation({
    mutationFn: (id: number) => apiRequest<{ status: string }>(token, `/api/repositories/${id}/webhook-token/rotate`, { method: "POST" }),
    onSuccess: () => { setRevision((current) => current + 1); void queryClient.invalidateQueries({ queryKey: ["repositories"] }); },
  });
  return <div className="page">
    <PageHeader title="GitLab Webhook" subtitle="统一回调地址与项目专属 Secret" />
    <QueryState loading={query.isLoading} error={query.error} />
    {rotate.error && <p className="form-error" role="alert">{rotate.error.message}</p>}
    {!query.isLoading && !query.error && <section className="section"><div className="table-scroll responsive-table"><table><thead><tr><th>仓库</th><th>回调地址</th><th>Webhook Secret</th><th>事件</th><th>最近验证</th><th aria-label="操作" /></tr></thead><tbody>
      {query.data?.map((repo) => <tr key={repo.id}><td data-label="仓库"><strong>{repo.name}</strong><small className="table-sub">{repo.path_with_namespace || repo.gitlab_url}</small></td><td data-label="回调地址"><button className="copy-command" type="button" title="复制回调地址" onClick={() => { void navigator.clipboard.writeText(repo.webhook_url).then(() => setCopied(repo.id)); }}><span>{copied === repo.id ? "已复制" : "复制地址"}</span>{copied === repo.id ? <Check size={15} /> : <Copy size={15} />}</button></td><td data-label="Webhook Secret"><WebhookTokenCell key={`${repo.id}-${revision}`} token={token} repositoryId={repo.id} repositoryName={repo.name} /></td><td data-label="事件">{[repo.enable_merge_requests && "Merge request", repo.enable_default_branch_pushes && "Push"].filter(Boolean).join("、") || "未启用"}</td><td data-label="最近验证">{formatTime(repo.last_webhook_at)}</td><td data-label="操作"><button className="icon-button" type="button" title="重新生成 Webhook Secret" aria-label={`重新生成 ${repo.name} 的 Webhook Secret`} disabled={rotate.isPending || repo.auth_kind !== "secret"} onClick={() => { if (window.confirm(`确定重新生成“${repo.name}”的 Webhook Secret？需同时更新 GitLab Webhook。`)) rotate.mutate(repo.id); }}><RotateCcw size={16} /></button></td></tr>)}
      {query.data?.length === 0 && <tr><td colSpan={6} className="empty-row">请先创建仓库配置</td></tr>}
    </tbody></table></div></section>}
  </div>;
}
