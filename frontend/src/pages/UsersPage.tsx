/** @description 管理员准备账号并显式启用多人认证；密码从不进入列表缓存。 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Trash2, X } from "lucide-react";
import { useState } from "react";
import type { FormEvent } from "react";

import { apiRequest } from "../api/client";
import { Modal } from "../ui/Modal";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { SelectField } from "../ui/SelectField";
import { Status } from "../ui/Status";
import { formatTime } from "../ui/format";

interface ManagementUser { id: number; username: string; role: "admin" | "reader"; enabled: number; created_at: string }

/** 账号模式启用前至少需要一名管理员；切换后重新加载登录状态。 */
export function UsersPage({ token }: { /** 内存中的管理口令或会话。 */ token: string }) {
  const client = useQueryClient();
  const users = useQuery({ queryKey: ["management-users"], queryFn: () => apiRequest<ManagementUser[]>(token, "/api/auth/users") });
  const mode = useQuery({ queryKey: ["management-auth-mode"], queryFn: () => apiRequest<{ users_enabled: boolean }>(token, "/api/auth/mode") });
  const [adding, setAdding] = useState(false);
  const [editingUser, setEditingUser] = useState<ManagementUser | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"admin" | "reader">("reader");
  const [editRole, setEditRole] = useState<"admin" | "reader">("reader");
  const [editEnabled, setEditEnabled] = useState(true);
  const [feedback, setFeedback] = useState("");
  const refresh = () => void client.invalidateQueries({ queryKey: ["management-users"] });
  const create = useMutation({
    mutationFn: () => apiRequest(token, "/api/auth/users", { method: "POST", body: JSON.stringify({ username, password, role }) }),
    onSuccess: () => { setAdding(false); setUsername(""); setPassword(""); setRole("reader"); setFeedback("账号已创建"); refresh(); },
  });
  const update = useMutation({
    mutationFn: ({ id, input }: { id: number; input: { role?: string; enabled?: boolean; password?: string } }) => apiRequest(token, `/api/auth/users/${id}`, { method: "PATCH", body: JSON.stringify(input) }),
    onSuccess: () => { setEditingUser(null); setPassword(""); setFeedback("账号已更新，原有会话已失效"); refresh(); void client.invalidateQueries({ queryKey: ["auth-me"] }); },
  });
  const remove = useMutation({
    mutationFn: (id: number) => apiRequest(token, `/api/auth/users/${id}`, { method: "DELETE" }),
    onSuccess: () => { setEditingUser(null); setFeedback("账号已删除"); refresh(); void client.invalidateQueries({ queryKey: ["auth-me"] }); },
  });
  const switchMode = useMutation({
    mutationFn: (users_enabled: boolean) => apiRequest(token, "/api/auth/mode", { method: "PUT", body: JSON.stringify({ users_enabled }) }),
    onSuccess: () => window.location.reload(),
  });
  function closeEditor() { setAdding(false); setEditingUser(null); setPassword(""); }
  function openEditor(user: ManagementUser) { update.reset(); remove.reset(); setEditingUser(user); setEditRole(user.role); setEditEnabled(Boolean(user.enabled)); setPassword(""); }
  function submit(event: FormEvent) {
    event.preventDefault();
    if (adding) create.mutate();
    else if (editingUser) update.mutate({ id: editingUser.id, input: { role: editRole, enabled: editEnabled, ...(password ? { password } : {}) } });
  }
  return <div className="page"><PageHeader title="访问权限" subtitle="管理账号与只读账号" actions={<button className="button button-primary" type="button" onClick={() => { create.reset(); setPassword(""); setAdding(true); }}><Plus size={17} />添加账号</button>} />
    {feedback && <p className="form-success" role="status">{feedback}</p>}
    <section className="section"><div className="inline-setting"><h2>认证方式</h2><label className="checkbox-label"><input type="checkbox" checked={mode.data?.users_enabled ?? false} disabled={mode.isLoading || switchMode.isPending} onChange={(event) => { if (window.confirm(event.target.checked ? "启用账号登录后，现有共享口令立即失效。确定继续？" : "关闭账号登录后恢复原有本机访问方式。确定继续？")) switchMode.mutate(event.target.checked); }} />启用多人账号登录</label></div><QueryState loading={mode.isLoading} error={mode.error || switchMode.error} /></section>
    <section className="section"><div className="section-head"><h2>账号</h2><span>{users.data?.length ?? 0} 人</span></div><QueryState loading={users.isLoading} error={users.error} /><div className="table-scroll responsive-table"><table><thead><tr><th>用户名</th><th>角色</th><th>状态</th><th>创建时间</th><th aria-label="操作" /></tr></thead><tbody>
      {users.data?.map((user) => <tr key={user.id}><td data-label="用户名"><strong>{user.username}</strong></td><td data-label="角色">{user.role === "admin" ? "管理员" : "只读"}</td><td data-label="状态"><Status value={user.enabled ? "enabled" : "disabled"} /></td><td data-label="创建时间">{formatTime(user.created_at)}</td><td data-label="操作"><button className="icon-button" type="button" title="编辑账号" aria-label={`编辑 ${user.username}`} onClick={() => openEditor(user)}><Pencil size={16} /></button></td></tr>)}
      {users.data?.length === 0 && <tr><td className="empty-row" colSpan={5}>暂无账号，先添加一名管理员</td></tr>}
    </tbody></table></div></section>
    {(adding || editingUser) && <Modal titleId="user-title" onClose={closeEditor}><div className="modal-heading"><h2 id="user-title">{adding ? "添加账号" : `编辑 ${editingUser?.username}`}</h2><button className="icon-button" type="button" title="关闭" aria-label="关闭" onClick={closeEditor}><X size={19} /></button></div><form className="settings-form hook-form" onSubmit={submit}>
      {adding ? <><label>用户名<input value={username} onChange={(event) => setUsername(event.target.value)} minLength={3} maxLength={64} pattern="[A-Za-z0-9._-]+" required /></label><SelectField label="角色" value={role} onValueChange={(value) => setRole(value === "admin" ? "admin" : "reader")} options={[{ value: "admin", label: "管理员" }, { value: "reader", label: "只读" }]} /></> : <><SelectField label="角色" value={editRole} onValueChange={(value) => setEditRole(value === "admin" ? "admin" : "reader")} options={[{ value: "admin", label: "管理员" }, { value: "reader", label: "只读" }]} /><label className="checkbox-label"><input type="checkbox" checked={editEnabled} onChange={(event) => setEditEnabled(event.target.checked)} />启用账号</label></>}
      <label>{adding ? "密码" : "新密码（留空则不修改）"}<input type="password" autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} minLength={12} maxLength={128} required={adding} /></label>
      {(create.error || update.error || remove.error) && <p className="form-error" role="alert">{(create.error || update.error || remove.error)?.message}</p>}
      <div className="form-actions account-form-actions">{editingUser && <button className="button button-danger account-delete" type="button" disabled={remove.isPending} onClick={() => { if (window.confirm(`确定删除账号“${editingUser.username}”？该账号会立即退出登录。`)) remove.mutate(editingUser.id); }}><Trash2 size={16} />删除账号</button>}<button className="button button-secondary" type="button" onClick={closeEditor}>取消</button><button className="button button-primary" type="submit" disabled={create.isPending || update.isPending}>保存账号</button></div>
    </form></Modal>}
  </div>;
}
