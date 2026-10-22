/** @description 评审任务页的 MR 补触发入口；Worker 负责确认合并状态和生成任务。 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { GitPullRequest } from "lucide-react";
import { useState } from "react";

import { enqueueMergedMrs } from "../api/tasks";
import type { Repository } from "../api/types";
import { SelectField } from "../ui/SelectField";

interface MrTriggerProps {
  /** 内存中的管理口令。 */
  token: string;
  /** 管理员可选择的仓库，禁用仓库不会参与补触发。 */
  repositories: Repository[];
}

/** 按仓库和 MR IID 补建漏失的合并事件，由 Worker 复核后生成评审任务。 */
export function MrBatchEnqueue({ token, repositories }: MrTriggerProps) {
  const [repository, setRepository] = useState("");
  const [mrIids, setMrIids] = useState("");
  const client = useQueryClient();
  const enabledRepositories = repositories.filter((item) => Boolean(item.enabled));
  const enqueue = useMutation({
    mutationFn: () => enqueueMergedMrs(token, repository, mrIids.split(/[\s,，]+/).filter(Boolean).map(Number)),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["jobs"] }),
  });

  return <section className="task-command-bar" aria-labelledby="batch-enqueue-title"><h2 id="batch-enqueue-title">补触发已合并 MR</h2><form onSubmit={(event) => { event.preventDefault(); enqueue.mutate(); }}>
    <SelectField label="仓库" value={repository} onValueChange={setRepository} placeholder="选择仓库" required options={enabledRepositories.map((item) => ({ value: String(item.id), label: item.name }))} />
    <label>MR IID<input value={mrIids} onChange={(event) => setMrIids(event.target.value)} placeholder="7, 8, 9" required /></label>
    <button className="button button-secondary" disabled={enqueue.isPending || !repository}><GitPullRequest size={16} />补触发 MR</button>
  </form>{enqueue.error && <p className="form-error" role="alert">{enqueue.error.message}</p>}{enqueue.data && <ul aria-live="polite">{enqueue.data.map((item) => <li key={item.id}>MR !{item.id}：{item.status === "queued" ? "已加入队列" : "重复或无法补触发"}</li>)}</ul>}</section>;
}
