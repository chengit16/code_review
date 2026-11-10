/** @description 任务发现按持久化反馈展示已处理和待处理；筛选保留原始索引，不修改跟进问题。 */
import { Select, Tag } from "antd";
import { useState } from "react";
import { Link } from "react-router-dom";

import type { ReviewComment, ReviewJobDetail } from "../api/types";
import { formatCategory, formatSeverity } from "../ui/format";

import { FindingActions, findingFeedbackOptions, isFindingHandled } from "./FindingActions";
import type { FindingFeedbackChoice, FindingVerdict } from "./FindingActions";
import { FindingDescription } from "./FindingDescription";
import "../styles/findings.css";

const severityColors: Record<string, string> = { critical: "red", high: "red", medium: "gold", low: "blue" };

/** 文件、级别和反馈筛选只改变视图，服务端继续校验原始发现索引。 */
export function FindingsPanel({ comments, findingIds, findingSources, feedback, issueIds = {}, status, coverageWaived, onFeedback, pending, canEdit = true, initialIssueState = "all" }: {
  /** OCR 发现原始顺序。 */ comments: ReviewComment[];
  /** 聚合后的稳定来源身份，不作为旧接口索引。 */ findingIds?: string[];
  /** 每条发现的可读来源。 */ findingSources?: string[];
  /** 原始索引对应的人工标记。 */ feedback: Record<number, FindingVerdict>;
  /** 当前尝试中原始发现索引对应的待跟进问题。 */ issueIds?: Record<number, number>;
  /** 兼容既有调用方的跟进状态；发现处理状态仅按反馈判断，此字段不参与展示和筛选。 */ issueStatuses?: ReviewJobDetail["issue_statuses"];
  /** 任务当前状态。 */ status: string;
  /** 是否有未审核豁免文件。 */ coverageWaived: boolean;
  /** 发送原始索引及新标记。 */ onFeedback: (index: number, verdict: FindingFeedbackChoice | null) => void;
  /** 保存期间禁止重复触发。 */ pending: boolean;
  /** 只控制反馈按钮，服务端仍执行角色授权。 */ canEdit?: boolean;
  /** 详情直达的初始反馈处理视图；兼容旧 open 地址为尚未反馈，不提交问题处置。 */ initialIssueState?: "all" | "open";
}) {
  const [severity, setSeverity] = useState("all");
  const [file, setFile] = useState("all");
  const [verdict, setVerdict] = useState("all");
  const [issueState, setIssueState] = useState<string>(initialIssueState);
  const files = [...new Set(comments.map((comment) => comment.path))].sort();
  // 筛选不改变原始索引；发现有反馈即已处理，跟进问题的修复记录不影响此视图。
  const visible = comments.map((comment, index) => ({ comment, index })).filter(({ comment, index }) =>
    ((severity === "all" || (comment.severity ?? "none") === severity) &&
    (file === "all" || comment.path === file) &&
    (issueState === "all" || (issueState === "handled" ? isFindingHandled(feedback[index]) : !isFindingHandled(feedback[index]))) &&
    (verdict === "all" || (feedback[index] === "fixed" ? "unmarked" : feedback[index] ?? "unmarked") === verdict)));
  const canSubmit = !pending && ["complete", "partial", "failed", "skipped"].includes(status);
  const filtersLocked = pending;

  return <section className="section findings-section">
    <div className="section-head"><h2>评审发现</h2><span>{visible.length} / {comments.length} 条</span></div>
    {comments.length > 0 && <>
      <p className="finding-help"><strong>这条 review 对你有用吗？</strong>选择有帮助、误报或忽略即表示这条发现已处理，再次点击可撤销。代码修复记录可进入跟进问题查看。</p>
      <div className="filter-bar finding-filters">
        <label>严重级别<Select disabled={filtersLocked} aria-label="发现的严重级别" value={severity} onChange={setSeverity} options={[{ value: "all", label: "全部级别" }, ...[...new Set(comments.map((comment) => comment.severity ?? "none"))].map((value) => ({ value, label: value === "none" ? "未分级" : formatSeverity(value) }))]} /></label>
        <label>文件<Select disabled={filtersLocked} aria-label="发现的文件" value={file} onChange={setFile} options={[{ value: "all", label: "全部文件" }, ...files.map((value) => ({ value, label: value }))]} /></label>
        <label>反馈<Select disabled={filtersLocked} aria-label="发现的反馈" value={verdict} onChange={setVerdict} options={[{ value: "all", label: "全部反馈" }, { value: "unmarked", label: "未评价" }, ...findingFeedbackOptions.map(({ value, label }) => ({ value, label }))]} /></label>
        <label>处理状态<Select virtual={false} disabled={filtersLocked} aria-label="发现的处理状态" value={issueState} onChange={setIssueState} options={[{ value: "all", label: "全部发现" }, { value: "open", label: "待处理" }, { value: "handled", label: "已处理" }]} /></label>
      </div>
    </>}
    {visible.length ? <div className="findings">{visible.map(({ comment, index }) => {
      const handled = isFindingHandled(feedback[index]);
      return <article className="finding finding-card" aria-label={`发现 ${index + 1}`} data-severity={comment.severity ?? "none"} key={findingIds?.[index] ?? `${comment.path}-${index}`}>
        <div className="finding-head">
          <div className="finding-meta"><strong>发现 {index + 1}</strong><Tag color={severityColors[comment.severity ?? ""]}>{formatSeverity(comment.severity)}</Tag><Tag>{formatCategory(comment.category)}</Tag><Tag color={handled ? "green" : "orange"} aria-label={`发现 ${index + 1} 的处理状态`}>{handled ? "已处理" : "待处理"}</Tag></div>
          <span className="mono finding-path">{comment.path}{comment.start_line ? `:${comment.start_line}` : ""}</span>
        </div>
        <div className="finding-body">{findingSources?.[index] && <small className="finding-source">{findingSources[index]}</small>}<FindingDescription content={comment.content} /></div>
        <div className="finding-footer">
          {issueIds[index] ? <Link className="finding-issue-link" to={`/issues?issue=${issueIds[index]}`}>
            跟进问题 #{issueIds[index]}
          </Link> : <span />}
          {canEdit && <FindingActions index={index} marked={feedback[index]}
            canSubmit={canSubmit} onFeedback={onFeedback} />}
        </div>
      </article>;
    })}</div> : <p className="empty-inline">{comments.length === 0 && status === "complete" && !coverageWaived ? "评审完成，未发现问题" : comments.length ? "没有符合筛选条件的发现" : "暂无可展示的发现"}</p>}
  </section>;
}
