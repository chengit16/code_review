/**
 * @description 在目标仓库的最新目标分支提交上查看 OCR 实际命中的已保存规则。
 *
 * 请求只创建持久化诊断；Git 与 OCR 由 Worker 执行，页面轮询服务端结果。
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useState } from "react";
import type { FormEvent } from "react";

import { apiRequest } from "../api/client";
import type { Repository, RulePreview } from "../api/types";
import { SelectField } from "../ui/SelectField";
import { Status } from "../ui/Status";
import { formatTime } from "../ui/format";

interface RulePreviewPanelProps {
  /** 内存中的管理口令，只用于同源 API 请求。 */
  token: string;
  /** 全局规则可选择任意项目，项目规则固定为当前项目。 */
  scopeRepositoryId: number | null;
  /** 可用仓库列表，预览基于仓库目标分支。 */
  repositories: Repository[];
  /** 未保存编辑不能参与预览，需先保存。 */
  dirty: boolean;
}

/** 通过 Worker 查询实际命中的来源、模式与规则正文。 */
export function RulePreviewPanel({ token, scopeRepositoryId, repositories, dirty }: RulePreviewPanelProps) {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState(repositories[0]?.id ?? 0);
  const [filePath, setFilePath] = useState("");
  const repositoryId = scopeRepositoryId ?? selectedId;
  const previews = useQuery({
    queryKey: ["rule-previews", repositoryId],
    queryFn: () => apiRequest<RulePreview[]>(token, `/api/repositories/${repositoryId}/rule-previews`),
    enabled: repositoryId > 0,
    refetchInterval: (query) => query.state.data?.some((item) => item.status === "queued" || item.status === "running") ? 2000 : false,
  });
  const create = useMutation({
    mutationFn: () => apiRequest<{ id: number; status: string }>(token, `/api/repositories/${repositoryId}/rule-previews`, {
      method: "POST",
      body: JSON.stringify({ file_path: filePath.trim() }),
    }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["rule-previews", repositoryId] }),
  });
  const latest = previews.data?.[0];

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    create.mutate();
  }

  return <section className="section rule-workspace rule-preview">
    <div className="section-head"><h2><Search size={18} />规则生效预览</h2></div>
    <form className="rule-preview-form" onSubmit={handleSubmit}>
      {scopeRepositoryId === null && <SelectField label="目标项目" value={String(repositoryId)} onValueChange={(value) => setSelectedId(Number(value))} options={repositories.map((repo) => ({ value: String(repo.id), label: repo.name }))} />}
      <label>仓库内文件路径<input value={filePath} onChange={(event) => setFilePath(event.target.value)} placeholder="src/main.py" required /></label>
      <button className="button button-secondary" type="submit" disabled={repositoryId === 0 || dirty || create.isPending || !filePath.trim()}><Search size={16} />检查命中规则</button>
    </form>
    {dirty && <p className="rule-preview-note">请先保存当前编辑，再检查实际生效规则。</p>}
    {create.error && <p className="form-error" role="alert">{create.error.message}</p>}
    {previews.error && <p className="form-error" role="alert">{previews.error.message}</p>}
    {latest && <div className="rule-preview-result" aria-live="polite">
      <div className="rule-preview-meta"><Status value={latest.status} /><strong>{latest.file_path}</strong><span>{formatTime(latest.finished_at ?? latest.created_at)}</span>{latest.commit_sha && <code title={latest.commit_sha}>{latest.commit_sha.slice(0, 12)}</code>}</div>
      {latest.error && <p className="form-error">{latest.error}</p>}
      {latest.output && <pre>{latest.output}</pre>}
    </div>}
  </section>;
}
