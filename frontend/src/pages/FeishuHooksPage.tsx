/** @description 飞书机器人作为独立通知通道，可被多个 GitLab 仓库共享。 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "antd";
import { Plus, Save, X } from "lucide-react";
import { useState } from "react";
import type { FormEvent } from "react";

import { apiRequest } from "../api/client";
import type { NotificationTarget, NotificationTargetInput, Repository } from "../api/types";
import { ConnectionChecks } from "../ui/ConnectionChecks";
import { ListSearch } from "../ui/ListControls";
import { ListTable } from "../ui/ListTable";
import { Modal } from "../ui/Modal";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { ReadFeedback } from "../ui/ReadFeedback";
import { confirmDiscard, UnsavedChangesGuard } from "../ui/UnsavedChangesGuard";
import { useLocalList } from "../ui/useLocalList";

interface TargetForm {
  name: string;
  webhookUrl: string;
  signingSecret: string;
  clearSigning: boolean;
}

const emptyForm: TargetForm = { name: "", webhookUrl: "", signingSecret: "", clearSigning: false };

/** 维护通知通道及连接测试；服务端负责配置写入权限校验。 */
export function FeishuHooksPage({ token, embedded = false }: {
  /** 内存中的管理口令。 */ token: string;
  /** 嵌入系统设置时使用二级标题和内容布局。 */ embedded?: boolean;
}) {
  const queryClient = useQueryClient();
  const targets = useQuery({ queryKey: ["notification-targets"], queryFn: () => apiRequest<NotificationTarget[]>(token, "/api/notification-targets") });
  const repositories = useQuery({ queryKey: ["repositories"], queryFn: () => apiRequest<Repository[]>(token, "/api/repositories") });
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<NotificationTarget | null>(null);
  const [form, setForm] = useState<TargetForm>(emptyForm);
  const dirty = open && JSON.stringify(form) !== JSON.stringify({ ...emptyForm, name: editing?.name ?? "" });
  const closeEditor = () => { if (!save.isPending && confirmDiscard(dirty)) { setOpen(false); setForm(emptyForm); } };
  const [feedback, setFeedback] = useState("");

  const save = useMutation({
    mutationFn: ({ targetId, input }: { targetId: number | null; input: NotificationTargetInput }) =>
      apiRequest<NotificationTarget>(token, targetId === null ? "/api/notification-targets" : `/api/notification-targets/${targetId}`, {
        method: "POST", body: JSON.stringify(input),
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

  const list = useLocalList(targets.error ? undefined : targets.data, (item) => item.name, undefined, "feishu_");
  const checkRepository = repositories.isSuccess && editing
    ? repositories.data?.find((repository) => repository.feishu_target_id === editing.id)
    : undefined;

  return <div className={embedded ? "settings-content" : "page"}>
    <PageHeader headingLevel={embedded ? 2 : 1} title="飞书配置" subtitle="维护可供多个仓库共用的通知通道" actions={<button className="button button-primary" type="button" onClick={beginAdd}><Plus size={17} />新增飞书配置</button>} />
    <UnsavedChangesGuard dirty={dirty} />
    {feedback && <p className="form-success" role="status">{feedback}</p>}
    {remove.error && <p className="form-error" role="alert">{remove.error.message}</p>}
    <QueryState loading={targets.isLoading} error={targets.error} onRetry={() => void targets.refetch()} />
    <ReadFeedback name="关联仓库" loading={repositories.isPending} error={repositories.error} onRetry={() => void repositories.refetch()} />
    <section className="list-surface"><div className="list-toolbar"><ListSearch key={list.q} label="搜索通道" value={list.q} onSearch={(value) => list.update("q", value)} /></div>
      <ListTable rowKey="id" dataSource={list.filtered ?? []} loading={targets.isFetching} pagination={list.pagination} scroll={{ x: 650 }} locale={{ emptyText: targets.error ? "无法读取飞书配置" : "暂无飞书配置" }} columns={[
        { title: "通道名称", key: "name", width: 200, render: (_, target) => <strong>{target.name}</strong> },
        { title: "关联项目", key: "linked", render: (_, target) => {
          const linked = repositories.data?.filter((item) => item.feishu_target_id === target.id) ?? [];
          return <><span>{target.repository_count} 个项目</span><span className="list-secondary">{!repositories.isSuccess ? "关联项目待确认" : linked.length ? linked.slice(0, 2).map((item) => item.name).join("、") : "尚未关联项目"}</span>{linked.length > 2 && <details><summary>其余 {linked.length - 2} 个项目</summary>{linked.slice(2).map((item) => <p key={item.id}>{item.name}</p>)}</details>}</>;
        } },
        { title: "签名配置", key: "signing", width: 150, render: (_, target) => target.has_signing_secret ? "签名校验已配置" : "未配置签名校验" },
        { title: "操作", key: "actions", width: 150, render: (_, target) => <><Button type="link" aria-label={`编辑 ${target.name}`} onClick={() => beginEdit(target)}>编辑</Button><Button type="link" danger aria-label={`删除 ${target.name}`} disabled={remove.isPending} onClick={() => deleteTarget(target)}>删除</Button></> },
      ]} />
      <p className="form-note">签名配置不代表通道可用；测试会向真实群发送消息，须在编辑窗口中显式操作。</p>
    </section>
    {open && <Modal titleId="target-title" onClose={closeEditor}>
      <div className="modal-heading"><h2 id="target-title">{editing ? `编辑 ${editing.name}` : "新增飞书配置"}</h2><button className="icon-button" type="button" title="关闭" aria-label="关闭" onClick={closeEditor}><X size={19} /></button></div>
      <form className="settings-form hook-form" onSubmit={submit}><fieldset className="form-fields" disabled={save.isPending}>
        <label>配置名称<input value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} required /></label>
        <label>Webhook URL<input type="password" autoComplete="new-password" value={form.webhookUrl} onChange={(event) => setForm((current) => ({ ...current, webhookUrl: event.target.value }))} placeholder={editing ? "留空则保留当前地址" : "https://open.feishu.cn/open-apis/bot/v2/hook/…"} required={!editing} /></label>
        <label>签名密钥<input type="password" autoComplete="new-password" value={form.signingSecret} onChange={(event) => setForm((current) => ({ ...current, signingSecret: event.target.value, clearSigning: false }))} placeholder={editing?.has_signing_secret ? "留空则保留当前密钥" : "未启用签名校验时留空"} disabled={form.clearSigning} /></label>
        {editing?.has_signing_secret && <label className="checkbox-label"><input type="checkbox" checked={form.clearSigning} onChange={(event) => setForm((current) => ({ ...current, clearSigning: event.target.checked, signingSecret: "" }))} />移除签名密钥</label>}
        {save.error && <p className="form-error" role="alert">{save.error.message}</p>}
        <div className="form-actions"><button className="button button-secondary" type="button" onClick={closeEditor}>取消</button><button className="button button-primary" type="submit" disabled={save.isPending}><Save size={16} />保存</button></div>
      </fieldset></form>
      {checkRepository && <div className="hook-form"><ConnectionChecks token={token} kinds={["feishu"]} repositoryId={checkRepository.id} /></div>}
    </Modal>}
  </div>;
}
