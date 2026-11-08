/** @description 配置全历史查询与安全恢复；筛选分页由 URL 管理，密文不进入差异展示。 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { App, Button, Drawer, Input } from "antd";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { apiRequest } from "../api/client";
import { searchConfigHistory, restoreConfigRevision } from "../api/configHistory";
import type { ConfigRevision as Revision } from "../api/configHistory";
import { ListConditions, ListSelect, ListTime, ListToolbar } from "../ui/ListControls";
import { ListTable } from "../ui/ListTable";
import { PageHeader } from "../ui/PageHeader";
import { Pagination } from "../ui/Pagination";
import { QueryState } from "../ui/QueryState";
import { localTimeInput, utcTimeInput } from "../ui/listDates";


const kinds = [
  { value: "repository", label: "项目配置", path: "/api/repositories" },
  { value: "notification_target", label: "飞书配置", path: "/api/notification-targets" },
  { value: "model_profile", label: "Agent 模型", path: "/api/model-profiles" },
];
const actions: Record<string, string> = { baseline: "初始版本", created: "新增", updated: "修改", deleted: "删除" };

/** 恢复目标包含冻结的类型和版本；更换列表条件不会改变确认的对象。 */
export function ConfigHistoryPage({ token }: { /** 内存中的管理口令。 */ token: string }) {
  const [params, setParams] = useSearchParams();
  const kind = kinds.find((item) => item.value === params.get("kind"))?.value ?? "repository";
  const object = params.get("object_id") ?? "all";
  const page = Math.max(1, Number(params.get("page")) || 1);
  const pageSize = [25, 50, 100].includes(Number(params.get("page_size"))) ? Number(params.get("page_size")) : 25;
  const query = new URLSearchParams({ kind, page: String(page), page_size: String(pageSize) });
  for (const key of ["object_id", "action", "since", "until"]) if (params.get(key)) query.set(key, params.get(key) ?? "");
  const [feedback, setFeedback] = useState("");
  const [dateError, setDateError] = useState("");
  const [detail, setDetail] = useState<Revision | null>(null);
  const client = useQueryClient();
  const { modal } = App.useApp();
  const objects = useQuery({ queryKey: ["history-objects", kind], queryFn: ({ signal }) => apiRequest<{ id: number; name: string }[]>(token, kinds.find((item) => item.value === kind)?.path ?? kinds[0].path, { signal }) });
  const history = useQuery({ queryKey: ["config-history", query.toString()], queryFn: ({ signal }) => searchConfigHistory(token, query, signal) });
  const restore = useMutation({
    mutationFn: (target: { kind: string; revision: Revision }) => restoreConfigRevision(token, target.kind, target.revision.object_id, target.revision.id),
    onSuccess: () => { setFeedback("配置内容已恢复，请重新核对外部连接"); void client.invalidateQueries(); },
  });
  function update(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value && value !== "all") next.set(key, value); else next.delete(key);
    if (key !== "page") next.delete("page");
    if (key === "kind") next.delete("object_id");
    setDetail(null); setFeedback(""); setParams(next);
  }
  return <div className="page"><PageHeader title="配置历史" subtitle="项目、飞书与模型的完整配置历史；恢复会建立新版本" />
    <section className="list-surface">
      <ListToolbar advanced={<>
        <ListSelect label="变更动作" value={params.get("action") ?? "all"} onValueChange={(value) => update("action", value)} disabled={restore.isPending} options={[{ value: "all", label: "全部动作" }, ...Object.entries(actions).map(([value, label]) => ({ value, label }))]} />
        <form className="list-toolbar" key={`${params.get("since")}-${params.get("until")}`} onSubmit={(event) => {
          event.preventDefault(); const form = new FormData(event.currentTarget);
          try {
            const since = utcTimeInput(String(form.get("since") ?? "")); const until = utcTimeInput(String(form.get("until") ?? ""));
            if (since && until && since > until) throw new Error("起始时间不能晚于结束时间");
            const next = new URLSearchParams(params); next.delete("page");
            for (const [key, value] of [["since", since], ["until", until]]) { if (value) next.set(key, value); else next.delete(key); }
            setDateError(""); setDetail(null); setFeedback(""); setParams(next);
          } catch (error) { setDateError(error instanceof Error ? error.message : "时间无效"); }
        }}><label>起始时间<Input name="since" type="datetime-local" defaultValue={localTimeInput(params.get("since"))} /></label><label>结束时间<Input name="until" type="datetime-local" defaultValue={localTimeInput(params.get("until"))} /></label><Button htmlType="submit" disabled={restore.isPending}>应用时间</Button></form>
      </>}>
        <ListSelect label="配置类型" value={kind} onValueChange={(value) => update("kind", value)} disabled={restore.isPending} options={kinds} />
        <ListSelect label="对象" value={object} onValueChange={(value) => update("object_id", value)} disabled={restore.isPending} options={[{ value: "all", label: "全部对象" }, ...(objects.data ?? []).map((item) => ({ value: String(item.id), label: item.name })), ...(object !== "all" && !objects.data?.some((item) => String(item.id) === object) ? [{ value: object, label: `历史对象 #${object}` }] : [])]} />
        <Button disabled={restore.isPending} onClick={() => { setDetail(null); setFeedback(""); setDateError(""); setParams(new URLSearchParams({ kind })); }}>重置</Button>
      </ListToolbar>
      <ListConditions disabled={restore.isPending} items={[{ key: "action", label: "动作", value: actions[params.get("action") ?? ""] ?? "" }, { key: "since", label: "起始", value: params.get("since") ?? "" }, { key: "until", label: "结束", value: params.get("until") ?? "" }]} onClear={(key) => update(key, "")} />
      {dateError && <p role="alert">{dateError}</p>}{feedback && <p role="status">{feedback}</p>}
      <QueryState loading={history.isLoading} error={history.error || objects.error || restore.error} onRetry={() => { void history.refetch(); void objects.refetch(); }} />
      <p className="form-note">凭据只展示是否变更；恢复不改变模型启用状态，也不保证历史凭据仍然有效。</p>
      <ListTable rowKey="id" dataSource={history.data?.items ?? []} loading={history.isFetching} pagination={false} scroll={{ x: 850 }} locale={{ emptyText: history.error ? "无法读取配置历史" : "暂无配置版本" }} columns={[
        { title: "版本 / 动作", key: "version", width: 120, render: (_, revision) => <>#{revision.id}<span className="list-secondary">{actions[revision.action] ?? revision.action}</span></> },
        { title: "对象", key: "object", width: 200, render: (_, revision) => <>{objects.data?.find((item) => item.id === revision.object_id)?.name ?? (objects.isSuccess ? `已删除对象 #${revision.object_id}` : `对象 #${revision.object_id} · 名称待确认`)}<span className="list-secondary">{kinds.find((item) => item.value === kind)?.label}</span></> },
        { title: "操作人", dataIndex: "actor", key: "actor", width: 130 },
        { title: "记录时间", key: "time", width: 140, render: (_, revision) => <ListTime value={revision.created_at} /> },
        { title: "变更摘要", key: "changes", render: (_, revision) => <Button type="link" onClick={() => setDetail(revision)}>{revision.changes.length} 个字段 · 查看差异</Button> },
        { title: "操作", key: "action", width: 150, render: (_, revision) => {
          const reason = !revision.restorable ? "删除版本不可恢复" : !objects.isSuccess ? "对象状态待确认" : !objects.data.some((item) => item.id === revision.object_id) ? "对象已删除，不可恢复" : "";
          return <><Button type="link" aria-label={`恢复版本 ${revision.id}`} disabled={restore.isPending || !!reason} onClick={() => modal.confirm({ title: `恢复对象 #${revision.object_id} 到版本 #${revision.id}？`, content: "会建立新版本；历史凭据可能已被外部撤销，模型启用状态保持当前设置。", onOk: () => restore.mutateAsync({ kind, revision }) })}>恢复</Button>{reason && <span className="list-secondary">{reason}</span>}</>;
        } },
      ]} />
      <Pagination label="配置历史分页" page={page} pageSize={pageSize} total={history.error ? undefined : history.data?.total} disabled={history.isFetching || !!history.error || restore.isPending} onPage={(value) => update("page", String(value))} onPageSize={(value) => update("page_size", String(value))} />
    </section>
    <Drawer open={detail !== null} title={detail ? `版本 #${detail.id} · 对象 #${detail.object_id}` : "变更详情"} onClose={() => setDetail(null)} destroyOnHidden>{detail?.changes.map((change) => <section key={change.field}><h3>{change.field}</h3><p className="prewrap">{change.secret ? "凭据已变更，明文不回显" : `${String(change.before ?? "未设置")} → ${String(change.after ?? "未设置")}`}</p></section>)}</Drawer>
  </div>;
}
