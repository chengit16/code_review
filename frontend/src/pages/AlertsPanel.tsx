/** @description 主动告警配置与投递历史；配置草稿不会被后台轮询覆盖。 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RotateCcw, Save } from "lucide-react";
import { useState } from "react";

import { apiRequest } from "../api/client";
import type { NotificationTarget } from "../api/types";
import { QueryState } from "../ui/QueryState";
import { SelectField } from "../ui/SelectField";
import { Status } from "../ui/Status";
import { formatTime } from "../ui/format";

interface Config { enabled: number | boolean; target_id: number | null; queue_minutes: number }
interface Alerts { config: Config; deliveries: { id: number; message: string; status: string; attempts: number; error: string | null; created_at: string }[] }

function Editor({ token, config, targets }: { token: string; config: Config; targets: NotificationTarget[] }) {
  const [enabled, setEnabled] = useState(Boolean(config.enabled));
  const [target, setTarget] = useState(config.target_id ? String(config.target_id) : "none");
  const [minutes, setMinutes] = useState(config.queue_minutes);
  const client = useQueryClient();
  const save = useMutation({ mutationFn: () => apiRequest(token, "/api/alerts/config", { method: "PUT", body: JSON.stringify({ enabled, target_id: target === "none" ? null : Number(target), queue_minutes: minutes }) }), onSuccess: () => void client.invalidateQueries({ queryKey: ["alerts"] }) });
  return <form className="filter-bar" onSubmit={(event) => { event.preventDefault(); save.mutate(); }}><label className="checkbox-label"><input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} />主动飞书告警</label><SelectField label="告警通道" value={target} onValueChange={setTarget} options={[{ value: "none", label: "未选择" }, ...targets.map((item) => ({ value: String(item.id), label: item.name }))]} /><label>队列等待阈值（分钟）<input type="number" min="1" max="1440" value={minutes} onChange={(event) => setMinutes(Number(event.target.value))} /></label><button className="button button-secondary" disabled={save.isPending}><Save size={16} />保存告警设置</button>{save.error && <p className="form-error" role="alert">{save.error.message}</p>}</form>;
}

/** 独立监控服务投递后的事实在此展示，不把保存开关当作告警发送成功。 */
export function AlertsPanel({ token }: { /** 内存口令。 */ token: string }) {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["alerts"], queryFn: () => apiRequest<Alerts>(token, "/api/alerts"), refetchInterval: 30000 });
  const targets = useQuery({ queryKey: ["notification-targets"], queryFn: () => apiRequest<NotificationTarget[]>(token, "/api/notification-targets") });
  const retry = useMutation({ mutationFn: (id: number) => apiRequest(token, `/api/alerts/${id}/retry`, { method: "POST" }), onSuccess: () => void client.invalidateQueries({ queryKey: ["alerts"] }) });
  return <section className="section"><div className="section-head"><h2>告警与恢复通知</h2></div><QueryState loading={query.isLoading} error={query.error || targets.error || retry.error} />{query.data && <><Editor key={JSON.stringify(query.data.config)} token={token} config={query.data.config} targets={targets.data ?? []} /><div className="table-scroll"><table><thead><tr><th>消息</th><th>状态</th><th>尝试</th><th>时间</th><th>诊断</th><th aria-label="操作" /></tr></thead><tbody>{query.data.deliveries.map((item) => <tr key={item.id}><td>{item.message}</td><td><Status value={item.status} /></td><td>{item.attempts}</td><td>{formatTime(item.created_at)}</td><td>{item.error}</td><td>{item.status === "failed" && <button className="icon-button" aria-label={`重发告警 ${item.id}`} title="重发告警" disabled={retry.isPending} onClick={() => retry.mutate(item.id)}><RotateCcw size={16} /></button>}</td></tr>)}</tbody></table></div></>}</section>;
}
