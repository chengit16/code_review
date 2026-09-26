/** @description GitLab 项目配置；飞书 Hook 和 Agent 模型由独立配置入口维护。 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Play, Plus, Settings2, Trash2, X } from "lucide-react";
import { useState } from "react";
import type { FormEvent } from "react";

import { apiRequest } from "../api/client";
import type { NotificationTarget, Repository, RepositoryInput, RepositoryUpdateInput } from "../api/types";
import { ConnectionChecks } from "../ui/ConnectionChecks";
import { Modal } from "../ui/Modal";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { SelectField } from "../ui/SelectField";
import { formatTime } from "../ui/format";

const initial: RepositoryInput = {
  name: "", gitlab_url: "", project_id: 0, remote_url: "", target_branch: "main",
  path_with_namespace: "", gitlab_token: "", enable_merge_requests: true,
  enable_default_branch_pushes: false, auth_kind: "secret",
};

/** 保存项目接入配置，密钥提交成功后立即从表单内存清除。 */
export function RepositoriesPage({ token }: { /** 内存中的管理口令。 */ token: string }) {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["repositories"], queryFn: () => apiRequest<Repository[]>(token, "/api/repositories") });
  const targets = useQuery({ queryKey: ["notification-targets"], queryFn: () => apiRequest<NotificationTarget[]>(token, "/api/notification-targets") });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<RepositoryInput>(initial);
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
    try {
      const clone = new URL(form.remote_url);
      mutation.mutate({ ...form, gitlab_url: clone.origin, auth_kind: "secret" });
    } catch {
      setFeedback("Clone URL 必须是完整的 HTTPS 地址");
    }
  }

  function field<K extends keyof RepositoryInput>(key: K, value: RepositoryInput[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function beginEdit(repo: Repository) {
    setEditing(repo);
    setEditForm({ name: repo.name, project_id: repo.project_id, feishu_target_id: repo.feishu_target_id, enable_merge_requests: Boolean(repo.enable_merge_requests), enable_default_branch_pushes: Boolean(repo.enable_default_branch_pushes) });
    update.reset();
  }

  function submitEdit(event: FormEvent) {
    event.preventDefault();
    if (!editing) return;
    const input = { ...editForm };
    if (!input.gitlab_token) delete input.gitlab_token;
    update.mutate({ id: editing.id, input });
  }

  function deleteRepository(repo: Repository) {
    if (!window.confirm(`确定删除项目配置“${repo.name}”？关联事件、评审和通知记录也会删除。`)) return;
    setFeedback("");
    remove.reset();
    remove.mutate(repo.id);
  }

  return <div className="page"><PageHeader title="项目配置" subtitle="GitLab 仓库连接与评审开关" actions={
    <button className="button button-primary" type="button" onClick={() => setOpen(true)}><Plus size={17} />添加仓库</button>
  } /><QueryState loading={query.isLoading} error={query.error} />{!query.isLoading && !query.error && <section className="section">
    <div className="table-scroll responsive-table"><table><thead><tr><th>仓库</th><th>项目 ID</th><th>目标分支</th><th>飞书配置</th><th>最近验证</th><th>接收</th><th aria-label="操作" /></tr></thead><tbody>
      {query.data?.map((repo) => <tr key={repo.id}><td data-label="仓库"><strong>{repo.name}</strong><small className="table-sub">{repo.path_with_namespace || repo.gitlab_url}</small></td><td data-label="项目 ID" className="mono">{repo.project_id}</td><td data-label="目标分支" className="mono">{repo.target_branch}</td><td data-label="飞书配置">{targets.data?.find((target) => target.id === repo.feishu_target_id)?.name ?? "未配置"}</td><td data-label="最近验证">{formatTime(repo.last_webhook_at)}</td><td data-label="接收"><label className="toggle-hit"><input className="repo-toggle" type="checkbox" checked={Boolean(repo.enabled)} disabled={toggle.isPending} onChange={(event) => toggle.mutate({ id: repo.id, enabled: event.target.checked })} aria-label={`${repo.name} 接收 webhook`} title={repo.enabled ? "暂停接收" : "恢复接收"} /></label></td><td data-label="操作"><div className="row-actions"><button className="icon-button" type="button" title="编辑仓库设置" aria-label={`编辑 ${repo.name}`} onClick={() => beginEdit(repo)}><Settings2 size={16} /></button><button className="icon-button icon-button-danger" type="button" title="删除项目配置" aria-label={`删除 ${repo.name}`} onClick={() => deleteRepository(repo)} disabled={remove.isPending}><Trash2 size={16} /></button></div></td></tr>)}
      {query.data?.length === 0 && <tr><td className="empty-row" colSpan={7}>尚未接入仓库</td></tr>}
    </tbody></table></div>
  </section>}
      {feedback && <p className="form-success" role="status">{feedback}</p>}
      {(toggle.error || remove.error) && <p className="form-error" role="alert">{(toggle.error || remove.error)?.message}</p>}
  {!!query.data?.length && <section className="section"><div className="section-head"><h2>按 MR 补触发</h2></div>
    <form className="inline-form" onSubmit={(event) => { event.preventDefault(); trigger.mutate(); }}>
      <SelectField label="仓库" name="repository" value={triggerRepository} onValueChange={setTriggerRepository} placeholder="选择仓库" required options={query.data.map((repo) => ({ value: String(repo.id), label: repo.name }))} />
      <label>MR IID<input type="number" min="1" value={mrIid} onChange={(event) => setMrIid(event.target.value)} required /></label>
      <button className="button button-secondary" type="submit" disabled={trigger.isPending}><Play size={16} />加入事件队列</button>
    </form>
    {trigger.error && <p className="form-error" role="alert">{trigger.error.message}</p>}
    {trigger.isSuccess && !trigger.error && <p className="form-success" role="status">已加入事件队列</p>}
  </section>}
  {open && <Modal titleId="add-repo-title" onClose={() => setOpen(false)}><div className="modal-heading"><h2 id="add-repo-title">添加 GitLab 仓库</h2><button className="icon-button" type="button" aria-label="关闭" title="关闭" onClick={() => setOpen(false)}><X size={19} /></button></div>
    <form onSubmit={submit} className="form-grid">
      <label>仓库名称<input value={form.name} onChange={(e) => field("name", e.target.value)} required /></label>
      <label>项目数字 ID<input type="number" min="1" value={form.project_id || ""} onChange={(e) => field("project_id", Number(e.target.value))} required /></label>
      <label>仓库路径<input placeholder="team/repo" value={form.path_with_namespace} onChange={(e) => field("path_with_namespace", e.target.value)} required /></label>
      <label>目标分支<input value={form.target_branch} onChange={(e) => field("target_branch", e.target.value)} required /></label>
      <label className="wide">Clone URL<input type="url" placeholder="https://gitlab.example.com/team/repo.git" value={form.remote_url} onChange={(e) => field("remote_url", e.target.value)} required /></label>
      <label>GitLab Token<input type="password" autoComplete="new-password" value={form.gitlab_token} onChange={(e) => field("gitlab_token", e.target.value)} required /></label>
      <SelectField label="飞书配置" value={form.feishu_target_id == null ? "none" : String(form.feishu_target_id)} onValueChange={(value) => field("feishu_target_id", value === "none" ? null : Number(value))} options={[{ value: "none", label: "暂不关联" }, ...(targets.data ?? []).map((target) => ({ value: String(target.id), label: target.name }))]} />
      <label className="checkbox-label"><input type="checkbox" checked={form.enable_merge_requests} onChange={(e) => field("enable_merge_requests", e.target.checked)} />Merge Request 审核</label>
      <label className="checkbox-label"><input type="checkbox" checked={form.enable_default_branch_pushes} onChange={(e) => field("enable_default_branch_pushes", e.target.checked)} />默认分支 Push 审核</label>
      {mutation.error && <p className="form-error wide" role="alert">{mutation.error.message}</p>}
      <div className="form-actions wide"><button type="button" className="button button-secondary" onClick={() => setOpen(false)}>取消</button><button type="submit" className="button button-primary" disabled={mutation.isPending}>保存仓库</button></div>
    </form>
  </Modal>}
  {editing && <Modal titleId="edit-repo-title" onClose={() => setEditing(null)}><div className="modal-heading"><h2 id="edit-repo-title">编辑 {editing.name}</h2><button className="icon-button" type="button" aria-label="关闭" title="关闭" onClick={() => setEditing(null)}><X size={19} /></button></div>
    <form onSubmit={submitEdit} className="form-grid">
      <label>仓库名称<input value={editForm.name ?? ""} onChange={(event) => setEditForm((current) => ({ ...current, name: event.target.value }))} required /></label>
      <label>项目数字 ID<input type="number" min="1" value={editForm.project_id || ""} onChange={(event) => setEditForm((current) => ({ ...current, project_id: Number(event.target.value) }))} required /></label>
      <label>新 GitLab Token<input type="password" autoComplete="new-password" value={editForm.gitlab_token ?? ""} onChange={(event) => setEditForm((current) => ({ ...current, gitlab_token: event.target.value }))} placeholder="留空则保留" /></label>
      <SelectField label="飞书配置" value={editForm.feishu_target_id == null ? "none" : String(editForm.feishu_target_id)} onValueChange={(value) => setEditForm((current) => ({ ...current, feishu_target_id: value === "none" ? null : Number(value) }))} options={[{ value: "none", label: "暂不关联" }, ...(targets.data ?? []).map((target) => ({ value: String(target.id), label: target.name }))]} />
      <label className="checkbox-label"><input type="checkbox" checked={editForm.enable_merge_requests ?? false} onChange={(event) => setEditForm((current) => ({ ...current, enable_merge_requests: event.target.checked }))} />Merge Request 审核</label>
      <label className="checkbox-label"><input type="checkbox" checked={editForm.enable_default_branch_pushes ?? false} onChange={(event) => setEditForm((current) => ({ ...current, enable_default_branch_pushes: event.target.checked }))} />默认分支 Push 审核</label>
      {update.error && <p className="form-error wide" role="alert">{update.error.message}</p>}
      <div className="form-actions wide"><button type="button" className="button button-secondary" onClick={() => setEditing(null)}>取消</button><button type="submit" className="button button-primary" disabled={update.isPending}>保存设置</button></div>
    </form>
    <ConnectionChecks token={token} kinds={["git", "gitlab"]} repositoryId={editing.id} />
  </Modal>}
  </div>;
}
