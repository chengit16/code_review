/** @description 配置版本字段差异和恢复；服务端保护凭据及队列一致性。 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RotateCcw } from "lucide-react";
import { useState } from "react";

import { apiRequest } from "../api/client";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { SelectField } from "../ui/SelectField";
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
  return <div className="page"><PageHeader title="配置历史" subtitle="项目、飞书与模型版本" />
    <div className="filter-bar"><SelectField label="配置类型" value={kind} onValueChange={(value) => { setKind(value); setObject("all"); setFeedback(""); restore.reset(); }} options={kinds} /><SelectField label="对象" value={object} onValueChange={setObject} options={[{ value: "all", label: "全部对象" }, ...(objects.data ?? []).map((item) => ({ value: String(item.id), label: item.name }))]} /></div>
    {feedback && <p className="form-success" role="status">{feedback}</p>}<QueryState loading={history.isLoading} error={history.error || objects.error || restore.error} />
    <section className="section"><div className="table-scroll"><table><thead><tr><th>版本</th><th>对象</th><th>时间 / 操作者</th><th>变更</th><th aria-label="操作" /></tr></thead><tbody>{history.data?.map((revision) => <tr key={revision.id}><td>#{revision.id}<small className="table-sub">{({ baseline: "初始版本", created: "新增", updated: "修改", deleted: "删除" } as Record<string, string>)[revision.action]}</small></td><td>{objects.data?.find((item) => item.id === revision.object_id)?.name ?? `已删除对象 #${revision.object_id}`}</td><td>{formatTime(revision.created_at)}<small className="table-sub">{revision.actor}</small></td><td className="revision-changes"><details><summary>{revision.changes.length} 个字段</summary>{revision.changes.map((change) => <p key={change.field}><strong>{change.field}</strong><br />{change.secret ? "凭据已变更" : `${String(change.before ?? "未设置")} → ${String(change.after ?? "未设置")}`}</p>)}</details></td><td><button className="icon-button" title="恢复此版本内容" aria-label={`恢复版本 ${revision.id}`} disabled={restore.isPending || !revision.restorable || !objects.data?.some((item) => item.id === revision.object_id)} onClick={() => { if (window.confirm(`将对象 #${revision.object_id} 恢复为版本 #${revision.id} 的内容？历史凭据可能已被外部撤销。模型启用状态保持当前设置。`)) restore.mutate(revision); }}><RotateCcw size={16} /></button></td></tr>)}{history.data?.length === 0 && <tr><td colSpan={5} className="empty-row">暂无配置版本</td></tr>}</tbody></table></div></section>
  </div>;
}
