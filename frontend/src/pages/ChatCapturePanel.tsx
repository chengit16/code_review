/** @description 管理员混合记录收件箱；展示真实采集健康、待核实来源和可逆关联，不推断验收结论。 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Drawer, Input } from "antd";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { getChatInbox, linkChatEvent, setChatBinding } from "../api/chatCapture";
import type { ChatBinding, ChatEvent } from "../api/chatCapture";
import { ListExcerpt, ListSelect, ListTime } from "../ui/ListControls";
import { ListTable } from "../ui/ListTable";
import { Pagination } from "../ui/Pagination";
import { QueryState } from "../ui/QueryState";
import { formatTime } from "../ui/format";

function isRecent(time: string | null) {
  if (!time) return false;
  const age = Date.now() - Date.parse(time.includes("T") ? time : `${time.replace(" ", "T")}Z`);
  return age >= 0 && age < 120_000;
}

/** 仅在工具分区与收件箱均展开时每五秒读取；未运行、暂停和查询失败分别显示。 */
export function ChatCapturePanel({ token, active = true }: { /** 仅内存管理员会话，服务端仍验证角色。 */ token: string; /** 所在工具分区可见时才读取与轮询。 */ active?: boolean }) {
  const [params, setParams] = useSearchParams();
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<ChatEvent | null>(null);
  const page = Math.max(1, Number(params.get("chat_page")) || 1);
  const pageSize = [25, 50, 100].includes(Number(params.get("chat_page_size"))) ? Number(params.get("chat_page_size")) : 25;
  const classification = params.get("chat_classification") ?? "";
  function update(key: string, value: string) {
    const next = new URLSearchParams(params); if (value && value !== "all") next.set(`chat_${key}`, value); else next.delete(`chat_${key}`);
    if (key !== "page") next.delete("chat_page"); setParams(next);
  }
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["chat-capture", page, pageSize, classification], enabled: active && open, queryFn: ({ signal }) => getChatInbox(token, page, pageSize, signal, classification), refetchInterval: active && open ? 5000 : false });
  const toggle = useMutation({ mutationFn: (binding: ChatBinding) => setChatBinding(token, binding), onSuccess: () => void client.invalidateQueries({ queryKey: ["chat-capture"] }) });
  return <details className="section" onToggle={(event) => setOpen(event.currentTarget.open)}><summary>聊天自动受理与待核实收件箱{query.data ? ` · 全范围待核实 ${query.data.pending} 条` : ""}</summary>
    <p className="muted">仅采集本机显式绑定的项目会话，后台每 30 秒检查，页面每 5 秒读取。不是即时推送，也不保证语义零遗漏；疑似问题自动受理，其他消息保留待核实。验证和部署仍以实际证据为准。</p>
    <QueryState loading={query.isLoading} error={query.error} onRetry={() => void query.refetch()} />
    {query.data && !query.isError && <>
      {query.data.bindings.length === 0 && <p>尚未绑定会话，不会自动读取其他聊天。</p>}
      {query.data.bindings.map((binding) => <article key={binding.id}><p>绑定 #{binding.id} · {binding.enabled ? binding.last_error_code ? "采集失败，等待重试" : isRecent(binding.last_success_at) ? "近期采集正常" : "采集未启动或已过期" : "已暂停"} · 最近成功 {formatTime(binding.last_success_at)}</p>
        {binding.enabled && (!isRecent(binding.last_success_at) || binding.last_error_code) && <p role="alert">会话采集尚未确认正常；请核对 monitor 与会话权限。{binding.last_error_code && `原因码：${binding.last_error_code}`}</p>}
        <p className="muted">起始范围 {new Date(binding.since_ms).toLocaleString("zh-CN")} · 上轮核对 {binding.last_scan_count} 条</p>
        <Button disabled={toggle.isPending} onClick={() => toggle.mutate(binding)}>{binding.enabled ? "暂停采集" : "恢复采集"} #{binding.id}</Button></article>)}
      {toggle.error && <p role="alert">{toggle.error.message}</p>}
      <div className="list-toolbar"><ListSelect label="来源分类" value={classification || "all"} onValueChange={(value) => update("classification", value)} options={[{ value: "all", label: "全部分类" }, { value: "issue", label: "疑似问题" }, { value: "pending", label: "待核实" }, { value: "progress", label: "进展线索" }]} /></div>
      <ListTable onOpenRow={setSelected} rowLabel={(event) => `查看来源 ${event.id}`} rowKey="id" dataSource={query.data.items} pagination={false} scroll={{ x: 800 }} locale={{ emptyText: "尚无匹配摄取记录；不能由空列表推断聊天中没有问题" }} columns={[
        { title: "来源 / 分类", key: "source", width: 160, render: (_, event) => <><Button type="link" aria-label="详情 / 关联" onClick={() => setSelected(event)}>来源 #{event.id}</Button><span className="list-secondary">{event.classification === "issue" ? "疑似问题，自动受理" : event.classification === "progress" ? "进展线索" : "待核实"}</span></> },
        { title: "脱敏摘要", key: "excerpt", render: (_, event) => <ListExcerpt text={event.excerpt} limit={70} /> },
        { title: "关联记录", key: "linked", width: 140, render: (_, event) => event.improvement_id ? <Link to={`/improvements/${event.improvement_id}`}>记录 #{event.improvement_id}</Link> : "未关联正式记录" },
        { title: "来源时间", key: "time", width: 140, render: (_, event) => <ListTime value={new Date(event.source_ms).toISOString()} /> },
      ]} />
      <Pagination label="聊天收件箱分页" total={query.data.total} page={page} pageSize={pageSize} disabled={query.isFetching} onPage={(value) => update("page", String(value))} onPageSize={(size) => update("page_size", String(size))} />
      <Drawer open={selected !== null && active && open} title={selected ? `来源 #${selected.id} · 关联与核实` : "来源详情"} onClose={() => setSelected(null)} destroyOnHidden>{selected && <EventRow key={selected.id} event={selected} token={token} onSaved={setSelected} />}</Drawer>
    </>}
  </details>;
}

function EventRow({ event, token, onSaved }: { event: ChatEvent; token: string; onSaved: (event: ChatEvent) => void }) {
  const [target, setTarget] = useState("");
  const client = useQueryClient();
  const change = useMutation({ mutationFn: ({ id, promote }: { id: number | null; promote?: boolean }) => linkChatEvent(token, event, id, promote),
    // 仅采用本次写入返回的版本，不让后台轮询覆盖正在编辑的目标编号。
    onSuccess: (saved) => { onSaved(saved); void client.invalidateQueries({ queryKey: ["chat-capture"] }); void client.invalidateQueries({ queryKey: ["improvements"] }); } });
  return <article className="attempt-evidence"><h3>来源 #{event.id} · {event.classification === "issue" ? "疑似问题，自动受理" : event.classification === "progress" ? "进展线索" : "待核实"}</h3>
    <p className="prewrap">{event.excerpt}</p><p>{new Date(event.source_ms).toLocaleString("zh-CN")} · {event.improvement_id ? <Link to={`/improvements/${event.improvement_id}`}>查看关联记录 #{event.improvement_id}</Link> : "未关联正式记录"}</p>
    <form className="improvement-search chat-capture-actions" onSubmit={(e) => { e.preventDefault(); change.mutate({ id: Number(target) }); }}><label>来源 #{event.id} 关联记录编号<Input type="number" min={1} step={1} required value={target} onChange={(e) => setTarget(e.target.value)} /></label><Button htmlType="submit" disabled={change.isPending}>关联已有记录</Button>
      {event.improvement_id ? <Button disabled={change.isPending} onClick={() => change.mutate({ id: null })}>解除关联</Button> : <Button disabled={change.isPending} onClick={() => change.mutate({ id: null, promote: true })}>建立待核实记录</Button>}</form>
    {change.error && <p role="alert">{change.error.message}；输入已保留，请刷新核对版本。</p>}
  </article>;
}
