/** @description 项目级合并前审查与背景来源配置；服务端复核 MR 和仓库文档。 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { apiRequest } from "../api/client";
import { QueryState } from "../ui/QueryState";

/** 仅控制界面操作，Webhook 与 Worker 仍在服务端执行授权。 */
export function PremergeSetting({ token, repositoryId }: {
  /** 内存口令。 */ token: string;
  /** 项目 ID。 */ repositoryId: number;
}) {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["premerge-setting", repositoryId], queryFn: () => apiRequest<{ enabled: boolean; include_description: boolean; context_paths: string[] }>(token, `/api/repositories/${repositoryId}/premerge`) });
  const [enabled, setEnabled] = useState(false);
  const [includeDescription, setIncludeDescription] = useState(false);
  const [paths, setPaths] = useState("");
  useEffect(() => {
    if (!query.data) return;
    setEnabled(query.data.enabled);
    setIncludeDescription(query.data.include_description);
    setPaths(query.data.context_paths.join("\n"));
  }, [query.data]);
  const save = useMutation({
    mutationFn: () => apiRequest(token, `/api/repositories/${repositoryId}/premerge`, { method: "PUT", body: JSON.stringify({ enabled, include_description: includeDescription, context_paths: paths.split("\n").map((path) => path.trim()).filter(Boolean) }) }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["premerge-setting", repositoryId] });
      void client.invalidateQueries({ queryKey: ["premerge-reviews"] });
    },
  });
  return <section className="section"><div className="section-head"><h3>合并前审查</h3></div><QueryState loading={query.isLoading} error={query.error || save.error} />
    <label className="checkbox-label"><input type="checkbox" checked={enabled} disabled={save.isPending || query.isLoading} onChange={(event) => setEnabled(event.target.checked)} />审查未合并 MR 的完整差异</label>
    <label className="checkbox-label"><input type="checkbox" checked={includeDescription} disabled={save.isPending || query.isLoading} onChange={(event) => setIncludeDescription(event.target.checked)} />包含 GitLab MR 描述</label>
    <label className="field premerge-context-paths">仓库业务文档路径，每行一份，最多 3 份<textarea aria-label="仓库业务文档路径" rows={3} value={paths} onChange={(event) => setPaths(event.target.value)} placeholder="docs/review-context.md" disabled={save.isPending || query.isLoading} /></label>
    <button className="button button-secondary" type="button" disabled={save.isPending || query.isLoading} onClick={() => save.mutate()}>保存合并前配置</button>
  </section>;
}
