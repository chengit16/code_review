/** @description 管理 OCR 模型配置，只有一个配置可处于启用状态。 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Plus, Settings2, Trash2, X } from "lucide-react";
import { useState } from "react";
import type { FormEvent } from "react";

import { apiRequest } from "../api/client";
import type { AuditEntry, ModelConfiguration } from "../api/types";
import { ConnectionChecks } from "../ui/ConnectionChecks";
import { Modal } from "../ui/Modal";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { SelectField } from "../ui/SelectField";
import { formatTime } from "../ui/format";

interface ModelForm {
  name: string;
  provider: string;
  model: string;
  base_url: string;
  api_key: string;
}

const initial: ModelForm = { name: "", provider: "dashscope", model: "", base_url: "", api_key: "" };

export function SettingsPage({ token }: { /** 内存中的管理口令。 */ token: string }) {
  const queryClient = useQueryClient();
  const profiles = useQuery({ queryKey: ["model-profiles"], queryFn: () => apiRequest<ModelConfiguration[]>(token, "/api/model-profiles") });
  const audit = useQuery({ queryKey: ["audit-logs"], queryFn: () => apiRequest<AuditEntry[]>(token, "/api/audit-logs"), refetchInterval: 10000 });
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<ModelConfiguration | null>(null);
  const [form, setForm] = useState<ModelForm>(initial);
  const [feedback, setFeedback] = useState("");
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["model-profiles"] });
  };
  const create = useMutation({
    mutationFn: (input: ModelForm) => apiRequest<ModelConfiguration>(token, "/api/model-profiles", { method: "POST", body: JSON.stringify(input) }),
    onSuccess: () => { setOpen(false); setForm(initial); setFeedback("模型已保存，请在列表中启用"); refresh(); },
  });
  const update = useMutation({
    mutationFn: ({ id, input }: { id: number; input: ModelForm }) => {
      const payload: Partial<ModelForm> = { ...input };
      if (!payload.api_key) delete payload.api_key;
      return apiRequest<ModelConfiguration>(token, `/api/model-profiles/${id}`, {
        method: "PATCH", body: JSON.stringify(payload),
      });
    },
    onSuccess: () => { setOpen(false); setEditing(null); setForm(initial); setFeedback("模型配置已更新"); refresh(); },
  });
  const activate = useMutation({
    mutationFn: (id: number) => apiRequest<ModelConfiguration>(token, `/api/model-profiles/${id}/activate`, { method: "POST" }),
    onSuccess: () => { setFeedback("模型已启用"); refresh(); },
  });
  const remove = useMutation({
    mutationFn: (id: number) => apiRequest<{ status: string }>(token, `/api/model-profiles/${id}`, { method: "DELETE" }),
    onSuccess: () => { setFeedback("模型配置已删除"); refresh(); },
  });
  function submit(event: FormEvent) {
    event.preventDefault();
    if (editing) update.mutate({ id: editing.id, input: form });
    else create.mutate(form);
  }
  function beginEdit(profile: ModelConfiguration) {
    setEditing(profile);
    setForm({ name: profile.name, provider: profile.provider, model: profile.model, base_url: profile.base_url, api_key: "" });
    create.reset();
    update.reset();
    setOpen(true);
  }
  const active = profiles.data?.find((profile) => profile.enabled);
  return <div className="page">
    <PageHeader title="Agent 模型" subtitle="Open Code Review 评审模型" actions={<button className="button button-primary" type="button" onClick={() => { setEditing(null); setForm(initial); create.reset(); update.reset(); setOpen(true); }}><Plus size={17} />新增模型</button>} />
    {feedback && <p className="form-success" role="status">{feedback}</p>}
    {(activate.error || remove.error) && <p className="form-error" role="alert">{(activate.error || remove.error)?.message}</p>}
    <QueryState loading={profiles.isLoading} error={profiles.error} />
    {!profiles.isLoading && !profiles.error && <section className="section">
      <div className="table-scroll responsive-table"><table><thead><tr><th>配置名称</th><th>Provider</th><th>模型标识</th><th>Base URL</th><th>状态</th><th aria-label="操作" /></tr></thead><tbody>
        {profiles.data?.map((profile) => <tr key={profile.id}><td data-label="配置名称"><strong>{profile.name}</strong></td><td data-label="Provider">{profile.provider}</td><td data-label="模型标识" className="mono">{profile.model}</td><td data-label="Base URL" className="mono">{profile.base_url || "内置端点"}</td><td data-label="状态">{profile.enabled ? "已启用" : "未启用"}</td><td data-label="操作"><div className="row-actions">
          {!profile.enabled && <button className="icon-button" type="button" title="启用模型" aria-label={`启用 ${profile.name}`} disabled={activate.isPending} onClick={() => activate.mutate(profile.id)}><Check size={16} /></button>}
          <button className="icon-button" type="button" title="编辑模型" aria-label={`编辑 ${profile.name}`} onClick={() => beginEdit(profile)}><Settings2 size={16} /></button>
          <button className="icon-button icon-button-danger" type="button" title="删除模型" aria-label={`删除 ${profile.name}`} disabled={Boolean(profile.enabled) || remove.isPending} onClick={() => { if (window.confirm(`确定删除模型“${profile.name}”？`)) remove.mutate(profile.id); }}><Trash2 size={16} /></button>
        </div></td></tr>)}
        {profiles.data?.length === 0 && <tr><td colSpan={6} className="empty-row">尚无模型配置</td></tr>}
      </tbody></table></div>
      <ConnectionChecks token={token} kinds={["model"]} enabled={Boolean(active)} />
    </section>}
    <section className="section"><div className="section-head"><h2>管理操作</h2><span>最近 100 条</span></div><QueryState loading={audit.isLoading} error={audit.error} /><div className="table-scroll"><table><thead><tr><th>时间</th><th>操作者</th><th>操作</th><th>对象</th><th>结果</th></tr></thead><tbody>{audit.data?.map((entry) => <tr key={entry.id}><td>{formatTime(entry.created_at)}</td><td>{entry.actor_name ?? "旧记录"}</td><td className="mono">{entry.action}</td><td>{entry.object_type}{entry.object_id !== null ? ` #${entry.object_id}` : ""}</td><td>{entry.outcome === "success" ? "成功" : entry.outcome}</td></tr>)}{audit.data?.length === 0 && <tr><td colSpan={5} className="empty-row">暂无管理操作</td></tr>}</tbody></table></div></section>
    {open && <Modal titleId="model-title" onClose={() => setOpen(false)}>
      <div className="modal-heading"><h2 id="model-title">{editing ? `编辑 ${editing.name}` : "新增模型"}</h2><button className="icon-button" type="button" title="关闭" aria-label="关闭" onClick={() => setOpen(false)}><X size={19} /></button></div>
      <form className="settings-form hook-form" onSubmit={submit}>
        <label>配置名称<input value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} required /></label>
        <SelectField label="Provider" value={form.provider} onValueChange={(value) => setForm((current) => ({ ...current, provider: value }))} options={[{ value: "dashscope", label: "DashScope" }, { value: "openai", label: "OpenAI" }, { value: "anthropic", label: "Anthropic" }]} />
        <label>模型标识<input value={form.model} onChange={(event) => setForm((current) => ({ ...current, model: event.target.value }))} required /></label>
        <label>Base URL<input type="url" value={form.base_url} onChange={(event) => setForm((current) => ({ ...current, base_url: event.target.value }))} placeholder="内置 Provider 可留空" /></label>
        <label>API Key<input type="password" autoComplete="new-password" value={form.api_key} onChange={(event) => setForm((current) => ({ ...current, api_key: event.target.value }))} placeholder={editing ? "留空则保留现有密钥" : ""} required={!editing} /></label>
        {(create.error || update.error) && <p className="form-error" role="alert">{(create.error || update.error)?.message}</p>}
        <div className="form-actions"><button className="button button-secondary" type="button" onClick={() => setOpen(false)}>取消</button><button className="button button-primary" type="submit" disabled={create.isPending || update.isPending}>保存模型</button></div>
      </form>
    </Modal>}
  </div>;
}
