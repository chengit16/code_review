/** @description 同页维护 GitLab 项目、Webhook 与评审开关；飞书和模型配置独立。 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, Plus, RotateCcw, Settings2, Trash2, X } from "lucide-react";
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
import { WebhookTokenCell } from "./WebhookTokenCell";
import { ProjectReviewLimits } from "./ProjectReviewLimits";
import { GitLabPublicationSetting } from "./GitLabPublicationSetting";
import { PremergeSetting } from "./PremergeSetting";
import { confirmDiscard, UnsavedChangesGuard } from "../ui/UnsavedChangesGuard";
import type { DraftStatus } from "../ui/useConfigurationDraft";
import { RepositoryDiagnosis } from "./RepositoryDiagnosis";

interface Readiness { repository_id: number; status: "ready" | "needs_check" | "paused"; git: string; gitlab: string; config_revision_id: number | null }
type RepositoryEditSection = "connection" | "review" | "publication" | "diagnosis";

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
  const readiness = useQuery({ queryKey: ["repository-readiness"], queryFn: () => apiRequest<Readiness[]>(token, "/api/repository-readiness"), refetchInterval: 10000 });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<RepositoryInput>(initial);
  const [editing, setEditing] = useState<Repository | null>(null);
  const [editForm, setEditForm] = useState<RepositoryUpdateInput>({});
  const [editSection, setEditSection] = useState<RepositoryEditSection>("connection");
  const [editBaseline, setEditBaseline] = useState("");
  const [reviewStatus, setReviewStatus] = useState<DraftStatus>({ dirty: false, pending: false });
  const [premergeStatus, setPremergeStatus] = useState<DraftStatus>({ dirty: false, pending: false });
  const [publicationStatus, setPublicationStatus] = useState<DraftStatus>({ dirty: false, pending: false });
  const editDirty = Boolean(editing) && (JSON.stringify(editForm) !== editBaseline || reviewStatus.dirty || premergeStatus.dirty);
  const [feedback, setFeedback] = useState("");
  const [callbackCopied, setCallbackCopied] = useState(false);
  const [copyError, setCopyError] = useState("");
  const [tokenRevision, setTokenRevision] = useState(0);
  const callbackUrl = query.data?.[0]?.webhook_url;
  const mutation = useMutation({
    mutationFn: async (input: RepositoryInput) => {
      // 预检是只读操作；成功后仍由正式保存路径重新校验并原子写入。
      await apiRequest(token, "/api/repositories/preflight", { method: "POST", body: JSON.stringify(input) });
      return apiRequest<Repository>(token, "/api/repositories", { method: "POST", body: JSON.stringify(input) });
    },
    onSuccess: () => { setForm(initial); setOpen(false); void queryClient.invalidateQueries({ queryKey: ["repositories"] }); },
  });
  const update = useMutation({
    mutationFn: async ({ id, input }: { id: number; input: RepositoryUpdateInput }) => {
      if (!editing) throw new Error("项目不存在");
      await apiRequest(token, `/api/repositories/preflight?repository_id=${id}`, { method: "POST", body: JSON.stringify({
        name: input.name ?? editing.name, gitlab_url: input.gitlab_url ?? editing.gitlab_url,
        project_id: input.project_id ?? editing.project_id,
        remote_url: input.remote_url ?? editing.remote_url,
        path_with_namespace: input.path_with_namespace ?? editing.path_with_namespace,
        target_branch: input.target_branch ?? editing.target_branch,
        auth_kind: input.auth_kind ?? editing.auth_kind,
        webhook_token: input.webhook_token || undefined,
        gitlab_token: input.gitlab_token || undefined,
        feishu_target_id: input.feishu_target_id ?? undefined,
        enable_merge_requests: input.enable_merge_requests ?? Boolean(editing.enable_merge_requests),
        enable_default_branch_pushes: input.enable_default_branch_pushes ?? Boolean(editing.enable_default_branch_pushes),
      }) });
      return apiRequest<Repository>(token, `/api/repositories/${id}`, { method: "PATCH", body: JSON.stringify(input) });
    },
    onSuccess: (result, { input }) => {
      // 仅更新基础配置基线并清除已提交密钥，其他页签草稿继续保留。
      if (input.webhook_token || input.auth_kind !== editing?.auth_kind) setTokenRevision((current) => current + 1);
      const saved = { ...input }; delete saved.gitlab_token; delete saved.webhook_token;
      setEditing(result); setEditForm(saved); setEditBaseline(JSON.stringify(saved));
      void queryClient.invalidateQueries({ queryKey: ["repositories"] });
      void queryClient.invalidateQueries({ queryKey: ["repository-readiness"] });
    },
  });
  const rotate = useMutation({
    mutationFn: (id: number) => apiRequest<{ status: string }>(token, `/api/repositories/${id}/webhook-token/rotate`, { method: "POST" }),
    onSuccess: () => {
      setTokenRevision((current) => current + 1);
      void queryClient.invalidateQueries({ queryKey: ["repositories"] });
    },
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
      for (const queryKey of ["repositories", "jobs", "connection-checks"]) {
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
    setEditSection("connection");
    setReviewStatus({ dirty: false, pending: false }); setPremergeStatus({ dirty: false, pending: false });
    const next = {
      name: repo.name,
      gitlab_url: repo.gitlab_url,
      project_id: repo.project_id,
      remote_url: repo.remote_url,
      path_with_namespace: repo.path_with_namespace,
      target_branch: repo.target_branch,
      auth_kind: repo.auth_kind,
      feishu_target_id: repo.feishu_target_id,
      enable_merge_requests: Boolean(repo.enable_merge_requests),
      enable_default_branch_pushes: Boolean(repo.enable_default_branch_pushes),
    };
    setEditForm(next); setEditBaseline(JSON.stringify(next));
    update.reset();
    rotate.reset();
  }

  const editPending = update.isPending || reviewStatus.pending || premergeStatus.pending || publicationStatus.pending;
  function closeAdd() { if (!mutation.isPending && confirmDiscard(JSON.stringify(form) !== JSON.stringify(initial))) { setOpen(false); setForm(initial); } }
  function closeEditor() { if (!editPending && confirmDiscard(editDirty)) { setEditing(null); setEditForm({}); } }

  function submitEdit(event: FormEvent) {
    event.preventDefault();
    if (!editing) return;
    const input = { ...editForm };
    if (!input.gitlab_token) delete input.gitlab_token;
    if (!input.webhook_token) delete input.webhook_token;
    update.mutate({ id: editing.id, input });
  }

  function copyCallback(url: string) {
    setCopyError("");
    void navigator.clipboard.writeText(url)
      .then(() => setCallbackCopied(true))
      .catch(() => setCopyError("复制失败，请手动选择回调地址"));
  }

  function rotateToken(repo: Repository) {
    if (!window.confirm(`确定重新生成“${repo.name}”的 Webhook Secret？需同时更新 GitLab Webhook。`)) return;
    rotate.mutate(repo.id);
  }

  function deleteRepository(repo: Repository) {
    if (!window.confirm(`确定删除项目配置“${repo.name}”？关联事件、评审和通知记录也会删除。`)) return;
    setFeedback("");
    remove.reset();
    remove.mutate(repo.id);
  }

  return <div className="page"><UnsavedChangesGuard dirty={editDirty || (open && JSON.stringify(form) !== JSON.stringify(initial))} /><PageHeader title="项目配置" subtitle="GitLab 仓库、Webhook 与评审开关" actions={
    <button className="button button-primary" type="button" onClick={() => setOpen(true)}><Plus size={17} />添加仓库</button>
  } /><QueryState loading={query.isLoading} error={query.error} />{!query.isLoading && !query.error && <>
    {callbackUrl && <div className="webhook-callback"><span>GitLab 回调地址</span><input className="mono" aria-label="GitLab 回调地址" value={callbackUrl} readOnly onFocus={(event) => event.target.select()} /><button className="button button-secondary" type="button" onClick={() => copyCallback(callbackUrl)}>{callbackCopied ? <Check size={16} /> : <Copy size={16} />}{callbackCopied ? "已复制" : "复制地址"}</button></div>}
    {copyError && <p className="form-error" role="alert">{copyError}</p>}
    <section className="section"><div className="table-scroll responsive-table"><table><thead><tr><th>仓库</th><th>项目 ID</th><th>目标分支</th><th>接入状态</th><th>飞书配置</th><th>Webhook Token</th><th>接收</th><th aria-label="操作" /></tr></thead><tbody>
      {query.data?.map((repo) => <tr key={repo.id}><td data-label="仓库"><strong>{repo.name}</strong><small className="table-sub">{repo.path_with_namespace || repo.gitlab_url}</small></td><td data-label="项目 ID" className="mono">{repo.project_id}</td><td data-label="目标分支" className="mono">{repo.target_branch}</td><td data-label="接入状态">{({ ready: "已验证", needs_check: "待重新测试", paused: "已暂停" } as Record<string, string>)[readiness.data?.find((item) => item.repository_id === repo.id)?.status ?? "needs_check"]}</td><td data-label="飞书配置">{targets.data?.find((target) => target.id === repo.feishu_target_id)?.name ?? "未配置"}</td><td data-label="Webhook Token"><WebhookTokenCell key={`${repo.id}-${tokenRevision}`} token={token} repositoryId={repo.id} repositoryName={repo.name} /><small className="table-sub">最近验证 {formatTime(repo.last_webhook_at)}</small></td><td data-label="接收"><label className="toggle-hit"><input className="repo-toggle" type="checkbox" checked={Boolean(repo.enabled)} disabled={toggle.isPending} onChange={(event) => toggle.mutate({ id: repo.id, enabled: event.target.checked })} aria-label={`${repo.name} 接收 webhook`} title={repo.enabled ? "暂停接收" : "恢复接收"} /></label></td><td data-label="操作"><div className="row-actions"><button className="icon-button" type="button" title="编辑仓库设置" aria-label={`编辑 ${repo.name}`} onClick={() => beginEdit(repo)}><Settings2 size={16} /></button><button className="icon-button icon-button-danger" type="button" title="删除项目配置" aria-label={`删除 ${repo.name}`} onClick={() => deleteRepository(repo)} disabled={remove.isPending}><Trash2 size={16} /></button></div></td></tr>)}
      {query.data?.length === 0 && <tr><td className="empty-row" colSpan={8}>尚未接入仓库</td></tr>}
    </tbody></table></div>
  </section></>}
      {feedback && <p className="form-success" role="status">{feedback}</p>}
      {(toggle.error || remove.error) && <p className="form-error" role="alert">{(toggle.error || remove.error)?.message}</p>}
  {open && <Modal titleId="add-repo-title" onClose={closeAdd}><div className="modal-heading"><h2 id="add-repo-title">添加 GitLab 仓库</h2><button className="icon-button" type="button" aria-label="关闭" title="关闭" onClick={closeAdd}><X size={19} /></button></div>
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
      <div className="form-actions wide"><button type="button" className="button button-secondary" onClick={closeAdd}>取消</button><button type="submit" className="button button-primary" disabled={mutation.isPending}>保存仓库</button></div>
    </form>
  </Modal>}
  {editing && <Modal titleId="edit-repo-title" className="modal-wide repository-editor-modal" onClose={closeEditor}><div className="modal-heading"><h2 id="edit-repo-title">编辑 {editing.name}</h2><button className="icon-button" type="button" aria-label="关闭" title="关闭" onClick={closeEditor} disabled={editPending}><X size={19} /></button></div>
    <div className="repository-editor-tabs" role="tablist" aria-label="仓库设置">
      <button className={`repository-editor-tab${editSection === "connection" ? " is-active" : ""}`} type="button" role="tab" aria-selected={editSection === "connection"} onClick={() => setEditSection("connection")}>基础接入</button>
      <button className={`repository-editor-tab${editSection === "review" ? " is-active" : ""}`} type="button" role="tab" aria-selected={editSection === "review"} onClick={() => setEditSection("review")}>评审参数</button>
      <button className={`repository-editor-tab${editSection === "publication" ? " is-active" : ""}`} type="button" role="tab" aria-selected={editSection === "publication"} onClick={() => setEditSection("publication")}>发布审查</button>
      <button className={`repository-editor-tab${editSection === "diagnosis" ? " is-active" : ""}`} type="button" role="tab" aria-selected={editSection === "diagnosis"} onClick={() => setEditSection("diagnosis")}>接入诊断</button>
    </div>
    <div className="repository-editor-body">
    <form hidden={editSection !== "connection"} onSubmit={submitEdit} className="form-grid repository-main-form"><fieldset className="configuration-fields form-grid wide" disabled={update.isPending}>
      <label>仓库名称<input value={editForm.name ?? ""} onChange={(event) => setEditForm((current) => ({ ...current, name: event.target.value }))} required /></label>
      <label>项目数字 ID<input type="number" min="1" value={editForm.project_id || ""} onChange={(event) => setEditForm((current) => ({ ...current, project_id: Number(event.target.value) }))} required /></label>
      <label>GitLab 地址<input type="url" value={editForm.gitlab_url ?? ""} onChange={(event) => setEditForm((current) => ({ ...current, gitlab_url: event.target.value }))} required /></label>
      <label>目标分支<input value={editForm.target_branch ?? ""} onChange={(event) => setEditForm((current) => ({ ...current, target_branch: event.target.value }))} required /></label>
      <label className="wide">仓库路径<input value={editForm.path_with_namespace ?? ""} onChange={(event) => setEditForm((current) => ({ ...current, path_with_namespace: event.target.value }))} required /></label>
      <label className="wide">Clone URL<input value={editForm.remote_url ?? ""} onChange={(event) => setEditForm((current) => ({ ...current, remote_url: event.target.value }))} required /></label>
      <label>新 GitLab Token<input type="password" autoComplete="new-password" value={editForm.gitlab_token ?? ""} onChange={(event) => setEditForm((current) => ({ ...current, gitlab_token: event.target.value }))} placeholder="留空则保留" /></label>
      <SelectField label="飞书配置" value={editForm.feishu_target_id == null ? "none" : String(editForm.feishu_target_id)} onValueChange={(value) => setEditForm((current) => ({ ...current, feishu_target_id: value === "none" ? null : Number(value) }))} options={[{ value: "none", label: "暂不关联" }, ...(targets.data ?? []).map((target) => ({ value: String(target.id), label: target.name }))]} />
      <label className="checkbox-label"><input type="checkbox" checked={editForm.enable_merge_requests ?? false} onChange={(event) => setEditForm((current) => ({ ...current, enable_merge_requests: event.target.checked }))} />Merge Request 审核</label>
      <label className="checkbox-label"><input type="checkbox" checked={editForm.enable_default_branch_pushes ?? false} onChange={(event) => setEditForm((current) => ({ ...current, enable_default_branch_pushes: event.target.checked }))} />默认分支 Push 审核</label>
      <h3 className="form-section-title wide">GitLab Webhook</h3>
      <SelectField label="鉴权方式" value={editForm.auth_kind ?? editing.auth_kind} onValueChange={(value) => setEditForm((current) => ({ ...current, auth_kind: value === "signing" ? "signing" : "secret" }))} options={[{ value: "secret", label: "Secret token" }, { value: "signing", label: "Signing token" }]} />
      <label>新 Webhook Token<input type="password" autoComplete="new-password" value={editForm.webhook_token ?? ""} onChange={(event) => setEditForm((current) => ({ ...current, webhook_token: event.target.value }))} placeholder="留空则保留" required={editForm.auth_kind === "signing" && editing.auth_kind !== "signing"} /></label>
      <div className="webhook-editor wide"><div className="webhook-editor-callback"><span>回调地址</span><code>{editing.webhook_url}</code></div><div><span>当前 Token</span><WebhookTokenCell key={`${editing.id}-${tokenRevision}`} token={token} repositoryId={editing.id} repositoryName={editing.name} /></div><button className="button button-secondary" type="button" disabled={rotate.isPending || editing.auth_kind !== "secret"} onClick={() => rotateToken(editing)}><RotateCcw size={16} />重新生成 Secret</button></div>
      {rotate.error && <p className="form-error wide" role="alert">{rotate.error.message}</p>}
      {rotate.isSuccess && <p className="form-success wide" role="status">Secret 已更新，请同步修改 GitLab Webhook</p>}
      <div className="repository-form-checks wide"><ConnectionChecks token={token} kinds={["git", "gitlab"]} repositoryId={editing.id} /></div>
      {update.error && <p className="form-error wide" role="alert">{update.error.message}</p>}
      {JSON.stringify(editForm) !== editBaseline && <p className="unsaved-note wide" role="status">基础接入有未保存的更改；保存设置只保存当前页签。</p>}
      <div className="form-actions repository-form-actions wide"><button type="button" className="button button-secondary" onClick={closeEditor} disabled={editPending}>取消</button><button type="submit" className="button button-primary" disabled={update.isPending}>保存设置</button></div>
      {update.isSuccess && JSON.stringify(editForm) === editBaseline && <p className="form-success wide" role="status">基础接入配置已保存</p>}
    </fieldset></form>
    <div hidden={editSection !== "review"} className="repository-editor-panel"><ProjectReviewLimits token={token} repositoryId={editing.id} onStatusChange={setReviewStatus} /></div>
    <div hidden={editSection !== "publication"} className="repository-editor-panel repository-editor-stack"><GitLabPublicationSetting token={token} repositoryId={editing.id} onStatusChange={setPublicationStatus} /><PremergeSetting token={token} repositoryId={editing.id} onStatusChange={setPremergeStatus} /></div>
    <div hidden={editSection !== "diagnosis"} className="repository-editor-panel"><RepositoryDiagnosis token={token} repository={editing} targets={targets.data ?? []} /></div>
    </div>
  </Modal>}
  </div>;
}
