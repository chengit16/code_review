/** @description 平台自身的问题台账；筛选和分页保留在 URL，不与 OCR 发现混用。 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Collapse } from "antd";
import { Plus } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { listImprovements } from "../api/improvements";
import { Pagination } from "../ui/Pagination";
import { QueryState } from "../ui/QueryState";
import { SelectField } from "../ui/SelectField";
import { formatTime } from "../ui/format";
import { ImprovementMaintenancePanel } from "./ImprovementMaintenancePanel";
import { ChatCapturePanel } from "./ChatCapturePanel";
import { ImprovementEditor } from "./ImprovementEditor";
import { ImprovementStates } from "./ImprovementFacts";
import { ImprovementThemesPanel } from "./ImprovementThemesPanel";
import { ImprovementSummaryPanel } from "./ImprovementSummaryPanel";
import { categoryLabels, kindLabels, progressLabels } from "./improvementFields";

/** 记录、历程与只读复盘共享入口，各视图筛选分别保留在 URL。 */
export function ImprovementsPage({ token }: { /** 内存管理员会话。 */ token: string }) {
  const [params, setParams] = useSearchParams();
  const view = params.get("view") === "themes" ? "themes" : params.get("view") === "summary" ? "summary" : "records";
  return <div className="page"><h1>问题与改进</h1><nav className="settings-tabs" aria-label="问题与改进视图">
    {[{ value: "records", label: "问题记录" }, { value: "themes", label: "优化历程" }, { value: "summary", label: "复盘汇总" }].map((item) => <button type="button" key={item.value} className={`repository-editor-tab${view === item.value ? " is-active" : ""}`} aria-pressed={view === item.value} onClick={() => { const next = new URLSearchParams(params); if (item.value !== "records") next.set("view", item.value); else next.delete("view"); setParams(next); }}>{item.label}</button>)}
  </nav><Collapse className="improvement-tools-collapse" items={[{ key: "maintenance", label: "维护与聊天收件箱（低频工具）", children: <div className="improvement-tools-content"><ImprovementMaintenancePanel token={token} /><ChatCapturePanel token={token} /></div> }]} />{view === "themes" ? <ImprovementThemesPanel token={token} /> : view === "summary" ? <ImprovementSummaryPanel token={token} /> : <ImprovementRecords token={token} />}</div>;
}

function ImprovementRecords({ token }: { token: string }) {
  const [params, setParams] = useSearchParams();
  const [adding, setAdding] = useState(false);
  const [feedback, setFeedback] = useState("");
  const client = useQueryClient();
  const page = Math.max(1, Number(params.get("page")) || 1);
  const pageSize = [25, 50, 100].includes(Number(params.get("page_size"))) ? Number(params.get("page_size")) : 25;
  const queryParams = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  for (const key of ["status", "kind", "category", "q"]) if (params.get(key)) queryParams.set(key, params.get(key) ?? "");
  queryParams.set("archive", ["active", "archived", "all"].includes(params.get("archive") ?? "") ? params.get("archive") ?? "active" : "active");
  const records = useQuery({ queryKey: ["improvements", queryParams.toString()], queryFn: ({ signal }) => listImprovements(token, queryParams, signal), refetchInterval: 30_000 });
  function filter(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value && (value !== "all" || key === "archive")) next.set(key, value); else next.delete(key);
    if (key !== "page") next.delete("page");
    setParams(next);
  }
  return <div><div className="improvement-records-heading"><p>记录平台问题、解决过程与阶段性改进，不是 OCR 发现的问题列表</p><button type="button" className="button button-primary" onClick={() => { setFeedback(""); setAdding(true); }}><Plus size={17} />新增记录</button></div>
    <section className="section">
      <p className="muted">代码已修改、本地验证通过、部署已生效分别记录。未解决的问题也可先保存排查进展。</p>
      <div className="improvement-filters">
        <SelectField label="归档范围" value={["active", "archived", "all"].includes(params.get("archive") ?? "") ? params.get("archive") ?? "active" : "active"} onValueChange={(value) => filter("archive", value)} options={[{ value: "active", label: "未归档" }, { value: "archived", label: "已归档" }, { value: "all", label: "全部（含归档）" }]} />
        <Search key={params.get("q") ?? ""} value={params.get("q") ?? ""} onSearch={(value) => filter("q", value)} />
        {([{ key: "status", label: "处理进展", labels: progressLabels }, { key: "kind", label: "记录类型", labels: kindLabels }, { key: "category", label: "分类", labels: categoryLabels }] as const).map((field) => <SelectField key={field.key} label={field.label} value={params.get(field.key) ?? "all"} onValueChange={(value) => filter(field.key, value)} options={[{ value: "all", label: "全部" }, ...Object.entries(field.labels).map(([value, label]) => ({ value, label }))]} />)}
      </div>
      {feedback && <p className="form-success" role="status">{feedback}</p>}
      <QueryState loading={records.isLoading} error={records.error} onRetry={() => void records.refetch()} />
      {records.data && <><div className="improvement-list">{records.data.items.map((record) => <article className="improvement-card" key={record.id}>
        <div className="improvement-card-head"><Link to={`/improvements/${record.id}`}>#{record.id} · {record.title}</Link>{record.archived_at && <span className="status">已归档</span>}<span className="status">{progressLabels[record.status]}</span></div>
        <p className="muted">{kindLabels[record.kind]} · {categoryLabels[record.category]} · {record.scope} · 更新于 {formatTime(record.updated_at)}</p>
        <p className="improvement-excerpt">{record.description}</p><ImprovementStates record={record} />
      </article>)}</div>
      {records.data.total === 0 && <p className="empty-row">当前条件下暂无记录。可先记下现象，处理后再追加解决和验证过程。</p>}
      <Pagination label="问题与改进分页" total={records.data.total} page={page} pageSize={pageSize} disabled={records.isFetching} onPage={(value) => filter("page", String(value))} onPageSize={(value) => filter("page_size", String(value))} /></>}
    </section>
    {adding && <ImprovementEditor token={token} onClose={() => setAdding(false)} onSaved={() => { setAdding(false); setFeedback("记录已保存至 SQLite，初始历史已保留。"); void client.invalidateQueries({ queryKey: ["improvements"] }); }} />}
  </div>;
}

function Search({ value, onSearch }: { value: string; onSearch: (value: string) => void }) {
  const [draft, setDraft] = useState(value);
  return <form className="improvement-search" onSubmit={(event) => { event.preventDefault(); onSearch(draft.trim()); }}><label>搜索记录<input maxLength={200} value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="标题、现象、原因、方案或功能" /></label><button className="button button-secondary" type="submit">搜索</button></form>;
}
