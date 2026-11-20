/** @description 管理 OCR 全局兜底规则与项目显式覆盖规则。 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Collapse, Select, Tag } from "antd";
import { History, RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import { useSearchParams } from "react-router-dom";

import { apiRequest } from "../api/client";
import type { Repository, ReviewRuleConfiguration, ReviewRuleDocument, ReviewRuleRevision } from "../api/types";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { formatTime } from "../ui/format";
import { RulePreviewPanel } from "./RulePreviewPanel";
import { ReviewFeedbackPanel } from "./ReviewFeedbackPanel";
import { UnsavedChangesGuard } from "../ui/UnsavedChangesGuard";
import { ReviewRuleEditor } from "./ReviewRuleEditor";

import "../styles/review-rules.css";

const emptyRule = (): ReviewRuleDocument => ({ include: [], exclude: [], rules: [] });
const lines = (value: string) => value.split("\n").map((item) => item.trim()).filter(Boolean);

/** 编排规则编辑、预览和版本恢复；规则写入保护由服务端执行。 */
export function ReviewRulesPage({ token, embedded = false }: {
  /** 内存中的管理口令。 */ token: string;
  /** 嵌入系统设置时使用二级标题和内容布局。 */ embedded?: boolean;
}) {
  const queryClient = useQueryClient();
  const repositories = useQuery({ queryKey: ["repositories"], queryFn: () => apiRequest<Repository[]>(token, "/api/repositories") });
  // 规则草稿不随窗口聚焦重新加载；只在自身保存、删除或恢复后显式失效。
  const configurations = useQuery({ queryKey: ["review-rules"], queryFn: () => apiRequest<ReviewRuleConfiguration[]>(token, "/api/review-rules"), staleTime: Infinity });
  const [scopeParams, setScopeParams] = useSearchParams();
  const scope = /^\d+$/.test(scopeParams.get("repository") ?? "") ? scopeParams.get("repository") ?? "global" : "global";
  const setScope = (value: string) => { const next = new URLSearchParams(scopeParams); if (value === "global") next.delete("repository"); else next.set("repository", value); setScopeParams(next); };
  const [form, setForm] = useState<ReviewRuleDocument>(emptyRule);
  const [includeText, setIncludeText] = useState("");
  const [excludeText, setExcludeText] = useState("");
  const [feedback, setFeedback] = useState("");
  const [localError, setLocalError] = useState("");
  const repositoryId = scope === "global" ? null : Number(scope);
  const current = configurations.data?.find((item) => item.repository_id === repositoryId);
  const baseline = current?.content ?? emptyRule();
  const dirty = JSON.stringify(form.rules) !== JSON.stringify(baseline.rules)
    || JSON.stringify(lines(includeText)) !== JSON.stringify(baseline.include)
    || JSON.stringify(lines(excludeText)) !== JSON.stringify(baseline.exclude);

  useEffect(() => {
    const saved = configurations.data?.find((item) => item.repository_id === repositoryId);
    // 规则是固定 JSON 结构，显式复制避免依赖较新的全局克隆 API，也不共享缓存中的数组。
    setForm(saved ? { include: [...saved.content.include], exclude: [...saved.content.exclude],
      rules: saved.content.rules.map((rule) => ({ ...rule })) } : emptyRule());
    setIncludeText(saved?.content.include.join("\n") ?? "");
    setExcludeText(saved?.content.exclude.join("\n") ?? "");
    setLocalError("");
  }, [repositoryId, configurations.data]);

  const endpoint = repositoryId === null ? "/api/review-rules/global" : `/api/review-rules/repositories/${repositoryId}`;
  const revisions = useQuery({ queryKey: ["review-rule-revisions", scope], queryFn: () => apiRequest<ReviewRuleRevision[]>(token, `${endpoint}/revisions`) });
  const save = useMutation({
    mutationFn: (value: ReviewRuleDocument) => apiRequest<{ status: string }>(token, endpoint, { method: "PUT", body: JSON.stringify(value) }),
    onSuccess: () => { remove.reset(); setFeedback("审核规则已保存"); void queryClient.invalidateQueries({ queryKey: ["review-rules"] }); void queryClient.invalidateQueries({ queryKey: ["review-rule-revisions", scope] }); },
  });
  const remove = useMutation({
    mutationFn: () => apiRequest<{ status: string }>(token, endpoint, { method: "DELETE" }),
    onSuccess: () => { save.reset(); setFeedback("当前配置已删除"); void queryClient.invalidateQueries({ queryKey: ["review-rules"] }); void queryClient.invalidateQueries({ queryKey: ["review-rule-revisions", scope] }); },
  });
  const restore = useMutation({
    mutationFn: (revisionId: number) => apiRequest<{ status: string }>(token, `${endpoint}/revisions/${revisionId}/restore`, { method: "POST" }),
    onSuccess: () => { setFeedback("历史版本已恢复"); void queryClient.invalidateQueries({ queryKey: ["review-rules"] }); void queryClient.invalidateQueries({ queryKey: ["review-rule-revisions", scope] }); },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    setLocalError("");
    setFeedback("");
    const rules = form.rules.map((entry) => ({ ...entry, path: entry.path.trim(), rule: entry.rule.trim() }));
    if (rules.some((entry) => !entry.path || !entry.rule)) {
      setLocalError("每条规则都需要填写路径模式和审核内容");
      return;
    }
    const include = lines(includeText);
    const exclude = lines(excludeText);
    if (!rules.length && !include.length && !exclude.length) {
      setLocalError("请至少配置一条规则或过滤路径");
      return;
    }
    save.mutate({ rules, include, exclude });
  }

  function changeScope(value: string) {

    save.reset();
    remove.reset();
    setFeedback("");
    setScope(value);
  }

  const busy = save.isPending || remove.isPending || restore.isPending;
  const scopeName = repositoryId === null ? "全局规则" : repositories.data?.find((repo) => repo.id === repositoryId)?.name ?? `项目 #${repositoryId}`;
  return <div className={`review-rules-page ${embedded ? "settings-content" : "page"}`}><PageHeader headingLevel={embedded ? 2 : 1} title="审核规则" />
    <UnsavedChangesGuard dirty={dirty} />
    <QueryState loading={repositories.isLoading || configurations.isLoading} error={repositories.error || configurations.error} onRetry={() => { void repositories.refetch(); void configurations.refetch(); }} />
    {!repositories.isLoading && !configurations.isLoading && !repositories.error && !configurations.error && <>
      <section className="rules-context" aria-label="规则配置范围">
        <div className="rules-context-row"><div className="rules-scope-control"><span>配置范围</span><Select aria-label="配置范围" value={scope} disabled={busy} virtual={false} showSearch={{ optionFilterProp: "label" }} onChange={changeScope} options={[{ value: "global", label: "全局规则" }, ...(repositories.data ?? []).map((repo) => ({ value: String(repo.id), label: repo.name }))]} /></div>
          <div className="rules-context-meta"><Tag color={current ? "blue" : "default"}>{current ? "已配置" : "使用下一级规则"}</Tag>{current && <span>更新于 {formatTime(current.updated_at)}</span>}{dirty && <Tag color="gold">未保存</Tag>}</div>
        </div>
        <div className="rules-precedence" aria-label="规则优先级"><span>优先级从高到低</span><ol><li>项目页面规则</li><li>仓库 rule.json</li><li>全局页面规则</li><li>OCR 内置规则</li></ol></div>
      </section>
      <ReviewRuleEditor value={form} includeText={includeText} excludeText={excludeText} scopeName={scopeName} configured={Boolean(current)} busy={busy} saving={save.isPending} error={localError || save.error?.message || remove.error?.message} feedback={feedback}
        onChange={setForm} onIncludeChange={setIncludeText} onExcludeChange={setExcludeText} onSubmit={submit} onDelete={() => { if (window.confirm("确定删除当前范围的审核规则配置？")) remove.mutate(); }} />
      <Collapse className="review-rule-secondary" items={[
        { key: "preview", label: "规则预览与反馈", children: <div className="review-rule-secondary-content"><ReviewFeedbackPanel token={token} repositoryId={repositoryId} /><RulePreviewPanel token={token} scopeRepositoryId={repositoryId} repositories={repositories.data ?? []} dirty={dirty} /></div> },
        { key: "history", label: "版本历史 · 最近 50 次变更", children: <section className="section rule-workspace rule-history">
        <div className="section-head"><h2><History size={18} />版本历史</h2><span>最近 50 次变更</span></div>
        <QueryState loading={revisions.isLoading} error={revisions.error} />
        {restore.error && <p className="form-error" role="alert">{restore.error.message}</p>}
        {revisions.data?.length === 0 && <p className="rule-empty">尚无历史版本</p>}
        <div className="rule-revisions">{revisions.data?.map((revision) => <div className="rule-revision" key={revision.id}>
          <div><strong>版本 #{revision.id}</strong><span>{revision.action === "deleted" ? "已删除" : revision.action === "restored" ? `已恢复自 #${revision.restored_from}` : "已保存"}</span><time>{formatTime(revision.created_at)}</time></div>
          <div className="row-actions"><Button icon={<RotateCcw size={15} />} disabled={busy} onClick={() => { if (dirty && !window.confirm("当前编辑内容尚未保存，恢复历史版本会覆盖当前配置。确定继续？")) return; if (window.confirm(`确定恢复版本 #${revision.id}？`)) restore.mutate(revision.id); }}>恢复</Button></div>
          <details><summary>查看版本内容</summary><pre>{revision.content ? JSON.stringify(revision.content, null, 2) : "该版本未配置审核规则"}</pre></details>
        </div>)}</div>
      </section> },
      ]} />
    </>}
  </div>;
}
