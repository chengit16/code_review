/** @description 主题的问题选择器；服务端检索和分页，选择不隐式扩展到其他页。 */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { listImprovements } from "../api/improvements";
import { QueryState } from "../ui/QueryState";
import { progressLabels } from "./improvementFields";

/** 搜索和换页保留显式选择；读取失败不会清空原关联。 */
export function ThemeProblemPicker({ token, selected, onChange, disabled }: {
  /** 管理员内存会话。 */ token: string;
  /** 所有已选编号，不限当前页。 */ selected: number[];
  /** 用户勾选、取消或主动移除单项时调用。 */ onChange: (ids: number[]) => void;
  /** 主题写入期间禁止编辑。 */ disabled: boolean;
}) {
  const [keyword, setKeyword] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const query = new URLSearchParams({ q, page: String(page), page_size: "25", archive: "all" });
  const issues = useQuery({ queryKey: ["improvements", "theme-picker", q, page],
    queryFn: ({ signal }) => listImprovements(token, query, signal) });
  return <section className="theme-issue-links" aria-label="关联问题记录"><h3>关联问题记录</h3>
    <p className="muted">已选 {selected.length} 条，仅关联显式选择的记录；不会自动改变问题状态。检索包含归档记录，原关联不会因归档丢失。</p>
    <div className="theme-selected-links">{selected.map((id) => <button key={id} className="button button-secondary" type="button" disabled={disabled} aria-label={`取消关联记录 ${id}`} onClick={() => onChange(selected.filter((value) => value !== id))}>#{id} ×</button>)}</div>
    <div className="improvement-search"><label>搜索可关联记录<input maxLength={200} value={keyword} disabled={disabled} onChange={(event) => setKeyword(event.target.value)} /></label><button type="button" className="button button-secondary" disabled={disabled} onClick={() => { setQ(keyword.trim()); setPage(1); }}>搜索问题</button></div>
    <QueryState loading={issues.isLoading} error={issues.error} onRetry={() => void issues.refetch()} />
    {issues.data && <><div className="theme-problem-options">{issues.data.items.map((issue) => <label className="checkbox-label" key={issue.id}><input type="checkbox" disabled={disabled || (!selected.includes(issue.id) && selected.length >= 500)} checked={selected.includes(issue.id)} onChange={(event) => onChange(event.target.checked ? [...selected, issue.id] : selected.filter((id) => id !== issue.id))} />#{issue.id} · {issue.title} · {progressLabels[issue.status]}{issue.archived_at ? " · 已归档" : ""}</label>)}</div>
      {issues.data.total === 0 && <p className="muted">没有匹配的记录，已有选择仍保留。</p>}
      <div className="pagination"><span>共 {issues.data.total} 条 · 第 {page} 页</span><button className="button button-secondary" type="button" disabled={disabled || issues.isFetching || page <= 1} onClick={() => setPage(page - 1)}>上一页问题</button><button className="button button-secondary" type="button" disabled={disabled || issues.isFetching || page * 25 >= issues.data.total} onClick={() => setPage(page + 1)}>下一页问题</button></div>
    </>}
  </section>;
}
