/**
 * @description 展示最近 Webhook 请求的接收结论与固定原因码。
 *
 * 未通过鉴权的项目与分支仅为请求自称值，不能当作已确认的 GitLab 事实。
 */

import { useQuery } from "@tanstack/react-query";

import { apiRequest } from "../api/client";
import type { Repository, WebhookDiagnostic } from "../api/types";
import { QueryState } from "../ui/QueryState";
import { Status } from "../ui/Status";
import { formatTime } from "../ui/format";

const reasons: Record<string, string> = {
  queued: "已加入事件队列",
  duplicate: "重复投递，未重复建任务",
  event_ignored: "事件不满足处理条件",
  push_disabled: "项目未启用默认分支 Push",
  merge_disabled: "项目未启用 MR 合并事件",
  merge_not_completed: "MR 事件不是合并动作",
  target_branch_mismatch: "目标分支与项目配置不符",
  invalid_push_range: "Push 提交范围不满足条件",
  authentication_failed: "Webhook Token 或签名校验失败",
  project_mismatch: "载荷中的目标项目不匹配",
  invalid_payload: "GitLab 事件字段无效",
  invalid_json: "请求体不是有效 JSON",
  unmatched_project_or_branch: "未找到启用的项目和目标分支",
  repository_unavailable: "项目不存在或已暂停",
  secret_unavailable: "服务端无法读取 Webhook 密钥",
  body_too_large: "请求体超过 1 MB",
  rejected: "投递被拒绝",
};

/** 展示最近 100 条脱敏投递记录，并自动刷新最近状态。 */
export function WebhookDiagnosticsPanel({ token, repositories }: {
  /** 内存中的管理口令。 */ token: string;
  /** 只用于已匹配仓库的名称展示。 */ repositories: Repository[];
}) {
  const diagnostics = useQuery({
    queryKey: ["webhook-diagnostics"],
    queryFn: () => apiRequest<WebhookDiagnostic[]>(token, "/api/webhook-diagnostics"),
    refetchInterval: 10000,
  });

  return <section className="section webhook-diagnostics">
    <div className="section-head"><h2>Webhook 投递诊断</h2><span>最近 100 次请求</span></div>
    <QueryState loading={diagnostics.isLoading} error={diagnostics.error} />
    <div className="table-scroll responsive-table"><table><thead><tr><th>时间</th><th>项目</th><th>声明项目 ID</th><th>声明分支</th><th>类型</th><th>结论</th><th>HTTP</th><th>原因</th></tr></thead><tbody>
      {diagnostics.data?.map((item) => <tr key={item.id}>
        <td data-label="时间">{formatTime(item.created_at)}</td>
        <td data-label="项目">{repositories.find((repo) => repo.id === item.repository_id)?.name ?? "未匹配"}</td>
        <td data-label="声明项目 ID" className="mono">{item.claimed_project_id ?? "—"}</td>
        <td data-label="声明分支" className="mono">{item.claimed_branch ?? "—"}</td>
        <td data-label="类型">{item.event_kind === "merge_request" ? "MR" : item.event_kind === "push" ? "Push" : "其他"}</td>
        <td data-label="结论"><Status value={item.outcome} /></td>
        <td data-label="HTTP" className="mono">{item.http_status}</td>
        <td data-label="原因" className="diagnostic">{reasons[item.reason] ?? item.reason}</td>
      </tr>)}
      {diagnostics.data?.length === 0 && <tr><td colSpan={8} className="empty-row">尚无 Webhook 投递记录</td></tr>}
    </tbody></table></div>
  </section>;
}
