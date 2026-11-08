/** @description 平台自身的问题台账；筛选和分页保留在 URL，不与 OCR 发现混用。 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Collapse } from "antd";
import { Plus } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { listImprovements } from "../api/improvements";
import { ListSelect as SelectField, ListSearch, ListStatusNav, ListTime, ListToolbar, ListConditions } from "../ui/ListControls";
import { ListTable } from "../ui/ListTable";
import { Pagination } from "../ui/Pagination";
import { QueryState } from "../ui/QueryState";
import { listReturnSearch } from "../ui/listReturn";

import { ChatCapturePanel } from "./ChatCapturePanel";
import { ImprovementEditor } from "./ImprovementEditor";
import { ImprovementMaintenancePanel } from "./ImprovementMaintenancePanel";
import { ImprovementSummaryPanel } from "./ImprovementSummaryPanel";
import { ImprovementThemesPanel } from "./ImprovementThemesPanel";
import { categoryLabels, kindLabels, progressLabels, codeLabels, verificationLabels, deploymentLabels } from "./improvementFields";

/** 记录、历程与只读复盘共享入口，各视图筛选分别保留在 URL。 */
export function ImprovementsPage({ token }: { /** 内存管理员会话。 */ token: string }) {
  const [params, setParams] = useSearchParams();
  const [toolsActive, setToolsActive] = useState(false);
  const view = params.get("view") === "themes" ? "themes" : params.get("view") === "summary" ? "summary" : "records";
  return <div className="page"><h1>问题与改进</h1><nav className="settings-tabs" aria-label="问题与改进视图">
    {[{ value: "records", label: "问题记录" }, { value: "themes", label: "优化历程" }, { value: "summary", label: "复盘汇总" }].map((item) => <Button key={item.value} className={`repository-editor-tab${view === item.value ? " is-active" : ""}`} aria-pressed={view === item.value} onClick={() => { const next = new URLSearchParams(params); if (item.value !== "records") next.set("view", item.value); else next.delete("view"); setParams(next); }}>{item.label}</Button>)}
  </nav><Collapse onChange={(keys) => setToolsActive(keys.includes("maintenance"))} className="improvement-tools-collapse" items={[{ key: "maintenance", label: "维护与聊天收件箱（低频工具）", children: <div className="improvement-tools-content"><ImprovementMaintenancePanel token={token} /><ChatCapturePanel token={token} active={toolsActive} /></div> }]} />{view === "themes" ? <ImprovementThemesPanel token={token} /> : view === "summary" ? <ImprovementSummaryPanel token={token} /> : <ImprovementRecords token={token} />}</div>;
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
  return <div><div className="improvement-records-heading"><p>记录平台问题、解决过程与阶段性改进，不是 OCR 发现的问题列表</p><Button type="primary" onClick={() => { setFeedback(""); setAdding(true); }}><Plus size={17} />新增记录</Button></div>
    <section className="list-surface">
      <ListStatusNav value={params.get("status") ?? "all"} labels={{ all: "全部", ...progressLabels }} counts={records.error ? undefined : records.data?.status_counts} onChange={(value) => filter("status", value)} />
      <p className="muted">代码已修改、本地验证通过、部署已生效分别记录。未解决的问题也可先保存排查进展。</p>
      <ListToolbar advanced={<>
        <SelectField label="记录类型" value={params.get("kind") ?? "all"} onValueChange={(value) => filter("kind", value)} options={[{ value: "all", label: "全部" }, ...Object.entries(kindLabels).map(([value, label]) => ({ value, label }))]} />
        <SelectField label="分类" value={params.get("category") ?? "all"} onValueChange={(value) => filter("category", value)} options={[{ value: "all", label: "全部" }, ...Object.entries(categoryLabels).map(([value, label]) => ({ value, label }))]} />
        <SelectField label="归档范围" value={params.get("archive") ?? "active"} onValueChange={(value) => filter("archive", value)} options={[{ value: "active", label: "未归档" }, { value: "archived", label: "已归档" }, { value: "all", label: "全部（含归档）" }]} />
      </>}>
        <ListSearch key={params.get("q") ?? ""} label="搜索记录" value={params.get("q") ?? ""} onSearch={(value) => filter("q", value)} placeholder="标题、现象、原因、方案或功能" />
        <Button onClick={() => { const next = new URLSearchParams(params); for (const key of ["status", "kind", "category", "q", "archive", "page"]) next.delete(key); setParams(next); }}>重置</Button>
      </ListToolbar>
      <ListConditions items={[{ key: "q", label: "搜索", value: params.get("q") ?? "" }, { key: "kind", label: "类型", value: kindLabels[params.get("kind") as keyof typeof kindLabels] ?? "" }, { key: "category", label: "分类", value: categoryLabels[params.get("category") as keyof typeof categoryLabels] ?? "" }, { key: "archive", label: "归档范围", value: params.get("archive") === "all" ? "含归档" : params.get("archive") === "archived" ? "已归档" : "" }]} onClear={(key) => filter(key, "")} />
      {feedback && <p className="form-success" role="status">{feedback}</p>}
      <QueryState loading={records.isLoading} error={records.error} onRetry={() => void records.refetch()} />
      <ListTable rowKey="id" dataSource={records.data?.items ?? []} loading={records.isFetching} pagination={false} scroll={{ x: 1100 }} locale={{ emptyText: records.error ? "无法读取记录" : "当前条件下暂无记录" }} columns={[
        { title: "记录 / 范围", key: "title", width: 260, render: (_, record) => <><Link className="list-primary list-title" to={`/improvements/${record.id}${listReturnSearch(params)}`}>#{record.id} · {record.title}</Link><span className="list-secondary">{record.scope}{record.archived_at ? " · 已归档" : ""}</span></> },
        { title: "类型 / 分类", key: "kind", width: 125, render: (_, record) => <>{kindLabels[record.kind]}<span className="list-secondary">{categoryLabels[record.category]}</span></> },
        { title: "处理进展", key: "status", width: 100, render: (_, record) => progressLabels[record.status] },
        { title: "代码修改", key: "code", width: 135, render: (_, record) => codeLabels[record.code_state] },
        { title: "本地验证", key: "verification", width: 135, render: (_, record) => verificationLabels[record.verification_state] },
        { title: "部署生效", key: "deployment", width: 125, render: (_, record) => deploymentLabels[record.deployment_state] },
        { title: "更新时间", key: "time", width: 140, render: (_, record) => <ListTime value={record.updated_at} /> },
        { title: "操作", key: "action", width: 70, render: (_, record) => <Link to={`/improvements/${record.id}${listReturnSearch(params)}`}>详情</Link> },
      ]} />
      <Pagination label="问题与改进分页" total={records.error ? undefined : records.data?.total} page={page} pageSize={pageSize} disabled={records.isFetching || Boolean(records.error)} onPage={(value) => filter("page", String(value))} onPageSize={(value) => filter("page_size", String(value))} />
    </section>
    {adding && <ImprovementEditor token={token} onClose={() => setAdding(false)} onSaved={() => { setAdding(false); setFeedback("记录已保存至 SQLite，初始历史已保留。"); void client.invalidateQueries({ queryKey: ["improvements"] }); }} />}
  </div>;
}
