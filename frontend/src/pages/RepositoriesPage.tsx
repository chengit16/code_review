/** @description 同页维护 GitLab 项目、Webhook 与评审开关；飞书和模型配置独立。 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Card, Checkbox, Drawer, Input, Select, Switch, Tag } from "antd";
import type { TableColumnsType } from "antd";
import { Check, Copy, Plus, RotateCcw, X } from "lucide-react";
import { useCallback, useContext, useEffect, useLayoutEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { flushSync } from "react-dom";
import { UNSAFE_DataRouterContext, useSearchParams } from "react-router-dom";

import { apiRequest } from "../api/client";
import type { NotificationTarget, Repository, RepositoryInput, RepositoryUpdateInput } from "../api/types";
import { RouteButton } from "../ui/RouteButton";
import { EffectiveConfiguration } from "./EffectiveConfiguration";
import { RepositoryCreateForm } from "./RepositoryCreateForm";
import { ConnectionChecks } from "../ui/ConnectionChecks";
import { ListSearch, ListStatusNav, ListSelect } from "../ui/ListControls";
import { ListTable as Table } from "../ui/ListTable";
import { Modal } from "../ui/Modal";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { ReadFeedback } from "../ui/ReadFeedback";
import { SelectField } from "../ui/SelectField";
import { confirmDiscard, UnsavedChangesGuard } from "../ui/UnsavedChangesGuard";
import { copyText } from "../ui/clipboard";
import { formatTime } from "../ui/format";
import type { DraftStatus } from "../ui/useConfigurationDraft";
import { useLocalList } from "../ui/useLocalList";

import { GitLabPublicationSetting } from "./GitLabPublicationSetting";
import { RepositoryConnectionFields } from "./RepositoryConnectionFields";
import { PremergeSetting } from "./PremergeSetting";
import { ProjectReviewLimits } from "./ProjectReviewLimits";
import { ProjectAgentSettings } from "./agentCapabilities/ProjectAgentSettings";
import { RepositoryDiagnosis } from "./RepositoryDiagnosis";
import { WebhookTokenCell } from "./WebhookTokenCell";
import "../styles/repository-publication.css";

function editContent(value: RepositoryUpdateInput) {
  return JSON.stringify(Object.fromEntries(Object.entries(value).filter(([key]) => key !== "query_session_id").sort(([left], [right]) => left.localeCompare(right))));
}

interface Readiness { repository_id: number; status: "ready" | "needs_check" | "paused"; git: string; gitlab: string; config_revision_id: number | null }
type RepositoryEditSection = "connection" | "review" | "agent" | "publication" | "diagnosis";

const initial: RepositoryInput = {
  name: "", gitlab_url: "", project_id: 0, remote_url: "", target_branch: "", target_branches: [],
  path_with_namespace: "", gitlab_token: "", enable_merge_requests: false,
  enable_default_branch_pushes: true, auth_kind: "secret",
};

/** 保存项目接入配置，密钥提交成功后立即从表单内存清除。 */
export function RepositoriesPage({ token }: { /** 内存中的管理口令。 */ token: string }) {
  const editorBody = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();
  const hasDataRouter = Boolean(useContext(UNSAFE_DataRouterContext));
  const query = useQuery({ queryKey: ["repositories"], queryFn: () => apiRequest<Repository[]>(token, "/api/repositories") });
  const targets = useQuery({ queryKey: ["notification-targets"], queryFn: () => apiRequest<NotificationTarget[]>(token, "/api/notification-targets") });
  const readiness = useQuery({ queryKey: ["repository-readiness"], queryFn: () => apiRequest<Readiness[]>(token, "/api/repository-readiness"), refetchInterval: 10000 });
  const [open, setOpen] = useState(false);
  const [draftVersion, setDraftVersion] = useState(0);
  const [listParams, setListParams] = useSearchParams();
  const [form, setForm] = useState<RepositoryInput>(initial);
  const [editing, setEditing] = useState<Repository | null>(null);
  const [editForm, setEditForm] = useState<RepositoryUpdateInput>({});
  const [editSection, setEditSection] = useState<RepositoryEditSection>("connection");
  const [editBaseline, setEditBaseline] = useState("");
  const [reviewStatus, setReviewStatus] = useState<DraftStatus>({ dirty: false, pending: false });
  const [premergeStatus, setPremergeStatus] = useState<DraftStatus>({ dirty: false, pending: false });
  const [publicationStatus, setPublicationStatus] = useState<DraftStatus>({ dirty: false, pending: false });
  const [agentStatus, setAgentStatus] = useState<DraftStatus>({ dirty: false, pending: false });
  const editDirty = Boolean(editing) && (editContent(editForm) !== editBaseline || reviewStatus.dirty || premergeStatus.dirty || publicationStatus.dirty || agentStatus.dirty);
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
    onSuccess: (result) => {
      // 保存成功先同步清除创建草稿，防止旧离开保护拦截进入已保存项目。
      flushSync(() => { setForm(initial); setOpen(false); setFeedback("仓库已保存，请继续配置 Webhook 并验证连接。"); });
      const next = new URLSearchParams(listParams); next.set("repository", String(result.id)); next.set("section", "connection"); setListParams(next);
      void queryClient.invalidateQueries({ queryKey: ["repositories"] });
    },
  });
  const update = useMutation({
    mutationFn: async ({ id, input }: { id: number; input: RepositoryUpdateInput }) => {
      if (!editing) throw new Error("项目不存在");
      await apiRequest(token, `/api/repositories/preflight?repository_id=${id}`, { method: "POST", body: JSON.stringify({
        name: input.name ?? editing.name, gitlab_url: input.gitlab_url ?? editing.gitlab_url,
        project_id: input.project_id ?? editing.project_id,
        remote_url: input.remote_url ?? editing.remote_url,
        path_with_namespace: input.path_with_namespace ?? editing.path_with_namespace,
        target_branch: input.target_branches?.[0] ?? input.target_branch ?? editing.target_branch,
        target_branches: input.target_branches ?? editing.target_branches ?? [editing.target_branch],
        auth_kind: input.auth_kind ?? editing.auth_kind,
        webhook_token: input.webhook_token || undefined,
        gitlab_token: input.gitlab_token || undefined,
        feishu_target_id: input.feishu_target_id ?? undefined,
        enable_merge_requests: input.enable_merge_requests ?? Boolean(editing.enable_merge_requests),
        enable_default_branch_pushes: input.enable_default_branch_pushes ?? Boolean(editing.enable_default_branch_pushes),
      }) });
      return apiRequest<Repository>(token, `/api/repositories/${id}`, { method: "POST", body: JSON.stringify(input) });
    },
    onSuccess: (result, { input }) => {
      // 仅更新基础配置基线并清除已提交密钥，其他页签草稿继续保留。
      if (input.webhook_token || input.auth_kind !== editing?.auth_kind) setTokenRevision((current) => current + 1);
      const saved = { ...input }; delete saved.gitlab_token; delete saved.webhook_token; delete saved.query_session_id;
      setEditing(result); setEditForm(saved); setEditBaseline(editContent(saved));
      void queryClient.invalidateQueries({ queryKey: ["repositories"] });
      void queryClient.invalidateQueries({ queryKey: ["repository-readiness"] });
      void queryClient.invalidateQueries({ queryKey: ["premerge-setting", result.id] });
      void queryClient.invalidateQueries({ queryKey: ["effective-configuration"] });
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
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) => apiRequest<Repository>(token, `/api/repositories/${id}`, { method: "POST", body: JSON.stringify({ enabled }) }),
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
      mutation.mutate({ ...form, target_branch: form.target_branches?.[0] ?? form.target_branch, enable_merge_requests: false, gitlab_url: clone.origin, auth_kind: "secret" });
    } catch {
      setFeedback("Clone URL 必须是完整的 HTTPS 地址");
    }
  }

  function field<K extends keyof RepositoryInput>(key: K, value: RepositoryInput[K]) {
    setDraftVersion((value) => value + 1);
    setForm((current) => ({ ...current, [key]: value, ...(["remote_url", "gitlab_token"].includes(key) ? { query_session_id: undefined } : {}) }));
  }

  const resetUpdate = update.reset, resetRotate = rotate.reset;
  const loadEditor = useCallback((repo: Repository) => {
    setEditing(repo);
    setEditSection("connection");
    setReviewStatus({ dirty: false, pending: false }); setPremergeStatus({ dirty: false, pending: false });
    setAgentStatus({ dirty: false, pending: false });
    const next = {
      name: repo.name,
      gitlab_url: repo.gitlab_url,
      project_id: repo.project_id,
      remote_url: repo.remote_url,
      path_with_namespace: repo.path_with_namespace,
      target_branch: repo.target_branch,
      target_branches: repo.target_branches ?? [repo.target_branch],
      auth_kind: repo.auth_kind,
      feishu_target_id: repo.feishu_target_id,
      enable_merge_requests: false,
      enable_default_branch_pushes: Boolean(repo.enable_default_branch_pushes),
      premerge_enabled: Boolean(repo.premerge_enabled),
    };
    setEditForm(next); setEditBaseline(editContent(next));
    resetUpdate();
    resetRotate();
  }, [resetUpdate, resetRotate]);

  function beginEdit(repo: Repository) { const next = new URLSearchParams(listParams); next.set("repository", String(repo.id)); next.set("section", "connection"); setListParams(next); }
  const targetId = Number(listParams.get("repository"));
  const targetSection = listParams.get("section");
  useEffect(() => {
    const repo = query.data?.find((item) => item.id === targetId);
    if (repo && editing?.id !== repo.id) loadEditor(repo);
    if (!targetId && editing) { setEditing(null); setEditForm({}); }
    if (["connection", "review", "agent", "publication", "diagnosis"].includes(targetSection ?? "")) setEditSection(targetSection as RepositoryEditSection);
  }, [targetId, targetSection, query.data, editing, loadEditor]);
  function selectSection(section: RepositoryEditSection) { const next = new URLSearchParams(listParams); next.set("section", section); setListParams(next, { replace: true }); }

  useLayoutEffect(() => { if (editorBody.current) editorBody.current.scrollTop = 0; }, [editSection, editing?.id]);

  const editPending = update.isPending || reviewStatus.pending || premergeStatus.pending || publicationStatus.pending || agentStatus.pending;
  function closeAdd() { if (!mutation.isPending && confirmDiscard(JSON.stringify(form) !== JSON.stringify(initial))) { setOpen(false); setForm(initial); } }
  function closeEditor() { if (editPending || (!hasDataRouter && !confirmDiscard(editDirty))) return; const next = new URLSearchParams(listParams); next.delete("repository"); next.delete("section"); setListParams(next); }

  function submitEdit(event: FormEvent) {
    event.preventDefault();
    if (!editing) return;
    const input = { ...editForm, target_branch: editForm.target_branches?.[0] ?? editForm.target_branch, enable_merge_requests: false };
    if (!input.target_branches?.length) { setFeedback("请至少选择一个目标分支"); return; }
    const connectionChanged = input.remote_url !== editing.remote_url || Boolean(input.gitlab_token) || JSON.stringify(input.target_branches) !== JSON.stringify(editing.target_branches ?? [editing.target_branch]);
    if (!connectionChanged) delete input.query_session_id;
    else if (!input.query_session_id) { setFeedback("请等待仓库识别与分支查询完成后保存"); return; }
    if (!input.gitlab_token) delete input.gitlab_token;
    if (!input.webhook_token) delete input.webhook_token;
    update.mutate({ id: editing.id, input });
  }

  async function copyCallback(url: string) {
    setCopyError(""); setCallbackCopied(false);
    try { await copyText(url); setCallbackCopied(true); }
    catch { setCopyError("复制失败，请手动选择回调地址"); }
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

  const readinessFilter = listParams.get("repo_readiness") ?? "all";
  const targetFilter = listParams.get("repo_target") ?? "all";
  const getReadiness = (id: number) => !readiness.isSuccess || readiness.error ? "unknown" : readiness.data.find((item) => item.repository_id === id)?.status ?? "unknown";
  const scoped = query.error ? undefined : query.data?.filter((item) => (readinessFilter === "all" || getReadiness(item.id) === readinessFilter) && (targetFilter === "all" || (targetFilter === "none" ? item.feishu_target_id == null : String(item.feishu_target_id) === targetFilter)));
  const list = useLocalList(scoped, (item) => `${item.name} ${item.path_with_namespace} ${item.project_id}`, (item) => item.enabled ? "enabled" : "disabled", "repo_");
  const [info, setInfo] = useState<Repository | null>(null);
  const repositoryColumns: TableColumnsType<Repository> = [
    { title: "仓库", dataIndex: "name", key: "name", width: 210, render: (name: string, repo) => <div className="repository-name-cell"><strong>{name}</strong><small className="table-sub">{repo.path_with_namespace || repo.gitlab_url} · ID {repo.project_id}</small></div> },
    { title: "目标分支", key: "target_branch", width: 180, render: (_: unknown, repo) => <div className="repository-branch-tags">{(repo.target_branches ?? [repo.target_branch]).map((branch) => <Tag key={branch} className="mono">{branch}</Tag>)}</div> },
    { title: "接入状态", key: "readiness", width: 135, render: (_: unknown, repo) => { const result = !readiness.error ? readiness.data?.find((item) => item.repository_id === repo.id) : undefined; const label = readiness.isSuccess && !readiness.error ? result ? ({ ready: "已验证", needs_check: "待重新测试", paused: "已暂停" } as Record<string, string>)[result.status] : "接入状态未知" : "接入状态待确认"; return <Tag variant="filled" color={result?.status === "ready" ? "green" : "default"}>{label}</Tag>; } },
    { title: "飞书配置", key: "feishu", width: 170, render: (_: unknown, repo) => repo.feishu_target_id == null ? "未配置" : !targets.isSuccess ? "飞书配置待确认" : targets.data.find((target) => target.id === repo.feishu_target_id)?.name ?? "关联通道不存在，请核对" },
    { title: "接收", dataIndex: "enabled", key: "enabled", width: 86, render: (enabled: number, repo) => <Switch checked={Boolean(enabled)} disabled={toggle.isPending} onChange={(checked) => toggle.mutate({ id: repo.id, enabled: checked })} aria-label={`${repo.name} 接收 webhook`} /> },
    { title: "操作", key: "actions", width: 240, render: (_: unknown, repo) => <div className="row-actions"><Button type="link" onClick={() => setInfo(repo)}>接入信息</Button><Button type="text" title="编辑仓库设置" aria-label={`编辑 ${repo.name}`} onClick={() => beginEdit(repo)}>编辑</Button><Button danger type="text" title="删除项目配置" aria-label={`删除 ${repo.name}`} onClick={() => deleteRepository(repo)} disabled={remove.isPending}>删除</Button></div> },
  ];

  return <div className="page"><UnsavedChangesGuard preserveSearchKeys={["section"]} dirty={editDirty || (open && JSON.stringify(form) !== JSON.stringify(initial))} /><PageHeader title="项目配置" subtitle="GitLab 仓库、Webhook 与评审开关" actions={
    <div className="row-actions"><RouteButton to="/onboarding">项目接入清单</RouteButton><Button type="primary" icon={<Plus size={17} />} onClick={() => setOpen(true)}>添加仓库</Button></div>
  } /><QueryState loading={query.isLoading} error={query.error} onRetry={() => void query.refetch()} />
    <ReadFeedback name="接入状态" loading={readiness.isPending} error={readiness.error} onRetry={() => void readiness.refetch()} />
    <ReadFeedback name="飞书配置" loading={targets.isPending} error={targets.error} onRetry={() => void targets.refetch()} />{!query.isLoading && !query.error && <>
    {query.data?.some((repo) => getReadiness(repo.id) === "needs_check") && <p className="coverage-note">有项目尚未验证当前连接配置。<RouteButton to="/onboarding">继续接入清单</RouteButton></p>}
    {callbackUrl && <section className="repository-callback-panel" aria-label="GitLab Webhook 接入地址"><div className="repository-callback-heading"><div><h2>GitLab 回调地址</h2><p>所有项目共用此地址；每个项目使用各自的 Secret。</p></div><Tag>Webhook</Tag></div><div className="repository-callback-control"><Input aria-label="GitLab 回调地址" className="mono" value={callbackUrl} readOnly onFocus={(event) => event.target.select()} /><Button icon={callbackCopied ? <Check size={16} /> : <Copy size={16} />} onClick={() => void copyCallback(callbackUrl)}>{callbackCopied ? "已复制" : "复制地址"}</Button></div>{copyError && <p className="form-error" role="alert">{copyError}</p>}<p className="form-note">在 GitLab → Settings → Webhooks 配置；勾选 Merge request events 接收合并前评审，勾选 Push events 接收目标分支变更。</p></section>}

    <Card className="repository-table-card" size="small" title={<h2 className="repository-table-heading">已接入仓库</h2>} extra={query.data ? `${query.data.length} 个` : "数量待确认"}>
<div className="list-toolbar"><ListSearch key={list.q} label="搜索项目" value={list.q} onSearch={(value) => list.update("q", value)} />
  <ListSelect label="接入验证" value={readinessFilter} onValueChange={(value) => list.update("readiness", value)} options={[{ value: "all", label: "全部接入状态" }, { value: "ready", label: "已验证" }, { value: "needs_check", label: "待重新测试" }, { value: "paused", label: "已暂停" }, { value: "unknown", label: "待确认 / 未知" }]} />
  <ListSelect label="关联飞书" value={targetFilter} onValueChange={(value) => list.update("target", value)} options={[{ value: "all", label: "全部关联" }, { value: "none", label: "未配置" }, ...(targets.data ?? []).map((item) => ({ value: String(item.id), label: item.name }))]} />
</div><ListStatusNav value={list.status} labels={{ all: "全部", enabled: "接收已启用", disabled: "接收已暂停" }} counts={list.counts} onChange={(value) => list.update("status", value)} />      <Table rowKey="id" columns={repositoryColumns} dataSource={list.filtered ?? []} loading={query.isFetching} locale={{ emptyText: query.error ? "无法读取项目配置" : "尚未接入仓库" }} scroll={{ x: 1180 }} pagination={list.pagination} />
    </Card></>}
      {feedback && <p className="form-success" role="status">{feedback}</p>}
      {(toggle.error || remove.error) && <p className="form-error" role="alert">{(toggle.error || remove.error)?.message}</p>}
  <Drawer open={info !== null} title={info ? `${info.name} · 接入信息` : "接入信息"} onClose={() => setInfo(null)} destroyOnHidden>
    {info && <><p>Webhook Token 默认遮罩，仅在主动查看时读取；请勿写入 URL 或日志。</p><WebhookTokenCell key={`${info.id}-${tokenRevision}`} token={token} repositoryId={info.id} repositoryName={info.name} /><p>最近 Token 验证：{formatTime(info.last_webhook_at)}</p><p className="form-note">接入验证与接收开关独立，测试通过不代表后续任务一定成功。</p></>}
  </Drawer>
  {open && <Modal titleId="add-repo-title" onClose={closeAdd}><div className="modal-heading"><h2 id="add-repo-title">添加 GitLab 仓库</h2><button className="icon-button" type="button" aria-label="关闭" title="关闭" onClick={closeAdd}><X size={19} /></button></div>
    <RepositoryCreateForm token={token} form={form} draftVersion={draftVersion} targets={targets.data ?? []} pending={mutation.isPending} error={mutation.error} onField={field} onMetadata={(metadata) => setForm((current) => ({ ...current, ...metadata, remote_url: current.remote_url, target_branch: current.target_branch || metadata.target_branch, target_branches: current.target_branches?.length ? current.target_branches : [metadata.target_branch] }))} onSubmit={submit} onCancel={closeAdd} />
  </Modal>}
  {editing && <Modal titleId="edit-repo-title" className="modal-wide repository-editor-modal" onClose={closeEditor}><div className="modal-heading"><h2 id="edit-repo-title">编辑 {editing.name}</h2><button className="icon-button" type="button" aria-label="关闭" title="关闭" onClick={closeEditor} disabled={editPending}><X size={19} /></button></div>
    <div className="repository-editor-tabs" role="tablist" aria-label="仓库设置">
      <button className={`repository-editor-tab${editSection === "connection" ? " is-active" : ""}`} type="button" role="tab" aria-selected={editSection === "connection"} onClick={() => selectSection("connection")}>基础接入</button>
      <button className={`repository-editor-tab${editSection === "review" ? " is-active" : ""}`} type="button" role="tab" aria-selected={editSection === "review"} onClick={() => selectSection("review")}>评审参数</button>
      <Button type={editSection === "agent" ? "primary" : "text"} role="tab"
        aria-selected={editSection === "agent"} onClick={() => selectSection("agent")}>自建 Agent</Button>
      <button className={`repository-editor-tab${editSection === "publication" ? " is-active" : ""}`} type="button" role="tab" aria-selected={editSection === "publication"} onClick={() => selectSection("publication")}>结果发布</button>
      <button className={`repository-editor-tab${editSection === "diagnosis" ? " is-active" : ""}`} type="button" role="tab" aria-selected={editSection === "diagnosis"} onClick={() => selectSection("diagnosis")}>接入诊断</button>
    </div>
    <div className="repository-editor-body" ref={editorBody}>
    <form hidden={editSection !== "connection"} onSubmit={submitEdit} className="form-grid repository-main-form"><fieldset className="configuration-fields form-grid wide" disabled={update.isPending}>
      <RepositoryConnectionFields token={token} repositoryId={editing.id} remoteUrl={editForm.remote_url ?? editing.remote_url} gitlabToken={editForm.gitlab_token ?? ""} branches={editForm.target_branches ?? editing.target_branches ?? [editing.target_branch]} disabled={update.isPending} onRemote={(value) => setEditForm((current) => ({ ...current, remote_url: value, query_session_id: undefined }))} onToken={(value) => setEditForm((current) => ({ ...current, gitlab_token: value, query_session_id: undefined }))} onBranches={(value) => setEditForm((current) => ({ ...current, target_branches: value, target_branch: value[0] ?? "" }))} onResolved={(metadata) => setEditForm((current) => ({ ...current, ...metadata, remote_url: current.remote_url, target_branch: current.target_branch ?? editing.target_branch }))} />
      <label className="wide">飞书配置<Select aria-label="飞书配置" value={editForm.feishu_target_id ?? 0} disabled={update.isPending} onChange={(value) => setEditForm((current) => ({ ...current, feishu_target_id: value || null }))} options={[{ value: 0, label: "暂不关联" }, ...(targets.data ?? []).map((target) => ({ value: target.id, label: target.name }))]} /></label>
      <div className="repository-trigger-options wide" role="group" aria-label="评审触发方式">
      <Checkbox checked={editForm.premerge_enabled ?? false} disabled={update.isPending} onChange={(event) => setEditForm((current) => ({ ...current, premerge_enabled: event.target.checked }))}>合并前 MR 评审</Checkbox>
      <Checkbox checked={editForm.enable_default_branch_pushes ?? false} disabled={update.isPending} onChange={(event) => setEditForm((current) => ({ ...current, enable_default_branch_pushes: event.target.checked }))}>目标分支 Push 评审</Checkbox></div>
      <p className="form-note wide">同版本已有合并前任务时自动复用；未关联飞书配置时不发送通知。</p>
      <h3 className="form-section-title wide">GitLab Webhook</h3>
      <SelectField label="鉴权方式" value={editForm.auth_kind ?? editing.auth_kind} onValueChange={(value) => setEditForm((current) => ({ ...current, auth_kind: value === "signing" ? "signing" : "secret" }))} options={[{ value: "secret", label: "Secret token" }, { value: "signing", label: "Signing token" }]} />
      <label>新 Webhook Token<input type="password" autoComplete="new-password" value={editForm.webhook_token ?? ""} onChange={(event) => setEditForm((current) => ({ ...current, webhook_token: event.target.value }))} placeholder="留空则保留" required={editForm.auth_kind === "signing" && editing.auth_kind !== "signing"} /></label>
      <div className="webhook-editor wide"><div className="webhook-editor-callback"><span>回调地址</span><code>{editing.webhook_url}</code></div><div><span>当前 Token</span><WebhookTokenCell key={`${editing.id}-${tokenRevision}`} token={token} repositoryId={editing.id} repositoryName={editing.name} /></div><button className="button button-secondary" type="button" disabled={rotate.isPending || editing.auth_kind !== "secret"} onClick={() => rotateToken(editing)}><RotateCcw size={16} />重新生成 Secret</button></div>
      {rotate.error && <p className="form-error wide" role="alert">{rotate.error.message}</p>}
      {rotate.isSuccess && <p className="form-success wide" role="status">Secret 已更新，请同步修改 GitLab Webhook</p>}
      <div className="repository-form-checks wide"><ConnectionChecks token={token} kinds={["git", "gitlab"]} repositoryId={editing.id} enabled={editContent(editForm) === editBaseline} /></div>
      {update.error && <p className="form-error wide" role="alert">{update.error.message}</p>}
      {editContent(editForm) !== editBaseline && <p className="unsaved-note wide" role="status">基础接入有未保存的更改；保存基础接入只影响本分区。</p>}
      <div className="form-actions repository-form-actions wide"><button type="button" className="button button-secondary" onClick={closeEditor} disabled={editPending}>取消</button><button type="submit" className="button button-primary" disabled={update.isPending}>保存基础接入</button></div>
      {update.isSuccess && editContent(editForm) === editBaseline && <p className="form-success wide" role="status">基础接入配置已保存</p>}
    </fieldset></form>
    <div hidden={editSection !== "review"} className="repository-editor-panel repository-editor-stack"><EffectiveConfiguration token={token} repositoryId={editing.id} /><ProjectReviewLimits token={token} repositoryId={editing.id} onStatusChange={setReviewStatus} /><PremergeSetting token={token} repositoryId={editing.id} targetBranch={(editing.target_branches ?? [editing.target_branch]).join("、")} contextOnly onOpenDiagnosis={() => selectSection("diagnosis")} onStatusChange={setPremergeStatus} /></div>
    <div hidden={editSection !== "agent"} className="repository-editor-panel">
      {(editSection === "agent" || agentStatus.dirty || agentStatus.pending) && <ProjectAgentSettings
        key={editing.id} token={token} repositoryId={editing.id} onStatusChange={setAgentStatus} />}
    </div>
    <div hidden={editSection !== "publication"} className="repository-editor-panel"><GitLabPublicationSetting token={token} repositoryId={editing.id} onStatusChange={setPublicationStatus} /></div>
    <div hidden={editSection !== "diagnosis"} className="repository-editor-panel"><RepositoryDiagnosis token={token} repository={editing} targets={targets.data ?? []} /></div>
    </div>
  </Modal>}
  </div>;
}
