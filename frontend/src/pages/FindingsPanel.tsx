/** @description 任务发现筛选和就地处理；问题状态以服务端为准，索引始终使用原始结果位置。 */
import { Select, Tag } from "antd";
import { useState } from "react";
import { Link } from "react-router-dom";

import type { ReviewComment, ReviewJobDetail } from "../api/types";
import { formatCategory, formatSeverity } from "../ui/format";

import { FindingActions, findingFeedbackOptions } from "./FindingActions";
import type { FindingFeedbackChoice, FindingVerdict } from "./FindingActions";
import { FindingDescription } from "./FindingDescription";
import "../styles/findings.css";

const issueLabels = { open: "待处理", fixed: "已修复", ignored: "已忽略", false_positive: "误报", merged: "已合并" };
const severityColors: Record<string, string> = { critical: "red", high: "red", medium: "gold", low: "blue" };

/** 文件、级别和反馈筛选只改变视图，服务端继续校验原始发现索引。 */
export function FindingsPanel({ comments, findingIds, findingSources, feedback, issueIds = {}, issueStatuses = {}, status, coverageWaived, onFeedback, pending, canEdit = true, initialIssueState = "all" }: {
  /** OCR 发现原始顺序。 */ comments: ReviewComment[];
  /** 聚合后的稳定来源身份，不作为旧接口索引。 */ findingIds?: string[];
  /** 每条发现的可读来源。 */ findingSources?: string[];
  /** 原始索引对应的人工标记。 */ feedback: Record<number, FindingVerdict>;
  /** 当前尝试中原始发现索引对应的待跟进问题。 */ issueIds?: Record<number, number>;
  /** 服务端返回的关联问题状态，不能由反馈替代。 */ issueStatuses?: ReviewJobDetail["issue_statuses"];
  /** 任务当前状态。 */ status: string;
  /** 是否有未审核豁免文件。 */ coverageWaived: boolean;
  /** 发送原始索引及新标记。 */ onFeedback: (index: number, verdict: FindingFeedbackChoice | null) => void;
  /** 保存期间禁止重复触发。 */ pending: boolean;
  /** 只控制反馈按钮，服务端仍执行角色授权。 */ canEdit?: boolean;
  /** 详情直达时的初始视图，筛选只改变展示，不提交处置。 */ initialIssueState?: "all" | "open";
}) {
  const [severity, setSeverity] = useState("all");
  const [file, setFile] = useState("all");
  const [verdict, setVerdict] = useState("all");
  const [issueState, setIssueState] = useState<string>(initialIssueState);
  const files = [...new Set(comments.map((comment) => comment.path))].sort();
  // 筛选不改变原始索引；反馈与关联问题状态各自使用服务端事实。
  const visible = comments.map((comment, index) => ({ comment, index })).filter(({ comment, index }) =>
    ((severity === "all" || (comment.severity ?? "none") === severity) &&
    (file === "all" || comment.path === file) &&
    (issueState === "all" || issueStatuses[index] === issueState) &&
    (verdict === "all" || (feedback[index] === "fixed" ? "unmarked" : feedback[index] ?? "unmarked") === verdict)));
  const canSubmit = !pending && ["complete", "partial", "failed", "skipped"].includes(status);
  const filtersLocked = pending;

  return <section className="section findings-section">
    <div className="section-head"><h2>评审发现</h2><span>{visible.length} / {comments.length} 条</span></div>
    {comments.length > 0 && <>
      <p className="finding-help"><strong>这条 review 对你有用吗？</strong>有帮助、误报、忽略只能选一项，再次点击可撤销。修复等处理请进入跟进问题，反馈不会改变问题状态。</p>
      <div className="filter-bar finding-filters">
        <label>严重级别<Select disabled={filtersLocked} aria-label="发现的严重级别" value={severity} onChange={setSeverity} options={[{ value: "all", label: "全部级别" }, ...[...new Set(comments.map((comment) => comment.severity ?? "none"))].map((value) => ({ value, label: value === "none" ? "未分级" : formatSeverity(value) }))]} /></label>
        <label>文件<Select disabled={filtersLocked} aria-label="发现的文件" value={file} onChange={setFile} options={[{ value: "all", label: "全部文件" }, ...files.map((value) => ({ value, label: value }))]} /></label>
        <label>反馈<Select disabled={filtersLocked} aria-label="发现的反馈" value={verdict} onChange={setVerdict} options={[{ value: "all", label: "全部反馈" }, { value: "unmarked", label: "未评价" }, ...findingFeedbackOptions.map(({ value, label }) => ({ value, label }))]} /></label>
        <label>问题处理<Select disabled={filtersLocked} aria-label="发现的问题处理" value={issueState} onChange={setIssueState} options={[{ value: "all", label: "全部问题" }, { value: "open", label: "待处理问题" }, { value: "ignored", label: "已忽略问题" }, { value: "fixed", label: "已修复问题" }, { value: "false_positive", label: "误报问题" }]} /></label>
      </div>
    </>}
    {visible.length ? <div className="findings">{visible.map(({ comment, index }) => {
      const issueStatus = issueStatuses[index];
      return <article className="finding finding-card" aria-label={`发现 ${index + 1}`} data-severity={comment.severity ?? "none"} key={findingIds?.[index] ?? `${comment.path}-${index}`}>
        <div className="finding-head">
          <div className="finding-meta"><strong>发现 {index + 1}</strong><Tag color={severityColors[comment.severity ?? ""]}>{formatSeverity(comment.severity)}</Tag><Tag>{formatCategory(comment.category)}</Tag></div>
          <span className="mono finding-path">{comment.path}{comment.start_line ? `:${comment.start_line}` : ""}</span>
        </div>
        <div className="finding-body">{findingSources?.[index] && <small className="finding-source">{findingSources[index]}</small>}<FindingDescription content={comment.content} /></div>
        <div className="finding-footer">
          {issueIds[index] ? <Link className="finding-issue-link" to={`/issues?issue=${issueIds[index]}`}>
            跟进问题 #{issueIds[index]}{issueStatus ? ` · ${issueLabels[issueStatus]}` : ""}
          </Link> : <span />}
          {canEdit && <FindingActions index={index} marked={feedback[index]}
            canSubmit={canSubmit} onFeedback={onFeedback} />}
        </div>
      </article>;
    })}</div> : <p className="empty-inline">{comments.length === 0 && status === "complete" && !coverageWaived ? "评审完成，未发现问题" : comments.length ? "没有符合筛选条件的发现" : "暂无可展示的发现"}</p>}
  </section>;
}
