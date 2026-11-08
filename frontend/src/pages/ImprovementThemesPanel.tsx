/** @description 优化历程列表和入口；主题目标、阶段及问题关联从 SQLite API 读取。 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "antd";
import { Plus } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { listImprovementThemes } from "../api/improvements";
import { ListSelect as SelectField, ListSearch, ListStatusNav, ListTime, ListToolbar, ListConditions } from "../ui/ListControls";
import { ListTable } from "../ui/ListTable";
import { PageHeader } from "../ui/PageHeader";
import { Pagination } from "../ui/Pagination";
import { QueryState } from "../ui/QueryState";
import { listReturnSearch } from "../ui/listReturn";

import { ImprovementThemeEditor } from "./ImprovementThemeEditor";
import { categoryLabels } from "./improvementFields";

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
  return <section className="list-surface improvement-theme-panel" aria-label="优化历程">
    <PageHeader title="优化历程" subtitle="按主题组织目标、阶段、验证结论与遗留工作" actions={<Button type="primary" onClick={() => setAdding(true)}><Plus size={17} />新增优化主题</Button>} />
    <ListStatusNav value={params.get("theme_status") ?? "all"} labels={{ all: "全部", ...statuses }} counts={themes.error ? undefined : themes.data?.status_counts} onChange={(value) => update("theme_status", value)} />
    <ListToolbar advanced={<SelectField label="归档范围" value={params.get("theme_archive") ?? "active"} onValueChange={(value) => update("theme_archive", value)} options={[{ value: "active", label: "未归档" }, { value: "archived", label: "已归档" }, { value: "all", label: "全部（含归档）" }]} />}>
      <ListSearch key={params.get("theme_q") ?? ""} label="搜索优化主题" value={params.get("theme_q") ?? ""} onSearch={(value) => update("theme_q", value)} />
      <SelectField label="分类" value={params.get("theme_category") ?? "all"} onValueChange={(value) => update("theme_category", value)} options={[{ value: "all", label: "全部" }, ...Object.entries(categoryLabels).map(([value, label]) => ({ value, label }))]} />
      <Button onClick={() => { const next = new URLSearchParams(params); for (const key of [...next.keys()]) if (key.startsWith("theme_")) next.delete(key); setParams(next); }}>重置主题筛选</Button>
    </ListToolbar>
    <ListConditions items={[{ key: "theme_q", label: "搜索", value: params.get("theme_q") ?? "" }, { key: "theme_category", label: "分类", value: params.get("theme_category") ?? "" }, { key: "theme_archive", label: "归档范围", value: params.get("theme_archive") === "all" ? "含归档" : params.get("theme_archive") === "archived" ? "已归档" : "" }]} onClear={(key) => update(key, "")} />
    {params.get("theme_improvement_id") && <p className="active-filters">仅看关联问题 #{params.get("theme_improvement_id")} 的主题 <Button onClick={() => update("theme_improvement_id", "")}>清除问题筛选</Button></p>}
    <QueryState loading={themes.isLoading} error={themes.error} onRetry={() => void themes.refetch()} />
    <ListTable rowKey="id" dataSource={themes.data?.items ?? []} loading={themes.isFetching} pagination={false} scroll={{ x: 950 }} locale={{ emptyText: themes.error ? "无法读取主题" : "暂无优化主题" }} columns={[
      { title: "主题 / 目标", key: "title", width: 290, render: (_, theme) => <><Link className="list-primary list-title" to={`/improvements/themes/${theme.id}${listReturnSearch(params)}`}>#{theme.id} · {theme.title}</Link><span className="list-secondary">{theme.objective.slice(0, 80)}{theme.objective.length > 80 ? "…" : ""}{theme.archived_at ? " · 已归档" : ""}</span></> },
      { title: "范围 / 分类", key: "category", width: 140, render: (_, theme) => <>{theme.scope}<span className="list-secondary">{categoryLabels[theme.category]}</span></> },
      { title: "主题进展", key: "status", width: 100, render: (_, theme) => statuses[theme.status] },
      { title: "阶段进度", key: "phases", width: 150, render: (_, theme) => theme.phases.length ? <>{theme.phases.filter((phase) => phase.status === "completed").length} / {theme.phases.length} 阶段已完成<span className="list-secondary">进行中 {theme.phases.filter((phase) => phase.status === "active").length} 阶段</span></> : "尚无阶段" },
      { title: "关联问题", key: "links", width: 90, render: (_, theme) => `${theme.improvement_ids.length} 条` },
      { title: "更新时间", key: "time", width: 140, render: (_, theme) => <ListTime value={theme.updated_at} /> },
      { title: "操作", key: "action", width: 70, render: (_, theme) => <Link to={`/improvements/themes/${theme.id}${listReturnSearch(params)}`}>详情</Link> },
    ]} />
    <Pagination label="优化主题分页" total={themes.error ? undefined : themes.data?.total} page={page} pageSize={pageSize} disabled={themes.isFetching || Boolean(themes.error)} onPage={(value) => update("theme_page", String(value))} onPageSize={(value) => update("theme_page_size", String(value))} />
    {adding && <ImprovementThemeEditor token={token} onClose={() => setAdding(false)} onSaved={() => { setAdding(false); void client.invalidateQueries({ queryKey: ["improvement-themes"] }); }} />}
  </section>;
}
