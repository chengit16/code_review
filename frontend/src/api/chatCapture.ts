/** @description 管理员聊天收件箱协议；只读取脱敏摘要、暂停授权和更正关联，不发送新会话路径。 */
import { apiRequest } from "./client";

/** 已显式绑定的会话和采集事实；是否持续运行还需检查最近成功时间。 */
export interface ChatBinding {
  id: number; thread_id: string; enabled: boolean; version: number; since_ms: number;
  last_checked_at: string | null; last_success_at: string | null; last_error_code: string;
  last_message_ms: number | null; last_scan_count: number;
}

/** 来源只保留脱敏摘要；自动受理不代表故障或部署已经确认。 */
export interface ChatEvent {
  id: number; binding_id: number; turn_id: string; message_id: string;
  role: "user" | "assistant"; classification: "issue" | "pending" | "progress";
  excerpt: string; source_ms: number; improvement_id: number | null; version: number; created_at: string;
}

/** 分页结果和真实计数；查询失败不得降级为空。 */
export interface ChatInbox {
  bindings: ChatBinding[]; items: ChatEvent[]; pending: number; total: number; page: number; page_size: number;
}

/** 查询绑定和脱敏来源，支持页面卸载取消。 */
export function getChatInbox(token: string, page: number, pageSize: number, signal?: AbortSignal, classification = "") {
  return apiRequest<ChatInbox>(token, `/api/chat-capture?page=${page}&page_size=${pageSize}${classification ? `&classification=${encodeURIComponent(classification)}` : ""}`, { signal });
}

/** 仅暂停或恢复已存在绑定；并发版本冲突由调用方显示，不重试覆盖。 */
export function setChatBinding(token: string, binding: ChatBinding) {
  const bindingId = binding.id;
  return apiRequest(token, `/api/chat-capture/bindings/${bindingId}`, {
    method: "PUT", body: JSON.stringify({ enabled: !binding.enabled, expected_version: binding.version }),
  });
}

/** 追加可逆关联或提升待核实线索，不更改正式问题的验证与部署状态。 */
export function linkChatEvent(token: string, event: ChatEvent, improvementId: number | null, promote = false) {
  const eventId = event.id;
  return apiRequest<ChatEvent>(token, `/api/chat-capture/events/${eventId}/link`, {
    method: "POST", body: JSON.stringify({ expected_version: event.version, improvement_id: improvementId, promote }),
  });
}
