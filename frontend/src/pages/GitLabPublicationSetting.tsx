/** @description GitLab 行内发布单独授权，默认关闭且不会改动飞书投递。 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiRequest } from "../api/client";
import { QueryState } from "../ui/QueryState";

/** 项目编辑时显示当前授权；关闭后待发布项暂停。 */
export function GitLabPublicationSetting({ token, repositoryId }: {
  /** 内存口令。 */ token: string;
  /** 项目 ID。 */ repositoryId: number;
}) {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["gitlab-publication", repositoryId], queryFn: () => apiRequest<{ enabled: boolean }>(token, `/api/repositories/${repositoryId}/gitlab-publication`) });
  const save = useMutation({ mutationFn: (enabled: boolean) => apiRequest(token, `/api/repositories/${repositoryId}/gitlab-publication`, { method: "PUT", body: JSON.stringify({ enabled }) }), onSuccess: () => void client.invalidateQueries({ queryKey: ["gitlab-publication", repositoryId] }) });
  return <section className="section"><div className="section-head"><h3>GitLab 行内评论</h3></div><QueryState loading={query.isLoading} error={query.error || save.error} /><label className="checkbox-label"><input type="checkbox" checked={query.data?.enabled ?? false} disabled={save.isPending || query.isLoading} onChange={(event) => save.mutate(event.target.checked)} />向 MR 发布可定位的评审发现</label></section>;
}
