/** @description GitLab 项目配置；飞书 Hook 和 Agent 模型由独立配置入口维护。 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, Play, Plus, Settings2, Trash2, X } from "lucide-react";
import { useState } from "react";
import type { FormEvent } from "react";

import { apiRequest } from "../api/client";
import type { Repository, RepositoryInput, RepositoryUpdateInput } from "../api/types";
import { ConnectionChecks } from "../ui/ConnectionChecks";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { Status } from "../ui/Status";
import { formatTime } from "../ui/format";

const initial: RepositoryInput = {
  name: "", gitlab_url: "", project_id: 0, remote_url: "", target_branch: "main",
  auth_kind: "signing", webhook_token: "",
};

/** 保存项目接入配置，密钥提交成功后立即从表单内存清除。 */
export function RepositoriesPage({ token }: { /** 内存中的管理口令。 */ token: string }) {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["repositories"], queryFn: () => apiRequest<Repository[]>(token, "/api/repositories") });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<RepositoryInput>(initial);
  const [copied, setCopied] = useState<number | null>(null);
  const [editing, setEditing] = useState<Repository | null>(null);
  const [editForm, setEditForm] = useState<RepositoryUpdateInput>({});
  const [triggerRepository, setTriggerRepository] = useState("");
  const [mrIid, setMrIid] = useState("");
  const [feedback, setFeedback] = useState("");
  const mutation = useMutation({
    mutationFn: (input: RepositoryInput) => apiRequest<Repository>(token, "/api/repositories", { method: "POST", body: JSON.stringify(input) }),
    onSuccess: () => { setForm(initial); setOpen(false); void queryClient.invalidateQueries({ queryKey: ["repositories"] }); },
  });
  const trigger = useMutation({
    mutationFn: () => apiRequest<{ status: string }>(token, `/api/repositories/${triggerRepository}/mrs/${mrIid}/enqueue`, { method: "POST" }),
    onSuccess: () => { setMrIid(""); void queryClient.invalidateQueries({ queryKey: ["events"] }); },
  });
  const update = useMutation({
    mutationFn: ({ id, input }: { id: number; input: RepositoryUpdateInput }) => apiRequest<Repository>(token, `/api/repositories/${id}`, { method: "PATCH", body: JSON.stringify(input) }),
    onSuccess: () => { setEditing(null); setEditForm({}); void queryClient.invalidateQueries({ queryKey: ["repositories"] }); },
  });
  const toggle = useMutation({
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) => apiRequest<Repository>(token, `/api/repositories/${id}`, { method: "PATCH", body: JSON.stringify({ enabled }) }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["repositories"] }),
  });
  const remove = useMutation({
    mutationFn: (id: number) => apiRequest<{ status: string }>(token, `/api/repositories/${id}`, { method: "DELETE" }),
    onSuccess: (_result, repositoryId) => {
      setFeedback("项目配置及关联记录已删除");
      queryClient.setQueryData<Repository[]>(["repositories"], (current) =>
        current?.filter((repository) => repository.id !== repositoryId),
      );
      for (const queryKey of ["repositories", "events", "jobs", "connection-checks"]) {
        void queryClient.invalidateQueries({ queryKey: [queryKey] });
      }
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate(form);
  }

  function field<K extends keyof RepositoryInput>(key: K, value: RepositoryInput[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function beginEdit(repo: Repository) {
    setEditing(repo);
    setEditForm({ name: repo.name, auth_kind: repo.auth_kind, webhook_id: repo.webhook_id });
    update.reset();
  }

  function submitEdit(event: FormEvent) {
    event.preventDefault();
    if (!editing) return;
    const input = { ...editForm };
    if (!input.webhook_token) delete input.webhook_token;
    delete input.feishu_webhook;
    update.mutate({ id: editing.id, input });
  }

  function deleteRepository(repo: Repository) {
    if (!window.confirm(`确定删除项目配置“${repo.name}”？关联事件、评审和通知记录也会删除。`)) return;
    setFeedback("");
    remove.reset();
    remove.mutate(repo.id);
  }

  return <div className="page"><PageHeader title="项目配置" subtitle="GitLab 项目身份、目标分支与入站回调" actions={
    <button className="button button-primary" type="button" onClick={() => setOpen(true)}><Plus size={17} />添加仓库</button>
  } /><QueryState loading={query.isLoading} error={query.error} />{!query.isLoading && !query.error && <section className="section">
    <div className="table-scroll"><table><thead><tr><th>仓库</th><th>项目 ID</th><th>目标分支</th><th>回调</th><th>鉴权</th><th>最近验证</th><th>接收</th><th aria-label="操作" /></tr></thead><tbody>
      {query.data?.map((repo) => <tr key={repo.id}><td><strong>{repo.name}</strong><small className="table-sub">{repo.gitlab_url}</small></td><td className="mono">{repo.project_id}</td><td className="mono">{repo.target_branch}</td><td><button className="copy-command" type="button" title="复制回调地址" onClick={() => { void navigator.clipboard.writeText(repo.webhook_url).then(() => setCopied(repo.id)); }}><span>{copied === repo.id ? "已复制" : "复制地址"}</span>{copied === repo.id ? <Check size={15} /> : <Copy size={15} />}</button></td><td><Status value={repo.auth_kind === "signing" ? "签名验证" : "令牌验证"} /></td><td>{formatTime(repo.last_webhook_at)}</td><td><input className="repo-toggle" type="checkbox" checked={Boolean(repo.enabled)} disabled={toggle.isPending} onChange={(event) => toggle.mutate({ id: repo.id, enabled: event.target.checked })} aria-label={`${repo.name} 接收 webhook`} title={repo.enabled ? "暂停接收" : "恢复接收"} /></td><td><div className="row-actions"><button className="icon-button" type="button" title="编辑仓库设置" aria-label={`编辑 ${repo.name}`} onClick={() => beginEdit(repo)}><Settings2 size={16} /></button><button className="icon-button icon-button-danger" type="button" title="删除项目配置" aria-label={`删除 ${repo.name}`} onClick={() => deleteRepository(repo)} disabled={remove.isPending}><Trash2 size={16} /></button></div></td></tr>)}
      {query.data?.length === 0 && <tr><td className="empty-row" colSpan={8}>尚未接入仓库</td></tr>}
    </tbody></table></div>
  </section>}
      {feedback && <p className="form-success" role="status">{feedback}</p>}
      {(toggle.error || remove.error) && <p className="form-error" role="alert">{(toggle.error || remove.error)?.message}</p>}
  {!!query.data?.length && <section className="section"><div className="section-head"><h2>按 MR 补触发</h2></div>
    <form className="inline-form" onSubmit={(event) => { event.preventDefault(); trigger.mutate(); }}>
      <label>仓库<select value={triggerRepository} onChange={(event) => setTriggerRepository(event.target.value)} required><option value="">选择仓库</option>{query.data.map((repo) => <option key={repo.id} value={repo.id}>{repo.name}</option>)}</select></label>
      <label>MR IID<input type="number" min="1" value={mrIid} onChange={(event) => setMrIid(event.target.value)} required /></label>
      <button className="button button-secondary" type="submit" disabled={trigger.isPending}><Play size={16} />加入事件队列</button>
    </form>
    {trigger.error && <p className="form-error" role="alert">{trigger.error.message}</p>}
    {trigger.isSuccess && !trigger.error && <p className="form-success" role="status">已加入事件队列</p>}
  </section>}
  {open && <div className="modal-backdrop" role="presentation"><div className="modal" role="dialog" aria-modal="true" aria-labelledby="add-repo-title"><div className="modal-heading"><h2 id="add-repo-title">添加 GitLab 仓库</h2><button className="icon-button" type="button" aria-label="关闭" title="关闭" onClick={() => setOpen(false)}><X size={19} /></button></div>
    <form onSubmit={submit} className="form-grid">
      <label>仓库名称<input value={form.name} onChange={(e) => field("name", e.target.value)} required /></label>
      <label>GitLab 地址<input type="url" placeholder="https://gitlab.example.com" value={form.gitlab_url} onChange={(e) => field("gitlab_url", e.target.value)} required /></label>
      <label>项目数字 ID<input type="number" min="1" value={form.project_id || ""} onChange={(e) => field("project_id", Number(e.target.value))} required /></label>
      <label>目标分支<input value={form.target_branch} onChange={(e) => field("target_branch", e.target.value)} required /></label>
      <label className="wide">Git 只读地址<input placeholder="git@gitlab.example.com:team/repo.git" value={form.remote_url} onChange={(e) => field("remote_url", e.target.value)} required /></label>
      <label>Webhook 鉴权<select value={form.auth_kind} onChange={(e) => field("auth_kind", e.target.value as RepositoryInput["auth_kind"])}><option value="signing">Signing token</option><option value="secret">Secret token</option></select></label>
      <label>{form.auth_kind === "signing" ? "Signing token" : "Secret token"}<input type="password" autoComplete="off" value={form.webhook_token} onChange={(e) => field("webhook_token", e.target.value)} required /></label>
      {mutation.error && <p className="form-error wide" role="alert">{mutation.error.message}</p>}
      <div className="form-actions wide"><button type="button" className="button button-secondary" onClick={() => setOpen(false)}>取消</button><button type="submit" className="button button-primary" disabled={mutation.isPending}>保存仓库</button></div>
    </form>
  </div></div>}
  {editing && <div className="modal-backdrop" role="presentation"><div className="modal" role="dialog" aria-modal="true" aria-labelledby="edit-repo-title"><div className="modal-heading"><h2 id="edit-repo-title">编辑 {editing.name}</h2><button className="icon-button" type="button" aria-label="关闭" title="关闭" onClick={() => setEditing(null)}><X size={19} /></button></div>
    <form onSubmit={submitEdit} className="form-grid">
      <label>仓库名称<input value={editForm.name ?? ""} onChange={(event) => setEditForm((current) => ({ ...current, name: event.target.value }))} required /></label>
      <label>GitLab Webhook ID<input value={editForm.webhook_id ?? ""} onChange={(event) => setEditForm((current) => ({ ...current, webhook_id: event.target.value || null }))} /></label>
      <label>Webhook 鉴权<select value={editForm.auth_kind ?? editing.auth_kind} onChange={(event) => setEditForm((current) => ({ ...current, auth_kind: event.target.value as Repository["auth_kind"] }))}><option value="signing">Signing token</option><option value="secret">Secret token</option></select></label>
      <label>新 Webhook token<input type="password" autoComplete="new-password" value={editForm.webhook_token ?? ""} onChange={(event) => setEditForm((current) => ({ ...current, webhook_token: event.target.value }))} required={editForm.auth_kind !== editing.auth_kind} /></label>
      {update.error && <p className="form-error wide" role="alert">{update.error.message}</p>}
      <div className="form-actions wide"><button type="button" className="button button-secondary" onClick={() => setEditing(null)}>取消</button><button type="submit" className="button button-primary" disabled={update.isPending}>保存设置</button></div>
    </form>
    <ConnectionChecks token={token} kinds={["git", "gitlab"]} repositoryId={editing.id} />
  </div></div>}
  </div>;
}
