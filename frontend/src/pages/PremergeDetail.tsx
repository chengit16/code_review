/** @description 合并前详情的有效性提示与安全发现展示；旧版本和失败结果不冒充完整结论。 */
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { apiRequest } from "../api/client";
import { parsePremergeResult, premergeLabels } from "../api/premerge";
import type { PremergeReview } from "../api/premerge";
import { QueryState } from "../ui/QueryState";
import { formatSeverity } from "../ui/format";
import { PremergeEvidence } from "./PremergeEvidence";

/** 地址栏决定当前版本，刷新后仍能恢复详情；只轮询未结束的审查。 */
export function PremergeDetail({ token, id, onClose }: {
  /** 内存凭据。 */ token: string;
  /** 版本编号。 */ id: number;
  /** 关闭详情但保留列表筛选。 */ onClose: () => void;
}) {
  const query = useQuery({ queryKey: ["premerge-review", id], queryFn: ({ signal }) => apiRequest<PremergeReview>(token, `/api/premerge-reviews/${id}`, { signal }),
    refetchInterval: (current) => ["running", "queued"].includes(current.state.data?.status ?? "") ? 10000 : false });
  const review = query.data;
  const result = parsePremergeResult(review?.result_json ?? null);
  const message = !review ? "" : review.status === "superseded" ? "该版本已失效，不代表当前 MR 的审查结论。请查看最新版本。" :
    review.status === "failed" ? "审查失败，无法形成完整结论。已生成的发现仅供核查，不代表其余文件没有问题。" :
    review.status === "partial" ? "仅完成部分审查，未覆盖的文件仍需核查，不能视为全部通过。" :
    ["queued", "running"].includes(review.status) ? "尚未完成审查，请等待最终结果。" :
    review.status === "skipped" ? "没有可审查文件，不等于代码已通过检查。" :
    !result.valid || !result.completeCoverage ? "缺少有效结果或完整覆盖证明，不能判定为未发现问题。" :
    result.comments.length ? `审查完成，发现 ${result.comments.length} 条问题。` : "完整审查已完成，未发现问题。";
  return <section className="section premerge-detail" aria-labelledby="premerge-detail-title"><div className="section-head"><h2 id="premerge-detail-title">审查详情 #{id}</h2><button className="button button-secondary" onClick={onClose}>关闭详情</button></div>
    <QueryState loading={query.isLoading} error={query.error} onRetry={() => void query.refetch()} />
    {review && <><p>{review.repository_name} · MR !{review.mr_iid} · {premergeLabels[review.status]}</p><p className="mono file-path">{review.head_sha}</p><p className={review.status === "complete" && result.completeCoverage ? "result-note" : "attention-note"}>{message}</p>
      {review.error && <p className="form-error" role="alert">{review.error} <Link to="/repositories">检查项目接入与配置 →</Link></p>}
      {review.status !== "superseded" && result.comments.length > 0 && <div className="findings">{result.comments.map((item, index) => <article className="finding" key={index} data-severity={item.severity ?? "none"}><div className="finding-head"><span className="mono finding-path">{item.path}{item.start_line ? `:${item.start_line}` : ""}</span><span>{formatSeverity(item.severity)}</span></div><p className="finding-body">{item.content}</p></article>)}</div>}
      {review.status !== "superseded" && review.status === "complete" && !result.valid && <p>结果格式不可用，请检查服务版本；不要把本次结果当作通过。</p>}
      <PremergeEvidence filesJson={review.changed_files} contextJson={review.context_json} />
      <p className="coverage-note">合并前审查仅展示评审结果，不自动阻止 GitLab 合并，也不自动发送飞书或发布行内评论。</p>
    </>}
  </section>;
}
