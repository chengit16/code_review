/** @description 问题侧栏的处理、证据与重复项选择；只提交用户明确确认的目标，服务端校验状态和同仓库约束。 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { apiRequest } from "../api/client";
import { Modal } from "../ui/Modal";
import { QueryState } from "../ui/QueryState";
import { SelectField } from "../ui/SelectField";
import { formatCategory, formatSeverity, formatTime, shortSha } from "../ui/format";

interface Issue {
  id: number; repository_id: number; repository_name: string; status: string; path: string;
  content: string; severity: string | null; category: string | null; merged_into_id: number | null;
  occurrences: Array<{ id: number; job_id: number; attempt_number: number; mr_iid: number; commit_sha: string; path: string; start_line: number | null; created_at: string }>;
  events: Array<{ id: number; new_status: string; actor: string; note: string | null; created_at: string }>;
}
const labels: Record<string, string> = { open: "待处理", fixed: "已修复", ignored: "已忽略", merged: "已合并" };

/** 桌面侧栏、窄屏全屏详情；地址栏决定当前问题，关闭回到原筛选位置。 */
export function IssueDetailDrawer({ token, id, canEdit, batchPending, onSelect }: {
  /** 内存凭据。 */ token: string;
  /** 当前问题编号，切换时由父组件重新挂载。 */ id: number;
  /** 仅控制操作显示，服务端仍是授权边界。 */ canEdit: boolean;
  /** 批量保存时避免单项同时覆盖。 */ batchPending: boolean;
  /** 选择其他问题或关闭侧栏。 */ onSelect: (id: number | null) => void;
}) {
  const client = useQueryClient();
  const [note, setNote] = useState("");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [occurrenceLimit, setOccurrenceLimit] = useState(10);
  const [eventLimit, setEventLimit] = useState(10);
  // 搜索延迟提交，切换关键词立即清空目标，防止选中旧结果。
  useEffect(() => { const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 300); return () => window.clearTimeout(timer); }, [search]);
  const [target, setTarget] = useState("");
  const detail = useQuery({ queryKey: ["review-issue", id], queryFn: ({ signal }) => apiRequest<Issue>(token, `/api/review-issues/${id}`, { signal }) });
  const candidates = useQuery({ queryKey: ["issue-merge-candidates", detail.data?.repository_id, debouncedSearch],
    queryFn: ({ signal }) => apiRequest<{ items: Issue[] }>(token, `/api/review-issues?repository_id=${detail.data?.repository_id}&status=open&page_size=10&q=${encodeURIComponent(debouncedSearch)}`, { signal }),
    enabled: canEdit && detail.data?.status === "open" && Boolean(debouncedSearch) && search.trim() === debouncedSearch });
  const refresh = () => { for (const key of ["review-issues", "review-issue", "job", "review-effectiveness", "issue-merge-candidates"]) void client.invalidateQueries({ queryKey: [key] }); };
  const change = useMutation({ mutationFn: (status: string) => apiRequest(token, `/api/review-issues/${id}`, { method: "PATCH", body: JSON.stringify({ status, note: note.trim() || null }) }), onSuccess: () => { setNote(""); refresh(); } });
  const merge = useMutation({ mutationFn: () => apiRequest(token, `/api/review-issues/${id}/merge`, { method: "POST", body: JSON.stringify({ target_id: Number(target) }) }), onSuccess: () => { setTarget(""); setSearch(""); refresh(); } });
  const issue = detail.data;
  const busy = batchPending || change.isPending || merge.isPending;
  const options = (candidates.data?.items ?? []).filter((item) => item.id !== id);
  return <Modal titleId="issue-drawer-title" className="issue-drawer" onClose={() => { if (!busy) onSelect(null); }}>
    <div className="modal-heading"><h2 id="issue-drawer-title">问题 #{id}</h2><button className="button button-secondary" disabled={busy} onClick={() => onSelect(null)}>关闭</button></div>
    <div className="issue-drawer-body"><QueryState loading={detail.isLoading} error={detail.error} onRetry={() => void detail.refetch()} />
      {issue && <><div className="issue-detail-head"><span>{issue.repository_name} · {labels[issue.status]}</span><span>{formatSeverity(issue.severity)} · {formatCategory(issue.category)}</span></div><p className="mono file-path">{issue.path}</p><p className="issue-full-content">{issue.content}</p>
        {issue.merged_into_id && <p>已并入问题 <button className="text-link" onClick={() => onSelect(issue.merged_into_id)}>#{issue.merged_into_id}</button></p>}
        {canEdit && issue.status !== "merged" && <div className="issue-actions"><label>处理说明<input disabled={busy} value={note} maxLength={500} onChange={(event) => setNote(event.target.value)} placeholder="可选，说明核查依据" /></label><div className="issue-action-buttons">{["open", "fixed", "ignored"].map((status) => <button key={status} className={issue.status === status ? "button button-primary" : "button button-secondary"} disabled={busy || issue.status === status} onClick={() => change.mutate(status)}>{labels[status]}</button>)}</div></div>}
        {(change.error || merge.error) && <p className="form-error" role="alert">{(change.error || merge.error)?.message}</p>}
        {change.isSuccess && <p role="status" className="form-success">问题状态已保存，关联任务同步更新。</p>}
        {canEdit && issue.status === "open" && <details className="advanced-panel"><summary>合并重复问题</summary><div className="merge-search"><label>搜索重复问题<input disabled={busy} value={search} maxLength={200} onChange={(event) => { setSearch(event.target.value); setTarget(""); }} placeholder="输入问题摘要、文件路径或编号" /></label><QueryState loading={candidates.isFetching} error={candidates.error} /><SelectField label="合并目标" value={target} disabled={busy || search.trim() !== debouncedSearch} onValueChange={setTarget} options={options.map((item) => ({ value: String(item.id), label: `#${item.id} ${item.content.slice(0, 80)} · ${item.path}` }))} placeholder="选择同项目的待处理问题" /><button className="button button-secondary" disabled={!target || busy || candidates.isFetching || search.trim() !== debouncedSearch} onClick={() => { if (window.confirm(`确认将问题 #${id} 合并到 #${target}？出现记录将归入目标问题，源问题保留合并历史。`)) merge.mutate(); }}>确认合并</button>{search.trim() && search.trim() === debouncedSearch && !candidates.isFetching && !candidates.error && !options.length && <p>未找到同项目的其他待处理问题，请更换关键词。</p>}</div></details>}
        <h3>出现记录</h3><div className="issue-occurrences">{issue.occurrences.slice(0, occurrenceLimit).map((item) => <div key={item.id}><Link to={`/jobs/${item.job_id}`}>任务 #{item.job_id} · 第 {item.attempt_number} 次 →</Link><span>{item.mr_iid > 0 ? `MR !${item.mr_iid}` : "默认分支 Push"} · {shortSha(item.commit_sha)}</span><span className="mono file-path">{item.path}{item.start_line ? `:${item.start_line}` : ""}</span><small>{formatTime(item.created_at)}</small></div>)}</div>
        {issue.occurrences.length > occurrenceLimit && <button className="text-link history-more" onClick={() => setOccurrenceLimit((value) => value + 10)}>再显示 10 条出现记录（已显示 {occurrenceLimit} / {issue.occurrences.length}）</button>}
        <h3>处理记录</h3><ul className="issue-history">{issue.events.slice(0, eventLimit).map((item) => <li key={item.id}><span>{formatTime(item.created_at)} · {item.actor} · {labels[item.new_status]}</span>{item.note && <p>{item.note}</p>}</li>)}</ul>
        {issue.events.length > eventLimit && <button className="text-link history-more" onClick={() => setEventLimit((value) => value + 10)}>再显示 10 条处理记录（已显示 {eventLimit} / {issue.events.length}）</button>}
      </>}
    </div>
  </Modal>;
}
