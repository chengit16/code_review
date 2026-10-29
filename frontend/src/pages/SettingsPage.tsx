/** @description 管理 OCR 模型配置，只有一个配置可处于启用状态。 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Plus, Settings2, Trash2, X } from "lucide-react";
import { useState } from "react";
import type { FormEvent } from "react";

import { apiRequest } from "../api/client";
import type { ModelConfiguration } from "../api/types";
import { ConnectionChecks } from "../ui/ConnectionChecks";
import { Modal } from "../ui/Modal";
import { PageHeader } from "../ui/PageHeader";
import { confirmDiscard, UnsavedChangesGuard } from "../ui/UnsavedChangesGuard";
import { QueryState } from "../ui/QueryState";
import { SelectField } from "../ui/SelectField";

interface ModelForm {
  name: string;
  provider: string;
  model: string;
  base_url: string;
  api_key: string;
  price_currency: "CNY" | "USD";
  input_price_per_million: string;
  output_price_per_million: string;
}

const initial: ModelForm = { name: "", provider: "dashscope", model: "", base_url: "", api_key: "", price_currency: "CNY", input_price_per_million: "", output_price_per_million: "" };

/** 维护模型配置与连接测试；密钥仅保留在当前编辑表单。 */
export function SettingsPage({ token, embedded = false }: {
  /** 内存中的管理口令。 */ token: string;
  /** 嵌入系统设置时省略独立页面留白；服务端仍负责授权。 */ embedded?: boolean;
}) {
  const queryClient = useQueryClient();
  const profiles = useQuery({ queryKey: ["model-profiles"], queryFn: () => apiRequest<ModelConfiguration[]>(token, "/api/model-profiles") });
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<ModelConfiguration | null>(null);
  const [form, setForm] = useState<ModelForm>(initial);
  const [baseline, setBaseline] = useState<ModelForm>(initial);
  const dirty = open && JSON.stringify(form) !== JSON.stringify(baseline);
  const closeEditor = () => { if (!create.isPending && !update.isPending && confirmDiscard(dirty)) { setOpen(false); setForm(initial); } };
  const [feedback, setFeedback] = useState("");
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["model-profiles"] });
  };
  const create = useMutation({
    mutationFn: (input: ModelForm) => apiRequest<ModelConfiguration>(token, "/api/model-profiles", { method: "POST", body: JSON.stringify({ ...input, input_price_per_million: input.input_price_per_million || null, output_price_per_million: input.output_price_per_million || null }) }),
    onSuccess: () => { setOpen(false); setForm(initial); setFeedback("模型已保存，请在列表中启用"); refresh(); },
  });
  const update = useMutation({
    mutationFn: ({ id, input }: { id: number; input: ModelForm }) => {
      const payload: Partial<ModelForm> = { ...input };
      if (!payload.api_key) delete payload.api_key;
      return apiRequest<ModelConfiguration>(token, `/api/model-profiles/${id}`, {
        method: "PATCH", body: JSON.stringify({ ...payload, input_price_per_million: input.input_price_per_million || null, output_price_per_million: input.output_price_per_million || null }),
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
    const draft: ModelForm = { name: profile.name, provider: profile.provider, model: profile.model, base_url: profile.base_url, api_key: "", price_currency: profile.price_currency, input_price_per_million: profile.input_price_per_million ?? "", output_price_per_million: profile.output_price_per_million ?? "" };
    setBaseline(draft);
    setForm(draft);
    create.reset();
    update.reset();
    setOpen(true);
  }
  const active = profiles.data?.find((profile) => profile.enabled);
  return <div className={embedded ? "settings-content" : "page"}>
    <PageHeader headingLevel={embedded ? 2 : 1} title="Agent 模型" subtitle="Open Code Review 评审模型" actions={<button className="button button-primary" type="button" onClick={() => { setEditing(null); setBaseline(initial); setForm(initial); create.reset(); update.reset(); setOpen(true); }}><Plus size={17} />新增模型</button>} />
    <UnsavedChangesGuard dirty={dirty} />
    {feedback && <p className="form-success" role="status">{feedback}</p>}
    {(activate.error || remove.error) && <p className="form-error" role="alert">{(activate.error || remove.error)?.message}</p>}
    <QueryState loading={profiles.isLoading} error={profiles.error} />
    {!profiles.isLoading && !profiles.error && <section className="section">
      <div className="table-scroll responsive-table"><table><thead><tr><th>配置名称</th><th>Provider</th><th>模型标识</th><th>Base URL</th><th>单价 / 百万 Token</th><th>状态</th><th aria-label="操作" /></tr></thead><tbody>
        {profiles.data?.map((profile) => <tr key={profile.id}><td data-label="配置名称"><strong>{profile.name}</strong></td><td data-label="Provider">{profile.provider === "dashscope" ? "百练 / DashScope" : profile.provider}</td><td data-label="模型标识" className="mono">{profile.model}</td><td data-label="Base URL" className="mono">{profile.base_url || "内置端点"}</td><td data-label="单价 / 百万 Token">{profile.input_price_per_million != null || profile.output_price_per_million != null ? `${profile.price_currency === "CNY" ? "¥" : "$"}${profile.input_price_per_million ?? "未配置"} 输入 / ${profile.output_price_per_million ?? "未配置"} 输出` : "未配置"}</td><td data-label="状态">{profile.enabled ? "已启用" : "未启用"}</td><td data-label="操作"><div className="row-actions">
          {!profile.enabled && <button className="icon-button" type="button" title="启用模型" aria-label={`启用 ${profile.name}`} disabled={activate.isPending} onClick={() => activate.mutate(profile.id)}><Check size={16} /></button>}
          <button className="icon-button" type="button" title="编辑模型" aria-label={`编辑 ${profile.name}`} onClick={() => beginEdit(profile)}><Settings2 size={16} /></button>
          <button className="icon-button icon-button-danger" type="button" title="删除模型" aria-label={`删除 ${profile.name}`} disabled={Boolean(profile.enabled) || remove.isPending} onClick={() => { if (window.confirm(`确定删除模型“${profile.name}”？`)) remove.mutate(profile.id); }}><Trash2 size={16} /></button>
        </div></td></tr>)}
        {profiles.data?.length === 0 && <tr><td colSpan={7} className="empty-row">尚无模型配置</td></tr>}
      </tbody></table></div>
      <ConnectionChecks token={token} kinds={["model"]} enabled={Boolean(active)} />
    </section>}
    {open && <Modal titleId="model-title" onClose={closeEditor}>
      <div className="modal-heading"><h2 id="model-title">{editing ? `编辑 ${editing.name}` : "新增模型"}</h2><button className="icon-button" type="button" title="关闭" aria-label="关闭" onClick={closeEditor}><X size={19} /></button></div>
      <form className="settings-form hook-form" noValidate onSubmit={submit}><fieldset className="form-fields" disabled={create.isPending || update.isPending}>
        <p className="form-note">可随时保存，字段留空或尚未填写完整也不影响保存。保存不代表模型可用，请另行测试模型。</p>
        <label>配置名称<input value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} /></label>
        <SelectField label="Provider" value={form.provider} onValueChange={(value) => setForm((current) => ({ ...current, provider: value }))} options={[{ value: "dashscope", label: "百练 / DashScope" }, { value: "openai", label: "OpenAI" }, { value: "anthropic", label: "Anthropic" }]} />
        {form.provider === "dashscope" && <p className="form-note">百练模型使用 DashScope API Key 和模型标识；Base URL 留空即可使用内置端点。</p>}
        <label>模型标识<input value={form.model} onChange={(event) => setForm((current) => ({ ...current, model: event.target.value }))} /></label>
        <label>Base URL<input value={form.base_url} onChange={(event) => setForm((current) => ({ ...current, base_url: event.target.value }))} placeholder="内置 Provider 可留空" /></label>
        <label>API Key<input type="password" autoComplete="new-password" value={form.api_key} onChange={(event) => setForm((current) => ({ ...current, api_key: event.target.value }))} placeholder={editing ? "留空则保留现有密钥" : "可留空，后续补充"} /></label>
        <SelectField label="计费币种" value={form.price_currency} onValueChange={(value) => setForm((current) => ({ ...current, price_currency: value === "USD" ? "USD" : "CNY" }))} options={[{ value: "CNY", label: "人民币 CNY" }, { value: "USD", label: "美元 USD" }]} />
        <label>输入单价（每百万 Token）<input type="text" inputMode="decimal" value={form.input_price_per_million} onChange={(event) => setForm((current) => ({ ...current, input_price_per_million: event.target.value }))} placeholder="可选" /></label>
        <label>输出单价（每百万 Token）<input type="text" inputMode="decimal" value={form.output_price_per_million} onChange={(event) => setForm((current) => ({ ...current, output_price_per_million: event.target.value }))} placeholder="可选" /></label>
        <p className="form-note">单价按原文保存；只有输入、输出单价都为有效数字时才估算费用。已有任务的预估费用不会随之后的单价修改变化。</p>
        {(create.error || update.error) && <p className="form-error" role="alert">{(create.error || update.error)?.message}</p>}
        <div className="form-actions"><button className="button button-secondary" type="button" onClick={closeEditor}>取消</button><button className="button button-primary" type="submit" disabled={create.isPending || update.isPending}>保存模型</button></div>
      </fieldset></form>
    </Modal>}
  </div>;
}
