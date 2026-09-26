/** @description 项目级合并前审查授权；服务端独立检查开关与 MR 版本。 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiRequest } from "../api/client";
import { QueryState } from "../ui/QueryState";

/** 仅控制界面操作，Webhook 与 Worker 仍在服务端执行授权。 */
export function PremergeSetting({ token, repositoryId }: {
  /** 内存口令。 */ token: string;
  /** 项目 ID。 */ repositoryId: number;
}) {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["premerge-setting", repositoryId], queryFn: () => apiRequest<{ enabled: boolean }>(token, `/api/repositories/${repositoryId}/premerge`) });
  const save = useMutation({
    mutationFn: (enabled: boolean) => apiRequest(token, `/api/repositories/${repositoryId}/premerge`, { method: "PUT", body: JSON.stringify({ enabled }) }),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["premerge-setting", repositoryId] }),
  });
  return <section className="section"><div className="section-head"><h3>合并前审查</h3></div><QueryState loading={query.isLoading} error={query.error || save.error} /><label className="checkbox-label"><input type="checkbox" checked={query.data?.enabled ?? false} disabled={save.isPending || query.isLoading} onChange={(event) => save.mutate(event.target.checked)} />审查未合并 MR 的完整差异</label></section>;
}
