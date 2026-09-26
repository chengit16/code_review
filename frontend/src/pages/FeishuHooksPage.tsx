/**
 * @description 按项目维护飞书机器人 Hook
 *
 * 只负责选择项目、录入和测试飞书地址；项目身份与 Agent 模型分别由其他配置入口维护。
 * Hook 密钥只在表单内存中存在，服务端只返回是否已配置。
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageSquare, Save, Settings2, Trash2, X } from "lucide-react";
import { useState } from "react";
import type { FormEvent } from "react";

import { apiRequest } from "../api/client";
import type { Repository, RepositoryUpdateInput } from "../api/types";
import { ConnectionChecks } from "../ui/ConnectionChecks";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { Status } from "../ui/Status";
import { formatTime } from "../ui/format";

/** 维护每个项目的飞书通知 Hook，凭据不会进入查询缓存或页面文本。 */
export function FeishuHooksPage({ token }: { /** 内存中的管理口令。 */ token: string }) {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["repositories"],
    queryFn: () => apiRequest<Repository[]>(token, "/api/repositories"),
  });
  const [editing, setEditing] = useState<Repository | null>(null);
  const [webhook, setWebhook] = useState("");
  const [feedback, setFeedback] = useState("");
  const update = useMutation({
    mutationFn: ({ id, input }: { id: number; input: RepositoryUpdateInput }) =>
      apiRequest<Repository>(token, `/api/repositories/${id}`, {
        method: "PATCH",
        body: JSON.stringify(input),
      }),
    onSuccess: (updated) => {
      setEditing(null);
      setWebhook("");
      setFeedback("飞书 Hook 已保存");
      queryClient.setQueryData<Repository[]>(["repositories"], (current) =>
        current?.map((repository) => repository.id === updated.id ? updated : repository),
      );
      void queryClient.invalidateQueries({ queryKey: ["repositories"] });
      void queryClient.invalidateQueries({ queryKey: ["connection-checks"] });
    },
  });
  const remove = useMutation({
    mutationFn: (id: number) => apiRequest<Repository>(token, `/api/repositories/${id}/feishu-hook`, { method: "DELETE" }),
    onSuccess: (updated) => {
      setFeedback("飞书 Hook 已删除");
      queryClient.setQueryData<Repository[]>(["repositories"], (current) =>
        current?.map((repository) => repository.id === updated.id ? updated : repository),
      );
      void queryClient.invalidateQueries({ queryKey: ["repositories"] });
      void queryClient.invalidateQueries({ queryKey: ["connection-checks"] });
    },
  });

  function beginEdit(repository: Repository) {
    setEditing(repository);
    setWebhook("");
    update.reset();
    remove.reset();
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!editing || !webhook) return;
    update.mutate({ id: editing.id, input: { feishu_webhook: webhook } });
  }

  function deleteHook(repository: Repository) {
    if (!window.confirm(`确定删除项目“${repository.name}”的飞书 Hook？项目和评审历史会保留。`)) return;
    setFeedback("");
    remove.reset();
    remove.mutate(repository.id);
  }

  return (
    <div className="page">
      <PageHeader title="飞书 Hook" subtitle="按项目配置通知目标；地址只写入，不回显" />
      {feedback && <p className="form-success" role="status">{feedback}</p>}
      {remove.error && <p className="form-error" role="alert">{remove.error.message}</p>}
      <QueryState loading={query.isLoading} error={query.error} />
      {!query.isLoading && !query.error && (
        <section className="section">
          <div className="config-callout">
            <MessageSquare size={19} aria-hidden="true" />
            <div>
              <strong>通知配置独立于项目参数</strong>
              <p>项目可以先接入 GitLab，稍后再为每个项目配置飞书机器人 Hook。</p>
            </div>
          </div>
          <div className="hook-list">
            {query.data?.map((repository) => (
              <article className="hook-row" key={repository.id}>
                <div className="hook-project">
                  <strong>{repository.name}</strong>
                  <span>{repository.gitlab_url} · {repository.target_branch}</span>
                </div>
                <Status value={repository.has_feishu_webhook ? "configured" : "unconfigured"} />
                <span className="hook-last">最近 GitLab 投递：{formatTime(repository.last_webhook_at)}</span>
                <div className="row-actions">
                  <button className="icon-button" type="button" title={repository.has_feishu_webhook ? "轮换飞书 Hook" : "添加飞书 Hook"} aria-label={`${repository.has_feishu_webhook ? "轮换" : "添加"} ${repository.name} 的飞书 Hook`} onClick={() => beginEdit(repository)}>
                    <Settings2 size={16} />
                  </button>
                  <button className="icon-button icon-button-danger" type="button" title="删除飞书 Hook" aria-label={`删除 ${repository.name} 的飞书 Hook`} onClick={() => deleteHook(repository)} disabled={!repository.has_feishu_webhook || remove.isPending}>
                    <Trash2 size={16} />
                  </button>
                </div>
              </article>
            ))}
            {query.data?.length === 0 && <p className="empty-inline">请先在项目配置中接入 GitLab 项目。</p>}
          </div>
        </section>
      )}
      {editing && (
        <div className="modal-backdrop" role="presentation">
          <div className="modal" role="dialog" aria-modal="true" aria-labelledby="feishu-hook-title">
            <div className="modal-heading">
              <h2 id="feishu-hook-title">配置 {editing.name} 的飞书 Hook</h2>
              <button className="icon-button" type="button" aria-label="关闭" title="关闭" onClick={() => setEditing(null)}>
                <X size={19} />
              </button>
            </div>
            <form className="settings-form hook-form" onSubmit={submit}>
              <label>
                飞书机器人 Webhook
                <input
                  type="password"
                  autoComplete="new-password"
                  value={webhook}
                  onChange={(event) => setWebhook(event.target.value)}
                  placeholder={editing.has_feishu_webhook ? "已配置，输入新地址可轮换" : "粘贴 open.feishu.cn Hook 地址"}
                  required
                />
              </label>
              {update.error && <p className="form-error" role="alert">{update.error.message}</p>}
              <div className="form-actions">
                <button type="button" className="button button-secondary" onClick={() => setEditing(null)}>取消</button>
                <button type="submit" className="button button-primary" disabled={update.isPending}><Save size={16} />保存 Hook</button>
              </div>
            </form>
            <ConnectionChecks token={token} kinds={["feishu"]} repositoryId={editing.id} enabled={editing.has_feishu_webhook} />
          </div>
        </div>
      )}
    </div>
  );
}
