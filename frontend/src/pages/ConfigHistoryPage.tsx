/** @description 配置版本字段差异和恢复；服务端保护凭据及队列一致性。 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Card, Select, Table } from "antd";
import type { TableColumnsType } from "antd";
import { RotateCcw } from "lucide-react";
import { useState } from "react";

import { apiRequest } from "../api/client";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { formatTime } from "../ui/format";

interface Revision {
  id: number; object_id: number; action: string; actor: string; created_at: string;
  restorable: boolean;
  changes: { field: string; secret: boolean; before: unknown; after: unknown }[];
}
const kinds = [
  { value: "repository", label: "项目配置", path: "/api/repositories" },
  { value: "notification_target", label: "飞书配置", path: "/api/notification-targets" },
  { value: "model_profile", label: "Agent 模型", path: "/api/model-profiles" },
];

/** 恢复前展示版本及对象，恢复后刷新所有关联配置缓存。 */
export function ConfigHistoryPage({ token }: { /** 内存中的管理口令。 */ token: string }) {
  const [kind, setKind] = useState("repository");
  const [object, setObject] = useState("all");
  const [feedback, setFeedback] = useState("");
  const queryClient = useQueryClient();
  const objects = useQuery({ queryKey: ["history-objects", kind], queryFn: () => apiRequest<{ id: number; name: string }[]>(token, kinds.find((k) => k.value === kind)?.path ?? kinds[0].path) });
  const history = useQuery({ queryKey: ["config-history", kind, object], queryFn: () => apiRequest<Revision[]>(token, `/api/config-history/${kind}${object === "all" ? "" : `?object_id=${object}`}`) });
  const restore = useMutation({
    mutationFn: (revision: Revision) => apiRequest(token, `/api/config-history/${kind}/${revision.object_id}/${revision.id}/restore`, { method: "POST" }),
    onSuccess: () => { setFeedback("配置内容已恢复，请重新核对外部连接"); void queryClient.invalidateQueries(); },
  });
  const columns: TableColumnsType<Revision> = [
    { title: "版本", dataIndex: "id", key: "id", width: 110, render: (id: number, revision) => <>#{id}<small className="table-sub">{({ baseline: "初始版本", created: "新增", updated: "修改", deleted: "删除" } as Record<string, string>)[revision.action]}</small></> },
    { title: "对象", key: "object", width: 180, render: (_: unknown, revision) => objects.data?.find((item) => item.id === revision.object_id)?.name ?? `已删除对象 #${revision.object_id}` },
    { title: "时间 / 操作者", key: "created_at", width: 190, render: (_: unknown, revision) => <>{formatTime(revision.created_at)}<small className="table-sub">{revision.actor}</small></> },
    { title: "变更", dataIndex: "changes", key: "changes", render: (changes: Revision["changes"]) => <details className="revision-changes"><summary>{changes.length} 个字段</summary>{changes.map((change) => <p key={change.field}><strong>{change.field}</strong><br />{change.secret ? "凭据已变更" : `${String(change.before ?? "未设置")} → ${String(change.after ?? "未设置")}`}</p>)}</details> },
    { title: "操作", key: "action", width: 72, render: (_: unknown, revision) => <Button type="text" title="恢复此版本内容" aria-label={`恢复版本 ${revision.id}`} disabled={restore.isPending || !revision.restorable || !objects.data?.some((item) => item.id === revision.object_id)} onClick={() => { if (window.confirm(`将对象 #${revision.object_id} 恢复为版本 #${revision.id} 的内容？历史凭据可能已被外部撤销。模型启用状态保持当前设置。`)) restore.mutate(revision); }}><RotateCcw size={16} /></Button> },
  ];
  return <div className="page"><PageHeader title="配置历史" subtitle="项目、飞书与模型版本" />
    <Card className="history-filter-card" size="small"><div className="history-filter-grid">
      <label>配置类型<Select aria-label="配置类型" value={kind} onChange={(value) => { setKind(value); setObject("all"); setFeedback(""); restore.reset(); }} options={kinds.map(({ value, label }) => ({ value, label }))} /></label>
      <label>对象<Select aria-label="对象" value={object} onChange={setObject} options={[{ value: "all", label: "全部对象" }, ...(objects.data ?? []).map((item) => ({ value: String(item.id), label: item.name }))]} /></label>
    </div></Card>
    {feedback && <p className="form-success" role="status">{feedback}</p>}<QueryState loading={history.isLoading} error={history.error || objects.error || restore.error} onRetry={() => { void history.refetch(); void objects.refetch(); }} />
    <Card className="history-table-card" size="small" title={<h2 className="history-table-heading">变更记录</h2>}><p className="issue-table-note">恢复会写入一个新版本；历史凭据可能已被外部撤销，模型启用状态保持当前设置。</p><Table rowKey="id" columns={columns} dataSource={history.data ?? []} loading={history.isFetching} locale={{ emptyText: history.error ? "无法读取配置历史" : "暂无配置版本" }} scroll={{ x: 760 }} pagination={{ pageSize: 25, pageSizeOptions: [25, 50, 100], showSizeChanger: true, locale: { items_per_page: "条/页", prev_page: "上一页", next_page: "下一页", page: "页", jump_to: "跳至", page_size: "每页条数" }, showTotal: (total) => `${total} 条` }} /></Card>
  </div>;
}
