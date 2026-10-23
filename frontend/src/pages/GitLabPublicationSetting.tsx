/** @description GitLab 行内发布单独授权，默认关闭且不会改动飞书投递。 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiRequest } from "../api/client";
import { useDraftStatus } from "../ui/useConfigurationDraft";
import type { DraftStatus } from "../ui/useConfigurationDraft";
import { QueryState } from "../ui/QueryState";

/** 项目编辑时显示当前授权；关闭后待发布项暂停。 */
export function GitLabPublicationSetting({ token, repositoryId, onStatusChange }: {
  /** 内存口令。 */ token: string;
  /** 项目 ID。 */ repositoryId: number;
  /** 自动保存期间阻止外层关闭。 */ onStatusChange?: (status: DraftStatus) => void;
}) {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["gitlab-publication", repositoryId], queryFn: () => apiRequest<{ enabled: boolean }>(token, `/api/repositories/${repositoryId}/gitlab-publication`) });
  const save = useMutation({ mutationFn: (enabled: boolean) => apiRequest(token, `/api/repositories/${repositoryId}/gitlab-publication`, { method: "PUT", body: JSON.stringify({ enabled }) }), onSuccess: () => void client.invalidateQueries({ queryKey: ["gitlab-publication", repositoryId] }) });
  useDraftStatus(false, save.isPending, onStatusChange);
  return <section className="section"><div className="section-head"><h3>GitLab 行内评论</h3></div><QueryState loading={query.isLoading} error={query.error} onRetry={() => void query.refetch()} /><label className="checkbox-label"><input type="checkbox" checked={query.data?.enabled ?? false} disabled={save.isPending || !query.data} onChange={(event) => save.mutate(event.target.checked)} />向 MR 发布可定位的评审发现</label><small>修改后自动保存。</small>{save.isPending && <p role="status">保存中…</p>}{save.error && <p className="form-error" role="alert">保存失败：{save.error.message}；请重新操作开关。</p>}{save.isSuccess && <p className="form-success" role="status">行内评论配置已保存</p>}</section>;
}
