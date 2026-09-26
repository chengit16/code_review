/** @description 项目执行参数单独保存；保持与仓库身份编辑解耦。 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Save } from "lucide-react";
import { useState } from "react";

import { apiRequest } from "../api/client";
import type { ModelConfiguration } from "../api/types";
import { QueryState } from "../ui/QueryState";
import { SelectField } from "../ui/SelectField";

interface Limits { model_profile_id: number | null; timeout_seconds: number | null; max_files: number | null; max_tokens_budget: number | null }

function Form({ token, repositoryId, value, models }: { token: string; repositoryId: number; value: Limits; models: ModelConfiguration[] }) {
  const [draft, setDraft] = useState(value);
  const client = useQueryClient();
  const save = useMutation({ mutationFn: () => apiRequest(token, `/api/repositories/${repositoryId}/limits`, { method: "PUT", body: JSON.stringify(draft) }), onSuccess: () => void client.invalidateQueries({ queryKey: ["project-limits", repositoryId] }) });
  function numberField(key: "timeout_seconds" | "max_files" | "max_tokens_budget", value: string) { setDraft((current) => ({ ...current, [key]: value ? Number(value) : null })); }
  return <form className="form-grid" onSubmit={(event) => { event.preventDefault(); save.mutate(); }}><SelectField label="Agent 模型" value={draft.model_profile_id ? String(draft.model_profile_id) : "global"} onValueChange={(value) => setDraft((current) => ({ ...current, model_profile_id: value === "global" ? null : Number(value) }))} options={[{ value: "global", label: "继承全局启用模型" }, ...models.map((model) => ({ value: String(model.id), label: model.name }))]} /><label>超时（秒）<input type="number" min="60" max="14400" placeholder="继承全局" value={draft.timeout_seconds ?? ""} onChange={(event) => numberField("timeout_seconds", event.target.value)} /></label><label>最多文件数<input type="number" min="1" max="5000" placeholder="不限制" value={draft.max_files ?? ""} onChange={(event) => numberField("max_files", event.target.value)} /></label><label>Token 预算<input type="number" min="1000" max="100000000" placeholder="不限制" value={draft.max_tokens_budget ?? ""} onChange={(event) => numberField("max_tokens_budget", event.target.value)} /></label><div className="form-actions wide"><button className="button button-secondary" disabled={save.isPending}><Save size={16} />保存评审参数</button></div>{save.error && <p role="alert" className="form-error wide">{save.error.message}</p>}{save.isSuccess && <p role="status" className="form-success wide">评审参数已保存</p>}</form>;
}

/** 仅在项目编辑时请求；模型密钥仍归 Agent 模型页面维护。 */
export function ProjectReviewLimits({ token, repositoryId }: { /** 内存口令。 */ token: string; /** 项目 ID。 */ repositoryId: number }) {
  const limits = useQuery({ queryKey: ["project-limits", repositoryId], queryFn: () => apiRequest<Limits>(token, `/api/repositories/${repositoryId}/limits`) });
  const models = useQuery({ queryKey: ["model-profiles"], queryFn: () => apiRequest<ModelConfiguration[]>(token, "/api/model-profiles") });
  return <section className="section"><div className="section-head"><h3>项目评审参数</h3></div><QueryState loading={limits.isLoading || models.isLoading} error={limits.error || models.error} />{limits.data && <Form key={JSON.stringify(limits.data)} token={token} repositoryId={repositoryId} value={limits.data} models={models.data ?? []} />}</section>;
}
