/** @description 合并前 MR 版本、发现与背景摘要；服务端状态决定当前结论。 */

import { useQuery } from "@tanstack/react-query";
import { GitPullRequest } from "lucide-react";
import { useState } from "react";

import { apiRequest } from "../api/client";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { formatSeverity } from "../ui/format";
import { formatTime } from "../ui/format";

interface PremergeReview {
  id: number;
  repository_name: string;
  mr_iid: number;
  head_sha: string;
  status: string;
  result_json: string | null;
  changed_files?: string | null;
  context_json?: string | null;
  error: string | null;
  created_at: string;
}

/** 旧版本即使曾有结果，也只显示失效状态，不当成当前审查结论。 */
export function PremergePage({ token }: { /** 内存口令。 */ token: string }) {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const reviews = useQuery({ queryKey: ["premerge-reviews"], queryFn: () => apiRequest<PremergeReview[]>(token, "/api/premerge-reviews"), refetchInterval: 10000 });
  const detail = useQuery({ queryKey: ["premerge-review", selectedId], queryFn: () => apiRequest<PremergeReview>(token, `/api/premerge-reviews/${selectedId}`), enabled: selectedId !== null, refetchInterval: 10000 });
  const labels: Record<string, string> = { queued: "排队中", running: "审查中", complete: "完成", partial: "部分完成", skipped: "无可审查文件", failed: "失败", superseded: "已失效" };
  return <div className="page"><PageHeader title="合并前审查" subtitle="按 MR 提交版本查看完整差异结果" /><QueryState loading={reviews.isLoading} error={reviews.error} />
    <section className="section"><div className="table-scroll responsive-table"><table><thead><tr><th>项目 / MR</th><th>提交版本</th><th>状态</th><th>发现</th><th>接收时间</th></tr></thead><tbody>
      {reviews.data?.map((review) => {
        const result = review.result_json ? JSON.parse(review.result_json) as { comments?: unknown[] } : null;
        return <tr key={review.id}><td data-label="项目 / MR"><GitPullRequest size={15} aria-hidden="true" /> {review.repository_name} !{review.mr_iid}</td><td data-label="提交版本" className="mono" title={review.head_sha}>{review.head_sha.slice(0, 12)}</td><td data-label="状态">{labels[review.status] ?? review.status}</td><td data-label="发现">{review.status === "superseded" ? "旧版本" : result?.comments?.length ?? review.error ?? "待处理"}</td><td data-label="接收时间">{formatTime(review.created_at)} <button className="button button-secondary" type="button" onClick={() => setSelectedId(review.id)}>详情</button></td></tr>;
      })}
      {reviews.data?.length === 0 && <tr><td className="empty-row" colSpan={5}>暂无合并前审查</td></tr>}
    </tbody></table></div></section>
    {selectedId !== null && <section className="section"><div className="section-head"><h2>审查详情</h2><button className="button button-secondary" type="button" onClick={() => setSelectedId(null)}>关闭</button></div><QueryState loading={detail.isLoading} error={detail.error} />{detail.data && <>
      <p>版本 {detail.data.head_sha} · {labels[detail.data.status] ?? detail.data.status}</p>
      {detail.data.error && <p className="form-error" role="alert">{detail.data.error}</p>}
      {detail.data.status === "superseded" && <p>该版本已失效，请以最新 MR 提交为准。</p>}
      {detail.data.context_json && (() => {
        const context = JSON.parse(detail.data.context_json) as { digest: string; sources: Array<{ kind: string; label: string; characters: number; digest: string }> };
        return <><h3>业务上下文</h3><p>本次上下文摘要 {context.digest}</p><ul>{context.sources.map((source) => <li key={`${source.kind}-${source.label}`}>{source.label} · {source.characters} 字 · 摘要 {source.digest}</li>)}</ul></>;
      })()}
      {detail.data.status !== "superseded" && (() => {
        const result = detail.data.result_json ? JSON.parse(detail.data.result_json) as { comments?: { path?: string; start_line?: number; severity?: string; content?: string }[] } : null;
        const files = detail.data.changed_files ? JSON.parse(detail.data.changed_files) as { path: string }[] : [];
        return <><h3>变更文件</h3><ul>{files.map((file) => <li key={file.path} className="mono">{file.path}</li>)}</ul><h3>发现</h3>{result?.comments?.length ? <ul>{result.comments.map((item, index) => <li key={index}><strong>{formatSeverity(item.severity)}</strong> {item.path ?? ""}{item.start_line ? `:${item.start_line}` : ""}<p>{item.content}</p></li>)}</ul> : <p>暂无发现</p>}</>;
      })()}</>}
    </section>}
  </div>;
}
