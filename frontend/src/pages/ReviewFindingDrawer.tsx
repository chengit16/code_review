/** @description 按稳定身份展开当前发现，复用描述与反馈控件；冲突保留操作版本并要求显式刷新。 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Drawer, Tag } from "antd";
import { Link } from "react-router-dom";

import { getReviewFinding } from "../api/reviewFindings";
import { setFindingFeedback } from "../api/reviewConclusions";
import { QueryState } from "../ui/QueryState";
import { formatSeverity } from "../ui/format";

import { FindingActions } from "./FindingActions";
import type { FindingFeedbackChoice } from "./FindingActions";
import { FindingDescription } from "./FindingDescription";
import { feedbackCacheKeys } from "./findingFeedbackCache";
import "../styles/findings.css";

/** 关闭不改变反馈；只有管理员显示写入按钮，服务端仍校验角色和版本。 */
export function ReviewFindingDrawer({ token, findingId, canEdit, onClose }: {
  /** 内存会话。 */ token: string;
  /** URL 中的主身份。 */ findingId: string;
  /** 仅控制操作显示。 */ canEdit: boolean;
  /** 返回列表并清理详情地址。 */ onClose: () => void;
}) {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["review-finding", findingId], queryFn: ({ signal }) => getReviewFinding(token, findingId, signal) });
  const feedback = useMutation({
    mutationFn: ({ verdict, source_attempt, revision, job_id }: { verdict: FindingFeedbackChoice | null; source_attempt: number; revision: number; job_id: number }) => setFindingFeedback(token, job_id, findingId, { source_attempt, revision }, verdict),
    // 保存后刷新所有同源视图；失败不替换冻结的输入或自动重试。
    onSuccess: async () => { await Promise.all(feedbackCacheKeys.map((key) => client.invalidateQueries({ queryKey: [key] }))); },
  });
  const finding = query.data;
  return <Drawer open title="评审发现详情" size={800} onClose={feedback.isPending ? undefined : onClose} closable={!feedback.isPending} mask={{ closable: !feedback.isPending }}>
    <QueryState loading={query.isLoading} error={query.error} onRetry={() => void query.refetch()} />
    {feedback.error && <div role="alert"><p>{feedback.error.message}；操作目标和版本已保留，未自动重试。请刷新核对后重新选择反馈。</p><p>{findingId} · 来源 {feedback.variables?.source_attempt} / 版本 {feedback.variables?.revision} · 选择 {feedback.variables?.verdict ?? "撤销"}</p><Button onClick={async () => { await query.refetch(); feedback.reset(); }}>刷新并重新核对</Button></div>}
    {finding && <><p><Link to={`/jobs/${finding.job_id}#job-result`}>任务 #{finding.job_id}</Link> · {finding.repository_name} · 提交人 {finding.commit_author?.trim() || "未记录"}</p>
      <p><Tag>{formatSeverity(finding.severity)}</Tag><Tag color={finding.handling === "handled" ? "green" : "orange"}>{finding.handling === "handled" ? "已处理" : "待处理"}</Tag></p>
      <p className="mono file-path">{finding.path}{finding.start_line ? `:${finding.start_line}` : ""}</p>
      <p>来源尝试 {finding.source_attempt} · 版本 {finding.revision} · <code>{finding.finding_id}</code></p>
      <FindingDescription content={finding.content} />
      {canEdit && <FindingActions index={0} marked={finding.feedback === "unmarked" ? undefined : finding.feedback} canSubmit={!feedback.isPending && !feedback.error && !query.isFetching && !query.error} onFeedback={(_, verdict) => feedback.mutate({ ...finding, verdict })} />}
      <p>有帮助、误报或忽略均表示已处理；再次点击当前反馈可撤销。已处理不代表代码已修复。</p>
      {finding.issue_id && <p><Link to={`/issues?issue=${finding.issue_id}&status=all`}>查看原问题 #{finding.issue_id} 的修复记录与跨任务历史</Link></p>}
    </>}
  </Drawer>;
}
