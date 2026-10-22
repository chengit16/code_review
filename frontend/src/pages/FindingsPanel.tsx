/** @description 任务发现筛选和就地处理；问题状态以服务端为准，索引始终使用原始结果位置。 */
import { useState } from "react";
import { Link } from "react-router-dom";

import type { ReviewComment, ReviewJobDetail } from "../api/types";
import { SelectField } from "../ui/SelectField";
import { formatSeverity } from "../ui/format";

type Verdict = "helpful" | "false_positive" | "fixed";

const issueLabels = { open: "待处理", fixed: "已修复", ignored: "已忽略，无需处理", merged: "已合并" };
const feedbackOptions = [
  { value: "helpful", label: "有帮助", title: "认可此发现，不代表处理完成" },
  { value: "false_positive", label: "误报", title: "确认为误报，同步忽略关联问题，无需重复处理" },
  { value: "fixed", label: "已修复", title: "确认代码已修复，同步关闭关联问题" },
] as const;

/** 文件、级别和反馈筛选只改变视图，服务端继续校验原始发现索引。 */
export function FindingsPanel({ comments, feedback, issueIds = {}, issueStatuses = {}, status, coverageWaived, onFeedback, pending, canEdit = true }: {
  /** OCR 发现原始顺序。 */ comments: ReviewComment[];
  /** 原始索引对应的人工标记。 */ feedback: Record<number, Verdict>;
  /** 当前尝试中原始发现索引对应的待跟进问题。 */ issueIds?: Record<number, number>;
  /** 服务端返回的关联问题状态，不能由反馈替代。 */ issueStatuses?: ReviewJobDetail["issue_statuses"];
  /** 任务当前状态。 */ status: string;
  /** 是否有未审核豁免文件。 */ coverageWaived: boolean;
  /** 发送原始索引及新标记。 */ onFeedback: (index: number, verdict: Verdict | null) => void;
  /** 保存期间禁止重复触发。 */ pending: boolean;
  /** 只控制反馈按钮，服务端仍执行角色授权。 */ canEdit?: boolean;
}) {
  const [severity, setSeverity] = useState("all");
  const [file, setFile] = useState("all");
  const [verdict, setVerdict] = useState("all");
  const files = [...new Set(comments.map((comment) => comment.path))].sort();
  const visible = comments.map((comment, index) => ({ comment, index })).filter(({ comment, index }) =>
    (severity === "all" || (comment.severity ?? "none") === severity) &&
    (file === "all" || comment.path === file) &&
    (verdict === "all" || (feedback[index] ?? "unmarked") === verdict));
  const canSubmit = !pending && ["complete", "partial", "failed", "skipped"].includes(status);

  return <section className="section findings-section">
    <div className="section-head"><h2>评审发现</h2><span>{visible.length} / {comments.length} 条</span></div>
    {comments.length > 0 && <>
      <p className="coverage-note">可直接在此处理：“误报”会同步忽略关联问题，“已修复”会同步关闭，无需再去待跟进问题重复操作。“有帮助”仅表示认可发现。</p>
      <div className="filter-bar finding-filters">
        <SelectField label="严重级别" value={severity} onValueChange={setSeverity} options={[{ value: "all", label: "全部级别" }, ...[...new Set(comments.map((comment) => comment.severity ?? "none"))].map((value) => ({ value, label: value === "none" ? "未分级" : formatSeverity(value) }))]} />
        <SelectField label="文件" value={file} onValueChange={setFile} options={[{ value: "all", label: "全部文件" }, ...files.map((value) => ({ value, label: value }))]} />
        <SelectField label="反馈" value={verdict} onValueChange={setVerdict} options={[{ value: "all", label: "全部反馈" }, { value: "unmarked", label: "未标记" }, ...feedbackOptions.map(({ value, label }) => ({ value, label }))]} />
      </div>
    </>}
    {visible.length ? <div className="findings">{visible.map(({ comment, index }) => {
      const issueStatus = issueStatuses[index];
      const marked = feedback[index];
      // 旧反馈可能尚未同步问题，允许原地重新确认，不在升级时批量改写人工决定。
      const needsSync = issueStatus === "open" && (marked === "false_positive" || marked === "fixed");
      return <article className="finding" data-severity={comment.severity ?? "none"} key={`${comment.path}-${index}`}>
        <div className="finding-head">
          <span className="mono finding-path">{comment.path}{comment.start_line ? `:${comment.start_line}` : ""}</span>
          <span className="finding-severity">{formatSeverity(comment.severity)}</span>
        </div>
        <div className="finding-body"><p>{comment.content}</p></div>
        <div className="finding-footer">
          {issueIds[index] ? <Link className="finding-issue-link" to={`/issues?issue=${issueIds[index]}`}>
            跟进问题 #{issueIds[index]}{issueStatus ? ` · ${issueLabels[issueStatus]}` : ""}
          </Link> : <span />}
          {canEdit && <div className="finding-feedback" role="group" aria-label={`发现 ${index + 1} 的反馈`}>
            {needsSync && <button type="button" disabled={!canSubmit} title="重新确认已有标记，同步处理关联问题" onClick={() => onFeedback(index, marked)}>同步处理</button>}
            {feedbackOptions.map((item) => <button key={item.value} type="button" title={item.title}
              aria-pressed={marked === item.value} disabled={!canSubmit}
              onClick={() => onFeedback(index, marked === item.value ? null : item.value)}>{item.label}</button>)}
          </div>}
        </div>
      </article>;
    })}</div> : <p className="empty-inline">{comments.length === 0 && status === "complete" && !coverageWaived ? "评审完成，未发现问题" : comments.length ? "没有符合筛选条件的发现" : "暂无可展示的发现"}</p>}
  </section>;
}
