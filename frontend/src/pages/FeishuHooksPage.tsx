/** @description 飞书机器人作为独立通知通道，可被多个 GitLab 仓库共享。 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Save, Settings2, Trash2, X } from "lucide-react";
import { useState } from "react";
import type { FormEvent } from "react";

import { apiRequest } from "../api/client";
import type { NotificationTarget, NotificationTargetInput, Repository } from "../api/types";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";

interface TargetForm {
  name: string;
  webhookUrl: string;
  signingSecret: string;
  clearSigning: boolean;
}

const emptyForm: TargetForm = { name: "", webhookUrl: "", signingSecret: "", clearSigning: false };

export function FeishuHooksPage({ token }: { /** 内存中的管理口令。 */ token: string }) {
  const queryClient = useQueryClient();
  const targets = useQuery({ queryKey: ["notification-targets"], queryFn: () => apiRequest<NotificationTarget[]>(token, "/api/notification-targets") });
  const repositories = useQuery({ queryKey: ["repositories"], queryFn: () => apiRequest<Repository[]>(token, "/api/repositories") });
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<NotificationTarget | null>(null);
  const [form, setForm] = useState<TargetForm>(emptyForm);
  const [feedback, setFeedback] = useState("");

  const save = useMutation({
    mutationFn: ({ targetId, input }: { targetId: number | null; input: NotificationTargetInput }) =>
      apiRequest<NotificationTarget>(token, targetId === null ? "/api/notification-targets" : `/api/notification-targets/${targetId}`, {
        method: targetId === null ? "POST" : "PATCH", body: JSON.stringify(input),
      }),
    onSuccess: () => {
      setOpen(false);
      setEditing(null);
      setForm(emptyForm);
      setFeedback("飞书配置已保存");
      void queryClient.invalidateQueries({ queryKey: ["notification-targets"] });
      void queryClient.invalidateQueries({ queryKey: ["repositories"] });
    },
  });
  const remove = useMutation({
    mutationFn: (targetId: number) => apiRequest<{ status: string }>(token, `/api/notification-targets/${targetId}`, { method: "DELETE" }),
    onSuccess: () => {
      setFeedback("飞书配置已删除，关联仓库已解除绑定");
      void queryClient.invalidateQueries({ queryKey: ["notification-targets"] });
      void queryClient.invalidateQueries({ queryKey: ["repositories"] });
    },
  });

  function beginAdd() {
    setEditing(null);
    setForm(emptyForm);
    setOpen(true);
    save.reset();
  }

  function beginEdit(target: NotificationTarget) {
    setEditing(target);
    setForm({ ...emptyForm, name: target.name });
    setOpen(true);
    save.reset();
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    const input: NotificationTargetInput = { name: form.name.trim() };
    if (form.webhookUrl.trim()) input.webhook_url = form.webhookUrl.trim();
    if (form.signingSecret) input.signing_secret = form.signingSecret;
    if (form.clearSigning) input.signing_secret = "";
    save.mutate({ targetId: editing?.id ?? null, input });
  }

  function deleteTarget(target: NotificationTarget) {
    if (!window.confirm(`确定删除飞书配置“${target.name}”？${target.repository_count} 个关联仓库将不再发送通知。`)) return;
    setFeedback("");
    remove.reset();
    remove.mutate(target.id);
  }

  return <div className="page">
    <PageHeader title="飞书配置" subtitle="维护可供多个仓库共用的通知通道" actions={<button className="button button-primary" type="button" onClick={beginAdd}><Plus size={17} />新增飞书配置</button>} />
    {feedback && <p className="form-success" role="status">{feedback}</p>}
    {remove.error && <p className="form-error" role="alert">{remove.error.message}</p>}
    <QueryState loading={targets.isLoading} error={targets.error} />
    {!targets.isLoading && !targets.error && <section className="section">
      <div className="hook-list">
        {targets.data?.map((target) => {
          const linked = repositories.data?.filter((repository) => repository.feishu_target_id === target.id) ?? [];
          return <article className="hook-row" key={target.id}>
            <div className="hook-project"><strong>{target.name}</strong><span>{linked.length ? linked.map((repository) => repository.name).join("、") : "尚未关联仓库"}</span></div>
            <span>{target.repository_count} 个仓库</span>
            <span className="hook-last">{target.has_signing_secret ? "签名校验已配置" : "未配置签名校验"}</span>
            <div className="row-actions">
              <button className="icon-button" type="button" title="编辑飞书配置" aria-label={`编辑 ${target.name}`} onClick={() => beginEdit(target)}><Settings2 size={16} /></button>
              <button className="icon-button icon-button-danger" type="button" title="删除飞书配置" aria-label={`删除 ${target.name}`} onClick={() => deleteTarget(target)} disabled={remove.isPending}><Trash2 size={16} /></button>
            </div>
          </article>;
        })}
        {targets.data?.length === 0 && <p className="empty-inline">暂无飞书配置</p>}
      </div>
    </section>}
    {open && <div className="modal-backdrop" role="presentation"><div className="modal" role="dialog" aria-modal="true" aria-labelledby="target-title">
      <div className="modal-heading"><h2 id="target-title">{editing ? `编辑 ${editing.name}` : "新增飞书配置"}</h2><button className="icon-button" type="button" title="关闭" aria-label="关闭" onClick={() => setOpen(false)}><X size={19} /></button></div>
      <form className="settings-form hook-form" onSubmit={submit}>
        <label>配置名称<input value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} required /></label>
        <label>Webhook URL<input type="password" autoComplete="new-password" value={form.webhookUrl} onChange={(event) => setForm((current) => ({ ...current, webhookUrl: event.target.value }))} placeholder={editing ? "留空则保留当前地址" : "https://open.feishu.cn/open-apis/bot/v2/hook/…"} required={!editing} /></label>
        <label>签名密钥<input type="password" autoComplete="new-password" value={form.signingSecret} onChange={(event) => setForm((current) => ({ ...current, signingSecret: event.target.value, clearSigning: false }))} placeholder={editing?.has_signing_secret ? "留空则保留当前密钥" : "未启用签名校验时留空"} disabled={form.clearSigning} /></label>
        {editing?.has_signing_secret && <label className="checkbox-label"><input type="checkbox" checked={form.clearSigning} onChange={(event) => setForm((current) => ({ ...current, clearSigning: event.target.checked, signingSecret: "" }))} />移除签名密钥</label>}
        {save.error && <p className="form-error" role="alert">{save.error.message}</p>}
        <div className="form-actions"><button className="button button-secondary" type="button" onClick={() => setOpen(false)}>取消</button><button className="button button-primary" type="submit" disabled={save.isPending}><Save size={16} />保存</button></div>
      </form>
    </div></div>}
  </div>;
}
