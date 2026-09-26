/** @description 管理员准备账号并显式启用多人认证；密码从不进入列表缓存。 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, RotateCcw, Trash2, X } from "lucide-react";
import { useState } from "react";
import type { FormEvent } from "react";

import { apiRequest } from "../api/client";
import { Modal } from "../ui/Modal";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { SelectField } from "../ui/SelectField";
import { formatTime } from "../ui/format";

interface ManagementUser { id: number; username: string; role: "admin" | "reader"; enabled: number; created_at: string }

/** 账号模式启用前至少需要一名管理员；切换后重新加载登录状态。 */
export function UsersPage({ token }: { /** 内存中的管理口令或会话。 */ token: string }) {
  const client = useQueryClient();
  const users = useQuery({ queryKey: ["management-users"], queryFn: () => apiRequest<ManagementUser[]>(token, "/api/auth/users") });
  const mode = useQuery({ queryKey: ["management-auth-mode"], queryFn: () => apiRequest<{ users_enabled: boolean }>(token, "/api/auth/mode") });
  const [adding, setAdding] = useState(false);
  const [resetUser, setResetUser] = useState<ManagementUser | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"admin" | "reader">("reader");
  const [feedback, setFeedback] = useState("");
  const refresh = () => void client.invalidateQueries({ queryKey: ["management-users"] });
  const create = useMutation({
    mutationFn: () => apiRequest(token, "/api/auth/users", { method: "POST", body: JSON.stringify({ username, password, role }) }),
    onSuccess: () => { setAdding(false); setUsername(""); setPassword(""); setRole("reader"); setFeedback("账号已创建"); refresh(); },
  });
  const update = useMutation({
    mutationFn: ({ id, input }: { id: number; input: { role?: string; enabled?: boolean; password?: string } }) => apiRequest(token, `/api/auth/users/${id}`, { method: "PATCH", body: JSON.stringify(input) }),
    onSuccess: () => { setResetUser(null); setPassword(""); setFeedback("账号已更新，原有会话已失效"); refresh(); void client.invalidateQueries({ queryKey: ["auth-me"] }); },
  });
  const remove = useMutation({
    mutationFn: (id: number) => apiRequest(token, `/api/auth/users/${id}`, { method: "DELETE" }),
    onSuccess: () => { setFeedback("账号已删除"); refresh(); void client.invalidateQueries({ queryKey: ["auth-me"] }); },
  });
  const switchMode = useMutation({
    mutationFn: (users_enabled: boolean) => apiRequest(token, "/api/auth/mode", { method: "PUT", body: JSON.stringify({ users_enabled }) }),
    onSuccess: () => window.location.reload(),
  });
  function submit(event: FormEvent) { event.preventDefault(); if (adding) create.mutate(); else if (resetUser) update.mutate({ id: resetUser.id, input: { password } }); }
  return <div className="page"><PageHeader title="访问权限" subtitle="管理账号与只读账号" actions={<button className="button button-primary" type="button" onClick={() => { setPassword(""); setAdding(true); }}><Plus size={17} />添加账号</button>} />
    {feedback && <p className="form-success" role="status">{feedback}</p>}
    <section className="section"><div className="section-head"><h2>认证方式</h2></div><QueryState loading={mode.isLoading} error={mode.error || switchMode.error} /><label className="checkbox-label"><input type="checkbox" checked={mode.data?.users_enabled ?? false} disabled={mode.isLoading || switchMode.isPending} onChange={(event) => { if (window.confirm(event.target.checked ? "启用账号登录后，现有共享口令立即失效。确定继续？" : "关闭账号登录后恢复原有本机访问方式。确定继续？")) switchMode.mutate(event.target.checked); }} />启用多人账号登录</label></section>
    <section className="section"><div className="section-head"><h2>账号</h2><span>{users.data?.length ?? 0} 人</span></div><QueryState loading={users.isLoading} error={users.error || update.error || create.error || remove.error} /><div className="table-scroll responsive-table"><table><thead><tr><th>用户名</th><th>角色</th><th>启用</th><th>创建时间</th><th aria-label="操作" /></tr></thead><tbody>
      {users.data?.map((user) => <tr key={user.id}><td data-label="用户名"><strong>{user.username}</strong></td><td data-label="角色"><SelectField label={`${user.username} 角色`} value={user.role} disabled={update.isPending} onValueChange={(value) => update.mutate({ id: user.id, input: { role: value } })} options={[{ value: "admin", label: "管理员" }, { value: "reader", label: "只读" }]} /></td><td data-label="启用"><label className="toggle-hit"><input className="repo-toggle" type="checkbox" checked={Boolean(user.enabled)} disabled={update.isPending} aria-label={`${user.username} 启用`} onChange={(event) => update.mutate({ id: user.id, input: { enabled: event.target.checked } })} /></label></td><td data-label="创建时间">{formatTime(user.created_at)}</td><td data-label="操作"><div className="row-actions"><button className="icon-button" type="button" title="重置密码" aria-label={`重置 ${user.username} 密码`} onClick={() => { setResetUser(user); setPassword(""); }}><RotateCcw size={16} /></button><button className="icon-button icon-button-danger" type="button" title="删除账号" aria-label={`删除 ${user.username}`} disabled={remove.isPending} onClick={() => { if (window.confirm(`确定删除账号“${user.username}”？该账号会立即退出登录。`)) remove.mutate(user.id); }}><Trash2 size={16} /></button></div></td></tr>)}
      {users.data?.length === 0 && <tr><td className="empty-row" colSpan={5}>暂无账号，先添加一名管理员</td></tr>}
    </tbody></table></div></section>
    {(adding || resetUser) && <Modal titleId="user-title" onClose={() => { setAdding(false); setResetUser(null); setPassword(""); }}><div className="modal-heading"><h2 id="user-title">{adding ? "添加账号" : `重置 ${resetUser?.username} 密码`}</h2><button className="icon-button" type="button" title="关闭" aria-label="关闭" onClick={() => { setAdding(false); setResetUser(null); setPassword(""); }}><X size={19} /></button></div><form className="settings-form hook-form" onSubmit={submit}>
      {adding && <><label>用户名<input value={username} onChange={(event) => setUsername(event.target.value)} minLength={3} maxLength={64} pattern="[A-Za-z0-9._-]+" required /></label><SelectField label="角色" value={role} onValueChange={(value) => setRole(value === "admin" ? "admin" : "reader")} options={[{ value: "admin", label: "管理员" }, { value: "reader", label: "只读" }]} /></>}
      <label>密码<input type="password" autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} minLength={12} maxLength={128} required /></label>
      {(create.error || update.error) && <p className="form-error" role="alert">{(create.error || update.error)?.message}</p>}
      <div className="form-actions"><button className="button button-secondary" type="button" onClick={() => { setAdding(false); setResetUser(null); setPassword(""); }}>取消</button><button className="button button-primary" type="submit" disabled={create.isPending || update.isPending}>保存账号</button></div>
    </form></Modal>}
  </div>;
}
