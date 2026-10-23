/** @description 展示业务对账差异并允许管理员下载不含业务正文的诊断包。 */

import { useMutation, useQuery } from "@tanstack/react-query";
import { Download, RefreshCw } from "lucide-react";

import { apiRequest } from "../api/client";
import { QueryState } from "../ui/QueryState";

interface ReconciliationIssue {
  code: string;
  object_type: string;
  object_id: number | string;
  detail: string;
}

interface ReconciliationReport {
  generated_at: string;
  issue_count: number;
  checked: Record<string, number>;
  orphan_artifact_directories: number;
  issues: ReconciliationIssue[];
}

/** 差异报告只读；修复仍需管理员按具体业务事实单独处理。 */
export function ReconciliationPanel({ token }: { /** 管理台内存会话。 */ token: string }) {
  const report = useQuery({
    queryKey: ["reconciliation"],
    queryFn: () => apiRequest<ReconciliationReport>(token, "/api/reconciliation"),
  });
  const download = useMutation({
    mutationFn: () => apiRequest<Record<string, unknown>>(token, "/api/diagnostics/export"),
    onSuccess: (bundle) => {
      const url = URL.createObjectURL(new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" }));
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "open-code-review-diagnostics.json";
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    },
  });
  const data = report.data;

  return <section className="section operation-card reconciliation-card">
    <div className="section-head"><h2>数据对账</h2><div className="row-actions">
      <button className="icon-button" type="button" title="刷新对账" aria-label="刷新对账" onClick={() => void report.refetch()}><RefreshCw size={17} /></button>
      <button className="button button-secondary" type="button" disabled={download.isPending} onClick={() => download.mutate()}><Download size={16} />下载诊断包</button>
    </div></div>
    <p className="reconciliation-note">检查事件、任务、尝试、通知与工件目录之间的一致性。报告不会自动修复业务数据。</p>
    <QueryState loading={report.isLoading} error={report.error || download.error} />
    {data && <>
      <div className="reconciliation-summary"><strong>{data.issue_count}</strong><span>项待核对差异</span><span>已检查 {data.checked.events} 个事件、{data.checked.jobs} 个任务、{data.orphan_artifact_directories} 个孤儿工件目录</span></div>
      {data.issues.length > 0 ? <ul className="reconciliation-issues">{data.issues.map((issue, index) => <li key={`${issue.code}-${issue.object_type}-${issue.object_id}-${index}`}><code>{issue.code}</code><span>{issue.object_type} #{issue.object_id} · {issue.detail}</span></li>)}</ul> : <p className="empty-inline">当前没有发现不一致。</p>}
      <p className="reconciliation-timestamp">检查时间：{new Date(data.generated_at).toLocaleString("zh-CN")}</p>
    </>}
    {download.isSuccess && <p className="form-success" role="status">诊断包已下载；内容不含凭据、评审正文或原始代码。</p>}
  </section>;
}
