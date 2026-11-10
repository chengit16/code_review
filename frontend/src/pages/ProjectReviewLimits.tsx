/** @description 项目执行参数单独保存；保持与仓库身份编辑解耦。 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Save } from "lucide-react";

import { apiRequest } from "../api/client";
import type { ModelConfiguration } from "../api/types";
import { QueryState } from "../ui/QueryState";
import { SelectField } from "../ui/SelectField";
import { useConfigurationDraft, useDraftStatus } from "../ui/useConfigurationDraft";
import type { DraftStatus } from "../ui/useConfigurationDraft";

interface Limits { model_profile_id: number | null; timeout_seconds: number | null; max_files: number | null; max_tokens_budget: number | null; newline_filter_enabled: boolean }

function Form({ token, repositoryId, value, models, onStatusChange }: { token: string; repositoryId: number; value: Limits; models: ModelConfiguration[]; onStatusChange?: (status: DraftStatus) => void }) {
  const state = useConfigurationDraft(value);
  const draft = state.value ?? value;
  const client = useQueryClient();
  const save = useMutation({ mutationFn: (input: Limits) => apiRequest(token, `/api/repositories/${repositoryId}/limits`, { method: "PUT", body: JSON.stringify(input) }), onSuccess: (_result, input) => { client.setQueryData(["project-limits", repositoryId], input); state.saved(); void client.invalidateQueries({ queryKey: ["effective-configuration", repositoryId] }); void client.invalidateQueries({ queryKey: ["project-limits", repositoryId] }); } });
  useDraftStatus(state.dirty, save.isPending, onStatusChange);
  function numberField(key: "timeout_seconds" | "max_files" | "max_tokens_budget", value: string) { state.setValue({ ...draft, [key]: value ? Number(value) : null }); }
  return <form className="form-grid" onSubmit={(event) => { event.preventDefault(); save.mutate(draft); }}><fieldset className="configuration-fields form-grid wide" disabled={save.isPending}><SelectField label="评审模型" value={draft.model_profile_id ? String(draft.model_profile_id) : "global"} onValueChange={(value) => state.setValue({ ...draft, model_profile_id: value === "global" ? null : Number(value) })} options={[{ value: "global", label: "继承全局默认模型" }, ...models.map((model) => ({ value: String(model.id), label: model.name }))]} /><label>超时（秒）<input type="number" min="60" max="14400" placeholder="继承全局" value={draft.timeout_seconds ?? ""} onChange={(event) => numberField("timeout_seconds", event.target.value)} /></label><label>最多文件数<input type="number" min="1" max="5000" placeholder="不限制（建议先试点 200）" value={draft.max_files ?? ""} onChange={(event) => numberField("max_files", event.target.value)} /></label><label>Token 预算<input type="number" min="1000" max="100000000" placeholder="不限制" value={draft.max_tokens_budget ?? ""} onChange={(event) => numberField("max_tokens_budget", event.target.value)} /></label><label className="wide"><span className="checkbox-label"><input type="checkbox" aria-label="自动过滤纯换行文件" checked={draft.newline_filter_enabled} onChange={(event) => state.setValue({ ...draft, newline_filter_enabled: event.target.checked })} /> 自动过滤纯换行文件</span><small>仅排除确认只有 CRLF/LF 变化的文件；逻辑、权限、类型变化仍评审，无法确认的文件保持纳入。默认关闭，开启后不代表原始全范围均由模型评审。</small></label><p className="coverage-note wide">最多文件数是正式选中范围的上限，超限会在模型调用前失败，不会截取前 N 个文件。开启换行过滤后，文件上限按双预览校验后的实际候选检查。Token 预算在请求边界检查，在途请求可能超额；请按代表性用量设置有限预算。</p><div className="form-actions wide"><button className="button button-secondary" disabled={!state.dirty}><Save size={16} />{save.isPending ? "保存中…" : "保存评审参数"}</button></div></fieldset>{state.dirty && <p className="unsaved-note wide" role="status">评审参数有未保存的更改。</p>}{save.error && <p role="alert" className="form-error wide">保存失败：{save.error.message}；草稿已保留，请重试保存。</p>}{save.isSuccess && !state.dirty && <p role="status" className="form-success wide">评审参数已保存</p>}</form>;
}

/** 仅在项目编辑时请求；模型密钥仍归 Agent 模型页面维护。 */
export function ProjectReviewLimits({ token, repositoryId, onStatusChange }: { /** 内存口令。 */ token: string; /** 项目 ID。 */ repositoryId: number; /** 汇总草稿与写入状态。 */ onStatusChange?: (status: DraftStatus) => void }) {
  const limits = useQuery({ queryKey: ["project-limits", repositoryId], queryFn: async () => { const value = await apiRequest<Limits>(token, `/api/repositories/${repositoryId}/limits`); return { ...value, newline_filter_enabled: Boolean(value.newline_filter_enabled) }; } });
  const models = useQuery({ queryKey: ["model-profiles"], queryFn: () => apiRequest<ModelConfiguration[]>(token, "/api/model-profiles") });
  return <section className="section"><div className="section-head"><h3>项目评审参数</h3></div><QueryState loading={limits.isLoading || models.isLoading} error={limits.error || models.error} onRetry={() => { void limits.refetch(); void models.refetch(); }} />{limits.data && <Form onStatusChange={onStatusChange} token={token} repositoryId={repositoryId} value={limits.data} models={models.data ?? []} />}</section>;
}
