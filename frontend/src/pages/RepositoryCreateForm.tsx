/** @description 仓库创建表单先读取元数据再核对；不保存远端凭据、不绕过服务端预检。 */
import { Button, Checkbox, Input, InputNumber } from "antd";
import type { FormEvent } from "react";

import type { NotificationTarget, RepositoryInput } from "../api/types";
import { SelectField } from "../ui/SelectField";
import { RepositoryMetadataLookup } from "./RepositoryMetadataLookup";
import type { RepositoryMetadata } from "../api/services/setup";

/** 保留手动填写与明确保存；父页拥有草稿、预检和错误状态。 */
export function RepositoryCreateForm({ token, form, draftVersion, targets, pending, error, onField, onMetadata, onSubmit, onCancel }: {
  /** 内存会话。 */ token: string;
  /** 当前表单草稿。 */ form: RepositoryInput;
  /** 手动变动使旧元数据请求失效。 */ draftVersion: number;
  /** 已保存通知通道。 */ targets: NotificationTarget[];
  /** 保存期间禁止再次提交。 */ pending: boolean;
  /** 原样展示安全服务端错误。 */ error: Error | null;
  /** 更新单项，不自动保存。 */ onField: <K extends keyof RepositoryInput>(key: K, value: RepositoryInput[K]) => void;
  /** 只回填当前请求结果。 */ onMetadata: (value: RepositoryMetadata) => void;
  /** 父页先预检再保存。 */ onSubmit: (event: FormEvent) => void;
  /** 父页执行草稿离开确认。 */ onCancel: () => void;
}) {
  return <form onSubmit={onSubmit} className="form-grid"><fieldset className="configuration-fields form-grid wide" disabled={pending}>
    <label className="wide">GitLab 项目或 Clone 地址<Input type="url" placeholder="https://gitlab.example.com/team/repo.git" value={form.remote_url} onChange={(e) => onField("remote_url", e.target.value)} required disabled={pending} /></label>
    <label className="wide">GitLab Token<Input.Password autoComplete="new-password" value={form.gitlab_token} onChange={(e) => onField("gitlab_token", e.target.value)} required disabled={pending} /></label>
    <RepositoryMetadataLookup token={token} remoteUrl={form.remote_url} gitlabToken={form.gitlab_token ?? ""} draftVersion={draftVersion} onResolved={onMetadata} />
    <label>仓库名称<Input value={form.name} onChange={(e) => onField("name", e.target.value)} required /></label>
    <label>项目数字 ID<InputNumber min={1} precision={0} value={form.project_id || null} onChange={(value) => onField("project_id", value ?? 0)} required /></label>
    <label>仓库路径<Input placeholder="team/repo" value={form.path_with_namespace} onChange={(e) => onField("path_with_namespace", e.target.value)} required /></label>
    <label>目标分支<Input value={form.target_branch} onChange={(e) => onField("target_branch", e.target.value)} required /></label>
    <SelectField label="飞书配置" value={form.feishu_target_id == null ? "none" : String(form.feishu_target_id)} onValueChange={(value) => onField("feishu_target_id", value === "none" ? null : Number(value))} options={[{ value: "none", label: "暂不关联" }, ...targets.map((target) => ({ value: String(target.id), label: target.name }))]} />
    <Checkbox checked={form.enable_merge_requests} onChange={(e) => onField("enable_merge_requests", e.target.checked)}>合并后评审（Merge Request）</Checkbox>
    <Checkbox checked={form.enable_default_branch_pushes} onChange={(e) => onField("enable_default_branch_pushes", e.target.checked)}>默认分支提交评审（Push）</Checkbox>
    {error && <p className="form-error wide" role="alert">{error.message}</p>}
    <div className="form-actions configuration-save-bar wide"><Button onClick={onCancel} disabled={pending}>取消</Button><Button htmlType="submit" type="primary" loading={pending}>保存仓库</Button></div>
  </fieldset></form>;
}
