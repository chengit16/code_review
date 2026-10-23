/** @description 项目级合并前配置；读取成功后才允许编辑，草稿不被后台刷新覆盖，服务端复核权限。 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiRequest } from "../api/client";
import { QueryState } from "../ui/QueryState";
import { useConfigurationDraft, useDraftStatus } from "../ui/useConfigurationDraft";
import type { DraftStatus } from "../ui/useConfigurationDraft";

interface Configuration { enabled: boolean; include_description: boolean; context_paths: string[] }

/** 配置独立保存，写入失败保留草稿；外层窗口负责离开确认。 */
export function PremergeSetting({ token, repositoryId, onStatusChange }: {
  /** 内存口令。 */ token: string;
  /** 项目 ID。 */ repositoryId: number;
  /** 汇总未保存与写入状态，不负责授权。 */ onStatusChange?: (status: DraftStatus) => void;
}) {
  const client = useQueryClient();
  const key = ["premerge-setting", repositoryId];
  const query = useQuery({ queryKey: key, queryFn: () => apiRequest<Configuration>(token, `/api/repositories/${repositoryId}/premerge`) });
  const draft = useConfigurationDraft(query.data);
  const save = useMutation({
    mutationFn: (input: Configuration) => apiRequest(token, `/api/repositories/${repositoryId}/premerge`, { method: "PUT", body: JSON.stringify(input) }),
    onSuccess: (_result, input) => {
      // 先更新读取基线再释放草稿，避免失效重取期间短暂回显旧配置。
      client.setQueryData(key, input);
      draft.saved();
      void client.invalidateQueries({ queryKey: key });
      void client.invalidateQueries({ queryKey: ["premerge-reviews"] });
    },
  });
  useDraftStatus(draft.dirty, save.isPending, onStatusChange);
  const value = draft.value;
  return <section className="section"><div className="section-head"><h3>合并前审查</h3></div>
    <QueryState loading={query.isLoading} error={query.error} onRetry={() => void query.refetch()} />
    {value && <><fieldset className="configuration-fields" disabled={save.isPending}>
      <label className="checkbox-label"><input type="checkbox" checked={value.enabled} onChange={(event) => draft.setValue({ ...value, enabled: event.target.checked })} />审查未合并 MR 的完整差异</label>
      <label className="checkbox-label"><input type="checkbox" checked={value.include_description} onChange={(event) => draft.setValue({ ...value, include_description: event.target.checked })} />包含 GitLab MR 描述</label>
      <label className="field premerge-context-paths">仓库业务文档路径，每行一份，最多 3 份<textarea aria-label="仓库业务文档路径" rows={3} value={value.context_paths.join("\n")} onChange={(event) => draft.setValue({ ...value, context_paths: event.target.value.split("\n") })} placeholder="docs/review-context.md" /></label>
      <button className="button button-secondary" type="button" disabled={!draft.dirty} onClick={() => save.mutate({ ...value, context_paths: value.context_paths.map((path) => path.trim()).filter(Boolean) })}>{save.isPending ? "保存中…" : "保存合并前配置"}</button>
    </fieldset>{draft.dirty && !save.isPending && <p className="unsaved-note" role="status">合并前配置有未保存的更改。</p>}</>}
    {save.error && <p className="form-error" role="alert">保存失败：{save.error.message}；草稿已保留，请重试保存。</p>}
    {save.isSuccess && !draft.dirty && <p className="form-success" role="status">合并前配置已保存</p>}
  </section>;
}
