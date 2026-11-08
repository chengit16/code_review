/** @description 管理 OCR 模型配置，只有一个配置可处于启用状态。 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Card } from "antd";
import type { TableColumnsType } from "antd";
import { Plus, RefreshCw, X } from "lucide-react";
import { useState } from "react";
import type { FormEvent } from "react";

import { apiRequest } from "../api/client";
import type { ModelConfiguration } from "../api/types";
import { ConnectionChecks } from "../ui/ConnectionChecks";
import { ListSearch, ListStatusNav } from "../ui/ListControls";
import { ListTable as Table } from "../ui/ListTable";
import { Modal } from "../ui/Modal";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { SelectField } from "../ui/SelectField";
import { confirmDiscard, UnsavedChangesGuard } from "../ui/UnsavedChangesGuard";
import { useLocalList } from "../ui/useLocalList";

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
        method: "POST", body: JSON.stringify({ ...payload, input_price_per_million: input.input_price_per_million || null, output_price_per_million: input.output_price_per_million || null }),
      });
    },
    onSuccess: () => { setOpen(false); setEditing(null); setForm(initial); setFeedback("模型配置已更新"); refresh(); },
  });
  const catalog = useMutation({
    mutationFn: (input: Pick<ModelForm, "provider" | "base_url" | "api_key"> & { profile_id?: number }) =>
      apiRequest<{ models: string[] }>(token, "/api/model-catalog", {
        method: "POST", body: JSON.stringify(input),
      }),
  });
  // 目录只对发起请求时的凭据与端点有效，旧响应不能覆盖新的编辑输入。
  const catalogMatches = open && catalog.variables?.provider === form.provider
    && catalog.variables?.base_url === form.base_url && catalog.variables?.api_key === form.api_key
    && catalog.variables?.profile_id === editing?.id;
  const catalogModels = catalogMatches ? catalog.data?.models ?? [] : [];
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
    catalog.reset();
    setEditing(profile);
    const draft: ModelForm = { name: profile.name, provider: profile.provider, model: profile.model, base_url: profile.base_url, api_key: "", price_currency: profile.price_currency, input_price_per_million: profile.input_price_per_million ?? "", output_price_per_million: profile.output_price_per_million ?? "" };
    setBaseline(draft);
    setForm(draft);
    create.reset();
    update.reset();
    setOpen(true);
  }
  const active = profiles.data?.find((profile) => profile.enabled);
  const list = useLocalList(profiles.error ? undefined : profiles.data, (item) => `${item.name} ${item.model} ${item.provider} ${item.base_url}`, (item) => item.enabled ? "enabled" : "disabled", "model_");
  const columns: TableColumnsType<ModelConfiguration> = [
    { title: "配置名称", dataIndex: "name", key: "name", render: (name: string, profile) => <><strong>{name}</strong><span className="list-secondary mono">{profile.model}</span></> },
    { title: "Provider", dataIndex: "provider", key: "provider", width: 150, render: (value: string) => value === "dashscope" ? "百练 / DashScope" : value },
    { title: "Base URL", dataIndex: "base_url", key: "base_url", width: 220, render: (value: string) => <span className="mono">{value || "内置端点"}</span> },
    { title: "单价 / 百万 Token", key: "price", width: 210, render: (_: unknown, profile) => profile.input_price_per_million != null || profile.output_price_per_million != null ? `${profile.price_currency === "CNY" ? "¥" : "$"}${profile.input_price_per_million ?? "未配置"} 输入 / ${profile.output_price_per_million ?? "未配置"} 输出` : "未配置" },
    { title: "状态", dataIndex: "enabled", key: "enabled", width: 100, render: (enabled: number) => enabled ? "已启用" : "未启用" },
    { title: "操作", key: "actions", width: 132, render: (_: unknown, profile) => <div className="row-actions">{!profile.enabled && <Button type="text" title="启用模型" aria-label={`启用 ${profile.name}`} disabled={activate.isPending} onClick={() => activate.mutate(profile.id)}>启用</Button>}<Button type="text" title="编辑模型" aria-label={`编辑 ${profile.name}`} onClick={() => beginEdit(profile)}>编辑</Button><Button danger type="text" title="删除模型" aria-label={`删除 ${profile.name}`} disabled={Boolean(profile.enabled) || remove.isPending} onClick={() => { if (window.confirm(`确定删除模型“${profile.name}”？`)) remove.mutate(profile.id); }}>删除</Button></div> },
  ];
  return <div className={embedded ? "settings-content" : "page"}>
    <PageHeader headingLevel={embedded ? 2 : 1} title="Agent 模型" subtitle="Open Code Review 评审模型" actions={<button className="button button-primary" type="button" onClick={() => { setEditing(null); setBaseline(initial); setForm(initial); create.reset(); update.reset(); catalog.reset(); setOpen(true); }}><Plus size={17} />新增模型</button>} />
    <UnsavedChangesGuard dirty={dirty} />
    {feedback && <p className="form-success" role="status">{feedback}</p>}
    {(activate.error || remove.error) && <p className="form-error" role="alert">{(activate.error || remove.error)?.message}</p>}
    <QueryState loading={profiles.isLoading} error={profiles.error} />
    {!profiles.isLoading && !profiles.error && <Card className="model-profile-card" size="small" title={<h2 className="model-profile-heading">模型配置</h2>}>
<div className="list-toolbar"><ListSearch key={list.q} label="搜索配置" value={list.q} onSearch={(value) => list.update("q", value)} /></div><ListStatusNav value={list.status} labels={{ all: "全部", enabled: "已启用", disabled: "未启用" }} counts={list.counts} onChange={(value) => list.update("status", value)} />      <Table rowKey="id" size="middle" columns={columns} dataSource={list.filtered ?? []} loading={profiles.isFetching} locale={{ emptyText: profiles.error ? "无法读取模型配置" : "尚无模型配置" }} scroll={{ x: 1000 }} pagination={list.pagination} />
      <p className="form-note">连接测试只测试当前已启用的模型{active ? `“${active.name}”` : ""}，保存配置不会发起模型请求。切换模型后请重新测试，最近结果可能来自之前启用的配置。</p>
      <ConnectionChecks token={token} kinds={["model"]} enabled={Boolean(active)} />
    </Card>}
    {open && <Modal titleId="model-title" onClose={closeEditor}>
      <div className="modal-heading"><h2 id="model-title">{editing ? `编辑 ${editing.name}` : "新增模型"}</h2><button className="icon-button" type="button" title="关闭" aria-label="关闭" onClick={closeEditor}><X size={19} /></button></div>
      <form className="settings-form hook-form" noValidate onSubmit={submit}><fieldset className="form-fields" disabled={create.isPending || update.isPending}>
        <p className="form-note">可随时保存，字段留空或尚未填写完整也不影响保存。保存不代表模型可用，请另行测试模型。</p>
        <label>配置名称<input value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} /></label>
        <SelectField label="Provider" value={form.provider} onValueChange={(value) => { catalog.reset(); setForm((current) => ({ ...current, provider: value })); }} options={[{ value: "dashscope", label: "百练 / DashScope" }, { value: "openai", label: "OpenAI" }, { value: "anthropic", label: "Anthropic" }]} />
        {form.provider === "dashscope" && <p className="form-note">百练模型使用 DashScope API Key 和模型标识；Base URL 留空即可使用内置端点。</p>}
        <label>Base URL<input value={form.base_url} onChange={(event) => { catalog.reset(); setForm((current) => ({ ...current, base_url: event.target.value })); }} placeholder="内置 Provider 可留空" /></label>
        <label>API Key<input type="password" autoComplete="new-password" value={form.api_key} onChange={(event) => { catalog.reset(); setForm((current) => ({ ...current, api_key: event.target.value })); }} placeholder={editing ? "留空则保留现有密钥" : "可留空，后续补充"} /></label>
        <div className="form-actions"><button className="button button-secondary" type="button" disabled={(!form.api_key.trim() && !editing?.has_api_key) || catalog.isPending} onClick={() => catalog.mutate({ provider: form.provider, base_url: form.base_url, api_key: form.api_key, profile_id: editing?.id })}><RefreshCw size={16} />{catalog.isPending ? "获取中…" : "自动获取模型"}</button></div>
        <p className="form-note">编辑时可留空 API Key，使用已保存的密钥获取模型；更换 Provider 或 Base URL 后需重新填写密钥。获取列表不代表所有模型均支持代码评审。</p>
        {catalogMatches && catalog.error && <p className="form-error" role="alert">{catalog.error.message}</p>}
        {catalogModels.length > 0 && <><p className="form-success" role="status">已获取 {catalogModels.length} 个模型，请选择</p><SelectField label="选择模型" placeholder="请选择模型" value={catalogModels.includes(form.model) ? form.model : ""} onValueChange={(value) => setForm((current) => ({ ...current, model: value }))} options={catalogModels.map((model) => ({ value: model, label: model }))} /></>}
        <label>模型标识<input value={form.model} onChange={(event) => setForm((current) => ({ ...current, model: event.target.value }))} /></label>
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
