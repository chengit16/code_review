/** @description 任务发现筛选和反馈；索引始终使用原始结果位置，避免筛选后反馈错位。 */
import { useState } from "react";

import type { ReviewComment } from "../api/types";
import { SelectField } from "../ui/SelectField";

type Verdict = "helpful" | "false_positive" | "fixed";

/** 文件、级别和反馈筛选只改变视图，服务端继续校验原始发现索引。 */
export function FindingsPanel({ comments, feedback, status, coverageWaived, onFeedback, pending, canEdit = true }: {
  /** OCR 发现原始顺序。 */ comments: ReviewComment[];
  /** 原始索引对应的人工标记。 */ feedback: Record<number, Verdict>;
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
  return <section className="section"><div className="section-head"><h2>评审发现</h2><span>{visible.length} / {comments.length} 条</span></div>{comments.length > 0 && <div className="filter-bar"><SelectField label="严重级别" value={severity} onValueChange={setSeverity} options={[{ value: "all", label: "全部级别" }, ...[...new Set(comments.map((comment) => comment.severity ?? "none"))].map((value) => ({ value, label: value === "none" ? "未分级" : value }))]} /><SelectField label="文件" value={file} onValueChange={setFile} options={[{ value: "all", label: "全部文件" }, ...files.map((value) => ({ value, label: value }))]} /><SelectField label="反馈" value={verdict} onValueChange={setVerdict} options={[{ value: "all", label: "全部反馈" }, { value: "unmarked", label: "未标记" }, { value: "helpful", label: "有帮助" }, { value: "false_positive", label: "误报" }, { value: "fixed", label: "已修复" }]} /></div>}{visible.length ? <div className="findings">{visible.map(({ comment, index }) => <article className="finding" key={`${comment.path}-${index}`}><div className="finding-meta"><span className="mono">{comment.path}{comment.start_line ? `:${comment.start_line}` : ""}</span><span>{comment.severity ?? "未分级"}</span></div><p>{comment.content}</p>{canEdit && <div className="finding-feedback" role="group" aria-label={`发现 ${index + 1} 的反馈`}>{([{ value: "helpful", label: "有帮助" }, { value: "false_positive", label: "误报" }, { value: "fixed", label: "已修复" }] as const).map((item) => <button key={item.value} type="button" aria-pressed={feedback[index] === item.value} disabled={pending || !["complete", "partial", "failed", "skipped"].includes(status)} onClick={() => onFeedback(index, feedback[index] === item.value ? null : item.value)}>{item.label}</button>)}</div>}</article>)}</div> : <p className="empty-inline">{comments.length === 0 && status === "complete" && !coverageWaived ? "评审完成，未发现问题" : comments.length ? "没有符合筛选条件的发现" : "暂无可展示的发现"}</p>}</section>;
}
