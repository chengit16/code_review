/** @description 优化历程列表和入口；主题目标、阶段及问题关联从 SQLite API 读取。 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { listImprovementThemes } from "../api/improvements";
import { PageHeader } from "../ui/PageHeader";
import { Pagination } from "../ui/Pagination";
import { QueryState } from "../ui/QueryState";
import { SelectField } from "../ui/SelectField";
import { formatTime } from "../ui/format";
import { categoryLabels } from "./improvementFields";
import { ImprovementThemeEditor } from "./ImprovementThemeEditor";

const statuses = { planned: "待开始", active: "进行中", paused: "已暂停", completed: "已完成", deferred: "暂缓" };

/** 优化主题列表提供独立归档筛选，不因主题归档改变阶段或问题状态。 */
export function ImprovementThemesPanel({ token }: { /** 管理员内存会话。 */ token: string }) {
  const [params, setParams] = useSearchParams();
  const [adding, setAdding] = useState(false);
  const client = useQueryClient();
  const page = Math.max(1, Number(params.get("theme_page")) || 1);
  const pageSize = [25, 50, 100].includes(Number(params.get("theme_page_size"))) ? Number(params.get("theme_page_size")) : 25;
  const query = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  for (const key of ["theme_status", "theme_category", "theme_q", "theme_improvement_id"]) if (params.get(key)) query.set(key.slice(6), params.get(key) ?? "");
  query.set("archive", ["active", "archived", "all"].includes(params.get("theme_archive") ?? "") ? params.get("theme_archive") ?? "active" : "active");
  const themes = useQuery({ queryKey: ["improvement-themes", query.toString()], queryFn: ({ signal }) => listImprovementThemes(token, query, signal), refetchInterval: 30_000 });
  function update(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value && (value !== "all" || key === "theme_archive")) next.set(key, value); else next.delete(key);
    if (key !== "theme_page") next.delete("theme_page");
    setParams(next);
  }
  return <section className="section improvement-theme-panel" aria-label="优化历程">
    <PageHeader title="优化历程" subtitle="按主题组织目标、阶段、验证结论与遗留工作" actions={<button type="button" className="button button-primary" onClick={() => setAdding(true)}><Plus size={17} />新增优化主题</button>} />
    <div className="improvement-filters"><SelectField label="归档范围" value={["active", "archived", "all"].includes(params.get("theme_archive") ?? "") ? params.get("theme_archive") ?? "active" : "active"} onValueChange={(value) => update("theme_archive", value)} options={[{ value: "active", label: "未归档" }, { value: "archived", label: "已归档" }, { value: "all", label: "全部（含归档）" }]} /><Search key={params.get("theme_q") ?? ""} value={params.get("theme_q") ?? ""} onSearch={(value) => update("theme_q", value)} />
      <SelectField label="主题进展" value={params.get("theme_status") ?? "all"} onValueChange={(value) => update("theme_status", value)} options={[{ value: "all", label: "全部" }, ...Object.entries(statuses).map(([value, label]) => ({ value, label }))]} />
      <SelectField label="分类" value={params.get("theme_category") ?? "all"} onValueChange={(value) => update("theme_category", value)} options={[{ value: "all", label: "全部" }, ...Object.entries(categoryLabels).map(([value, label]) => ({ value, label }))]} />
    </div>
    {params.get("theme_improvement_id") && <p className="active-filters">仅看关联问题 #{params.get("theme_improvement_id")} 的主题 <button className="button button-secondary" type="button" onClick={() => update("theme_improvement_id", "")}>清除问题筛选</button></p>}
    <QueryState loading={themes.isLoading} error={themes.error} onRetry={() => void themes.refetch()} />
    {themes.data && <><div className="improvement-list">{themes.data.items.map((theme) => <article className="improvement-card" key={theme.id}>
      <div className="improvement-card-head"><Link to={`/improvements/themes/${theme.id}`}>#{theme.id} · {theme.title}</Link>{theme.archived_at && <span className="status">已归档</span>}<span className="status">{statuses[theme.status]}</span></div>
      <p className="muted">{categoryLabels[theme.category]} · {theme.scope} · {theme.phases.length} 个阶段 · 关联 {theme.improvement_ids.length} 条问题 · 更新于 {formatTime(theme.updated_at)}</p>
      <p className="improvement-excerpt">{theme.objective}</p>
      {theme.phases.length > 0 && <ol className="theme-phase-list">{theme.phases.map((phase, index) => <li key={`${phase.title}-${index}`}><span>{phase.title}</span><span className="muted">{phase.status === "completed" ? "已完成" : phase.status === "active" ? "进行中" : phase.status === "deferred" ? "暂缓" : "待开始"}</span></li>)}</ol>}
    </article>)}</div>
    {themes.data.total === 0 && <p className="empty-row">暂无优化主题。可以先建立优化目标，再分阶段记录处理过程。</p>}
    <Pagination label="优化主题分页" total={themes.data.total} page={page} pageSize={pageSize} disabled={themes.isFetching} onPage={(value) => update("theme_page", String(value))} onPageSize={(value) => update("theme_page_size", String(value))} /></>}
    {adding && <ImprovementThemeEditor token={token} onClose={() => setAdding(false)} onSaved={() => { setAdding(false); void client.invalidateQueries({ queryKey: ["improvement-themes"] }); }} />}
  </section>;
}

function Search({ value, onSearch }: { value: string; onSearch: (value: string) => void }) {
  const [draft, setDraft] = useState(value);
  return <form className="improvement-search" onSubmit={(event) => { event.preventDefault(); onSearch(draft.trim()); }}><label>搜索优化主题<input maxLength={200} value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="名称、目标、背景或结果" /></label><button className="button button-secondary" type="submit">搜索</button></form>;
}
