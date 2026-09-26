/** @description 管理 OCR 全局兜底规则与项目显式覆盖规则。 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, History, Plus, RotateCcw, Save, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import { apiRequest } from "../api/client";
import type { Repository, ReviewRuleConfiguration, ReviewRuleDocument, ReviewRuleRevision } from "../api/types";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { SelectField } from "../ui/SelectField";
import { formatTime } from "../ui/format";
import { RulePreviewPanel } from "./RulePreviewPanel";
import { ReviewFeedbackPanel } from "./ReviewFeedbackPanel";

const emptyRule = (): ReviewRuleDocument => ({ include: [], exclude: [], rules: [] });
const lines = (value: string) => value.split("\n").map((item) => item.trim()).filter(Boolean);

export function ReviewRulesPage({ token }: { /** 内存中的管理口令。 */ token: string }) {
  const queryClient = useQueryClient();
  const repositories = useQuery({ queryKey: ["repositories"], queryFn: () => apiRequest<Repository[]>(token, "/api/repositories") });
  const configurations = useQuery({ queryKey: ["review-rules"], queryFn: () => apiRequest<ReviewRuleConfiguration[]>(token, "/api/review-rules"), staleTime: Infinity });
  const [scope, setScope] = useState("global");
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
    setForm(saved ? structuredClone(saved.content) : emptyRule());
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

  function updateRule(index: number, patch: Partial<ReviewRuleDocument["rules"][number]>) {
    setForm((value) => ({ ...value, rules: value.rules.map((entry, position) => position === index ? { ...entry, ...patch } : entry) }));
  }

  function moveRule(index: number, offset: number) {
    setForm((value) => {
      const rules = [...value.rules];
      [rules[index], rules[index + offset]] = [rules[index + offset], rules[index]];
      return { ...value, rules };
    });
  }

  function changeScope(value: string) {
    if (dirty && !window.confirm("当前审核规则尚未保存，确定切换配置范围？")) return;
    save.reset();
    remove.reset();
    setFeedback("");
    setScope(value);
  }

  return <div className="page"><PageHeader title="审核规则" subtitle="Open Code Review 逐文件规则" />
    <QueryState loading={repositories.isLoading || configurations.isLoading} error={repositories.error || configurations.error} />
    {!repositories.isLoading && !configurations.isLoading && !repositories.error && !configurations.error && <>
      <div className="rule-priority" aria-label="规则优先级"><strong>优先级</strong><span>项目页面规则</span><span>仓库 rule.json</span><span>全局页面规则</span><span>OCR 内置规则</span></div>
      <section className="section rule-workspace">
        <div className="rule-scope"><SelectField label="配置范围" value={scope} onValueChange={changeScope} options={[{ value: "global", label: "全局规则" }, ...(repositories.data ?? []).map((repo) => ({ value: String(repo.id), label: repo.name }))]} />
          <div className="rule-scope-meta"><strong>{current ? "已配置" : "使用下一级规则"}</strong>{current && <span>更新于 {formatTime(current.updated_at)}</span>}</div>
        </div>
        <form className="rule-form" onSubmit={submit}>
          <div className="section-head"><h2>规则条目</h2><button className="button button-secondary" type="button" onClick={() => setForm((value) => ({ ...value, rules: [...value.rules, { path: "", rule: "", merge_system_rule: true }] }))}><Plus size={16} />添加规则</button></div>
          {form.rules.length === 0 && <p className="rule-empty">当前范围尚无自定义条目</p>}
          <div className="rule-list">{form.rules.map((entry, index) => <div className="rule-item" key={index}>
            <div className="rule-item-head"><strong>规则 {index + 1}</strong><div className="row-actions"><button className="icon-button" type="button" aria-label={`上移规则 ${index + 1}`} title="上移规则" disabled={index === 0} onClick={() => moveRule(index, -1)}><ArrowUp size={16} /></button><button className="icon-button" type="button" aria-label={`下移规则 ${index + 1}`} title="下移规则" disabled={index === form.rules.length - 1} onClick={() => moveRule(index, 1)}><ArrowDown size={16} /></button><button className="icon-button icon-button-danger" type="button" aria-label={`删除规则 ${index + 1}`} title="删除规则" onClick={() => setForm((value) => ({ ...value, rules: value.rules.filter((_, position) => position !== index) }))}><Trash2 size={16} /></button></div></div>
            <label>文件路径模式<input value={entry.path} onChange={(event) => updateRule(index, { path: event.target.value })} placeholder="src/**/*.go" /></label>
            <label>审核内容<textarea rows={4} value={entry.rule} onChange={(event) => updateRule(index, { rule: event.target.value })} placeholder="检查公开接口的输入校验和权限判断。" /></label>
            <label className="checkbox-label"><input type="checkbox" checked={entry.merge_system_rule} onChange={(event) => updateRule(index, { merge_system_rule: event.target.checked })} />同时保留 OCR 内置语言规则</label>
          </div>)}</div>
          <div className="rule-filters"><label>额外纳入的路径<textarea rows={3} value={includeText} onChange={(event) => setIncludeText(event.target.value)} placeholder="**/*.test.ts" /></label><label>排除的路径<textarea rows={3} value={excludeText} onChange={(event) => setExcludeText(event.target.value)} placeholder="**/generated/**" /></label></div>
          {(localError || save.error || remove.error) && <p className="form-error" role="alert">{localError || save.error?.message || remove.error?.message}</p>}
          {feedback && <p className="form-success" role="status">{feedback}</p>}
          <div className="form-actions"><button className="button button-secondary" type="button" disabled={!current || remove.isPending} onClick={() => { if (window.confirm("确定删除当前范围的审核规则配置？")) remove.mutate(); }}><Trash2 size={16} />删除配置</button><button className="button button-primary" type="submit" disabled={save.isPending}><Save size={16} />保存规则</button></div>
        </form>
      </section>
      <ReviewFeedbackPanel token={token} repositoryId={repositoryId} />
      <RulePreviewPanel token={token} scopeRepositoryId={repositoryId} repositories={repositories.data ?? []} dirty={dirty} />
      <section className="section rule-workspace rule-history">
        <div className="section-head"><h2><History size={18} />版本历史</h2><span>最近 50 次变更</span></div>
        <QueryState loading={revisions.isLoading} error={revisions.error} />
        {restore.error && <p className="form-error" role="alert">{restore.error.message}</p>}
        {revisions.data?.length === 0 && <p className="rule-empty">尚无历史版本</p>}
        <div className="rule-revisions">{revisions.data?.map((revision) => <div className="rule-revision" key={revision.id}>
          <div><strong>版本 #{revision.id}</strong><span>{revision.action === "deleted" ? "已删除" : revision.action === "restored" ? `已恢复自 #${revision.restored_from}` : "已保存"}</span><time>{formatTime(revision.created_at)}</time></div>
          <div className="row-actions"><button className="button button-secondary" type="button" disabled={restore.isPending} onClick={() => { if (dirty && !window.confirm("当前编辑内容尚未保存，恢复历史版本会覆盖当前配置。确定继续？")) return; if (window.confirm(`确定恢复版本 #${revision.id}？`)) restore.mutate(revision.id); }}><RotateCcw size={15} />恢复</button></div>
          <details><summary>查看版本内容</summary><pre>{revision.content ? JSON.stringify(revision.content, null, 2) : "该版本未配置审核规则"}</pre></details>
        </div>)}</div>
      </section>
    </>}
  </div>;
}
