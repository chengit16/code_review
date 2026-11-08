/** @description 主动告警配置和通知历史；草稿跨视图及轮询保留，保存不代表已发送通知。 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Card, Checkbox, Input, Select } from "antd";
import { useSearchParams } from "react-router-dom";

import { apiRequest } from "../api/client";
import type { NotificationTarget } from "../api/types";
import { ListExcerpt, ListTime } from "../ui/ListControls";
import { ListTable as Table } from "../ui/ListTable";
import { QueryState } from "../ui/QueryState";
import { Status } from "../ui/Status";
import { useConfigurationDraft } from "../ui/useConfigurationDraft";

interface Config { enabled: number | boolean; target_id: number | null; queue_minutes: number }
interface Alerts { config: Config; deliveries: { id: number; message: string; status: string; attempts: number; error: string | null; created_at: string }[] }

function Editor({ token, config, targets, unavailable }: { token: string; config: Config; targets: NotificationTarget[]; unavailable: boolean }) {
  const draft = useConfigurationDraft(config);
  const value = draft.value;
  const client = useQueryClient();
  // 保存使用提交时快照；不以查询刷新重新挂载编辑器，避免丢失未提交输入。
  const save = useMutation({ retry: false, mutationFn: (payload: Config) => apiRequest(token, "/api/alerts/config", { method: "PUT", body: JSON.stringify(payload) }), onSuccess: (_, payload) => {
    client.setQueryData<Alerts>(["alerts"], (old) => old ? { ...old, config: payload } : old);
    draft.saved(); void client.invalidateQueries({ queryKey: ["alerts"] });
  } });
  const valid = value && Number.isInteger(value.queue_minutes) && value.queue_minutes >= 1 && value.queue_minutes <= 1440 && (!value.enabled || value.target_id !== null);
  if (!value) return null;
  return <form className="operations-alert-form" onSubmit={(event) => { event.preventDefault(); if (valid && !save.isPending && !unavailable) save.mutate({ ...value }); }}>
    <Checkbox className="alert-toggle" checked={Boolean(value.enabled)} disabled={save.isPending} onChange={(event) => draft.setValue({ ...value, enabled: event.target.checked })}>主动飞书告警</Checkbox>
    <div><label htmlFor="alert-target">告警通道</label><Select id="alert-target" value={value.target_id ?? "none"} disabled={save.isPending || unavailable} options={[{ value: "none", label: "未选择" }, ...targets.map((target) => ({ value: target.id, label: target.name }))]} onChange={(target) => draft.setValue({ ...value, target_id: target === "none" ? null : Number(target) })} /></div>
    <div><label htmlFor="alert-threshold">队列等待阈值（分钟）</label><Input id="alert-threshold" type="number" min={1} max={1440} value={Number.isNaN(value.queue_minutes) ? "" : value.queue_minutes} disabled={save.isPending} onChange={(event) => draft.setValue({ ...value, queue_minutes: event.target.value === "" ? NaN : Number(event.target.value) })} /></div>
    <Button htmlType="submit" type="primary" loading={save.isPending} disabled={!draft.dirty || !valid || unavailable}>保存告警设置</Button>
    {draft.dirty && <p role="status">告警设置有未保存更改，切换分区后仍保留。</p>}
    {save.isSuccess && !draft.dirty && <p role="status">告警配置已保存，不代表告警已发送。</p>}
    {save.error && <p className="form-error" role="alert">{save.error.message}；草稿保留。</p>}
  </form>;
}

/** 隐藏视图停止读取与轮询，但保留草稿和查询结果；单条重发不重跑评审。 */
export function AlertsPanel({ token, active = true }: {
  /** 内存管理口令。 */ token: string;
  /** 当前分区可见时才启用后台请求。 */ active?: boolean;
}) {
  const client = useQueryClient();
  const [params, setParams] = useSearchParams();
  const page = Math.max(1, Math.floor(Number(params.get("alerts_page"))) || 1);
  const setPage = (value: number) => { const next = new URLSearchParams(params); next.set("alerts_page", String(value)); setParams(next); };
  const query = useQuery({ queryKey: ["alerts"], enabled: active, queryFn: ({ signal }) => apiRequest<Alerts>(token, "/api/alerts", { signal }), refetchInterval: active ? 30000 : false });
  const targets = useQuery({ queryKey: ["notification-targets"], enabled: active, queryFn: ({ signal }) => apiRequest<NotificationTarget[]>(token, "/api/notification-targets", { signal }) });
  const retry = useMutation({ retry: false, mutationFn: (id: number) => apiRequest(token, `/api/alerts/${id}/retry`, { method: "POST" }), onSuccess: () => void client.invalidateQueries({ queryKey: ["alerts"] }) });
  return <div className="operations-alerts-section"><QueryState loading={query.isLoading || targets.isLoading} error={query.error || targets.error || retry.error} />
    {query.data && <>
      <Card title="主动告警设置"><p className="operations-caption">由独立 monitor 检查与发送；配置成功和通知投递成功是两件事。</p><Editor token={token} config={query.data.config} targets={targets.data ?? []} unavailable={!targets.data || !!targets.error} /></Card>
      <Card title="告警与恢复通知"><p className="operations-caption">仅显示最近 100 条投递，不代表全部历史或实时活跃告警数量。</p><Table rowKey="id" dataSource={query.data.deliveries} size="small" scroll={{ x: 750 }} pagination={{ current: Math.min(page, Math.max(1, Math.ceil(query.data.deliveries.length / 10))), onChange: setPage, pageSize: 10, showSizeChanger: false }} locale={{ emptyText: "暂无告警通知" }} columns={[
        { title: "消息", dataIndex: "message", width: 300, render: (message: string) => <ListExcerpt text={message} limit={70} /> }, { title: "状态", dataIndex: "status", render: (status: string) => <Status value={status} /> },
        { title: "尝试", dataIndex: "attempts" }, { title: "时间", dataIndex: "created_at", render: (time: string) => <ListTime value={time} /> },
        { title: "诊断", dataIndex: "error", render: (error: string | null) => <ListExcerpt text={error} /> },
        { title: "操作", render: (_, item) => item.status === "failed" && <Button aria-label={`重发告警 ${item.id}`} disabled={retry.isPending} onClick={() => retry.mutate(item.id)}>重发</Button> },
      ]} /></Card>
    </>}
  </div>;
}
