/** @description 管理员混合记录收件箱；展示真实采集健康、待核实来源和可逆关联，不推断验收结论。 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { getChatInbox, linkChatEvent, setChatBinding } from "../api/chatCapture";
import type { ChatBinding, ChatEvent } from "../api/chatCapture";
import { Pagination } from "../ui/Pagination";
import { QueryState } from "../ui/QueryState";
import { formatTime } from "../ui/format";

function isRecent(time: string | null) {
  if (!time) return false;
  const age = Date.now() - Date.parse(time.includes("T") ? time : `${time.replace(" ", "T")}Z`);
  return age >= 0 && age < 120_000;
}

/** 默认每五秒读状态，后台每三十秒摄取；未运行、暂停和查询失败分别显示。 */
export function ChatCapturePanel({ token }: { /** 仅内存管理员会话，服务端仍验证角色。 */ token: string }) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["chat-capture", page, pageSize], queryFn: ({ signal }) => getChatInbox(token, page, pageSize, signal), refetchInterval: 5000 });
  const toggle = useMutation({ mutationFn: (binding: ChatBinding) => setChatBinding(token, binding), onSuccess: () => void client.invalidateQueries({ queryKey: ["chat-capture"] }) });
  return <details className="section"><summary>聊天自动受理与待核实收件箱{query.data ? ` · 待核实 ${query.data.pending} 条` : ""}</summary>
    <p className="muted">仅采集本机显式绑定的项目会话，后台每 30 秒检查，页面每 5 秒读取。不是即时推送，也不保证语义零遗漏；疑似问题自动受理，其他消息保留待核实。验证和部署仍以实际证据为准。</p>
    <QueryState loading={query.isLoading} error={query.error} onRetry={() => void query.refetch()} />
    {query.data && !query.isError && <>
      {query.data.bindings.length === 0 && <p>尚未绑定会话，不会自动读取其他聊天。</p>}
      {query.data.bindings.map((binding) => <article key={binding.id}><p>绑定 #{binding.id} · {binding.enabled ? binding.last_error_code ? "采集失败，等待重试" : isRecent(binding.last_success_at) ? "近期采集正常" : "采集未启动或已过期" : "已暂停"} · 最近成功 {formatTime(binding.last_success_at)}</p>
        {binding.enabled && (!isRecent(binding.last_success_at) || binding.last_error_code) && <p role="alert">会话采集尚未确认正常；请核对 monitor 与会话权限。{binding.last_error_code && `原因码：${binding.last_error_code}`}</p>}
        <p className="muted">起始范围 {new Date(binding.since_ms).toLocaleString("zh-CN")} · 上轮核对 {binding.last_scan_count} 条</p>
        <button className="button button-secondary" type="button" disabled={toggle.isPending} onClick={() => toggle.mutate(binding)}>{binding.enabled ? "暂停采集" : "恢复采集"} #{binding.id}</button></article>)}
      {toggle.error && <p role="alert">{toggle.error.message}</p>}
      {query.data.items.map((event) => <EventRow key={event.id} event={event} token={token} />)}
      {query.data.total === 0 && <p>尚无摄取记录；不能由空列表推断聊天中没有问题。</p>}
      <Pagination label="聊天收件箱分页" total={query.data.total} page={page} pageSize={pageSize} disabled={query.isFetching} onPage={setPage} onPageSize={(size) => { setPageSize(size); setPage(1); }} />
    </>}
  </details>;
}

function EventRow({ event, token }: { event: ChatEvent; token: string }) {
  const [target, setTarget] = useState("");
  const client = useQueryClient();
  const change = useMutation({ mutationFn: ({ id, promote }: { id: number | null; promote?: boolean }) => linkChatEvent(token, event, id, promote),
    onSuccess: () => { void client.invalidateQueries({ queryKey: ["chat-capture"] }); void client.invalidateQueries({ queryKey: ["improvements"] }); } });
  return <article className="attempt-evidence"><h3>来源 #{event.id} · {event.classification === "issue" ? "疑似问题，自动受理" : event.classification === "progress" ? "进展线索" : "待核实"}</h3>
    <p className="prewrap">{event.excerpt}</p><p>{new Date(event.source_ms).toLocaleString("zh-CN")} · {event.improvement_id ? <Link to={`/improvements/${event.improvement_id}`}>查看关联记录 #{event.improvement_id}</Link> : "未关联正式记录"}</p>
    <form className="improvement-search chat-capture-actions" onSubmit={(e) => { e.preventDefault(); change.mutate({ id: Number(target) }); }}><label>来源 #{event.id} 关联记录编号<input type="number" min={1} step={1} required value={target} onChange={(e) => setTarget(e.target.value)} /></label><button className="button button-secondary" disabled={change.isPending}>关联已有记录</button>
      {event.improvement_id ? <button className="button button-secondary" type="button" disabled={change.isPending} onClick={() => change.mutate({ id: null })}>解除关联</button> : <button className="button button-secondary" type="button" disabled={change.isPending} onClick={() => change.mutate({ id: null, promote: true })}>建立待核实记录</button>}</form>
    {change.error && <p role="alert">{change.error.message}；输入已保留，请刷新核对版本。</p>}
  </article>;
}
