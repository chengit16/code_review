/** @description 仓库创建表单先读取元数据再核对；不保存远端凭据、不绕过服务端预检。 */
import { Button, Checkbox, Select } from "antd";
import type { FormEvent } from "react";

import type { NotificationTarget, RepositoryInput } from "../api/types";
import { RepositoryConnectionFields } from "./RepositoryConnectionFields";
import type { ResolvedRepository } from "./RepositoryConnectionFields";


/** 父页拥有草稿与原子保存，身份字段由服务器识别。 */
export function RepositoryCreateForm({ token, form, targets, pending, error, onField, onMetadata, onSubmit, onCancel }: {
  /** 内存会话。 */ token: string;
  /** 当前表单草稿。 */ form: RepositoryInput;
  /** 手动变动使旧元数据请求失效。 */ draftVersion: number;
  /** 已保存通知通道。 */ targets: NotificationTarget[];
  /** 保存期间禁止再次提交。 */ pending: boolean;
  /** 原样展示安全服务端错误。 */ error: Error | null;
  /** 更新单项，不自动保存。 */ onField: <K extends keyof RepositoryInput>(key: K, value: RepositoryInput[K]) => void;
  /** 只回填当前请求结果。 */ onMetadata: (value: ResolvedRepository) => void;
  /** 父页先预检再保存。 */ onSubmit: (event: FormEvent) => void;
  /** 父页执行草稿离开确认。 */ onCancel: () => void;
}) {
  return <form onSubmit={onSubmit} className="form-grid"><fieldset className="configuration-fields form-grid wide" disabled={pending}>
    <RepositoryConnectionFields token={token} remoteUrl={form.remote_url} gitlabToken={form.gitlab_token} branches={form.target_branches ?? (form.target_branch ? [form.target_branch] : [])} disabled={pending} onRemote={(value) => onField("remote_url", value)} onToken={(value) => onField("gitlab_token", value)} onBranches={(value) => onField("target_branches", value)} onResolved={onMetadata} />
    <label className="wide">飞书配置<Select aria-label="飞书配置" value={form.feishu_target_id ?? 0} disabled={pending} onChange={(value) => onField("feishu_target_id", value || null)} options={[{ value: 0, label: "暂不关联" }, ...targets.map((target) => ({ value: target.id, label: target.name }))]} /></label>
    <div className="repository-trigger-options wide" role="group" aria-label="评审触发方式">
    <Checkbox checked={form.premerge_enabled ?? false} onChange={(e) => onField("premerge_enabled", e.target.checked)}>合并前 MR 评审</Checkbox>
    <Checkbox checked={form.enable_default_branch_pushes} onChange={(e) => onField("enable_default_branch_pushes", e.target.checked)}>目标分支 Push 评审</Checkbox></div>
    <p className="form-note wide">同一版本已触发合并前评审，合入目标分支时自动复用任务。未配置飞书通道时不会发送通知。</p>
    {error && <p className="form-error wide" role="alert">{error.message}</p>}
    <div className="form-actions configuration-save-bar wide"><Button onClick={onCancel} disabled={pending}>取消</Button><Button htmlType="submit" type="primary" loading={pending} disabled={!form.query_session_id || !form.target_branches?.length}>保存仓库</Button></div>
  </fieldset></form>;
}
