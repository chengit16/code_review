/** @description 合并前 MR 版本检索与分页；默认每个 MR 只显示最新接收版本，失效结果保留历史。 */
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { apiRequest } from "../api/client";
import { parsePremergeResult, premergeLabels } from "../api/premerge";
import type { PremergeReview } from "../api/premerge";
import type { Repository } from "../api/types";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { SelectField } from "../ui/SelectField";
import { formatTime } from "../ui/format";
import { PremergeDetail } from "./PremergeDetail";

/** 列表与选中版本保存在 URL，可分享、刷新及返回；不触发外部评审。 */
export function PremergePage({ token }: { /** 内存凭据。 */ token: string }) {
  const [params, setParams] = useSearchParams();
  const query = new URLSearchParams(params); query.delete("review");
  const reviews = useQuery({ queryKey: ["premerge-reviews", query.toString()], queryFn: ({ signal }) => apiRequest<{ items: PremergeReview[]; total: number; page: number; page_size: number }>(token, `/api/premerge-search?${query}`, { signal }),
    refetchInterval: (current) => current.state.data?.items.some((item) => ["queued", "running"].includes(item.status)) ? 10000 : 30000 });
  const repositories = useQuery({ queryKey: ["repositories"], queryFn: () => apiRequest<Repository[]>(token, "/api/repositories") });
  const page = reviews.data?.page ?? 1;
  const pages = Math.max(1, Math.ceil((reviews.data?.total ?? 0) / (reviews.data?.page_size ?? 25)));
  const selected = Number(params.get("review")) || null;
  function filter(key: string, value: string) {
    const next = new URLSearchParams(params); next.delete("page"); next.delete("review");
    if (value) next.set(key, value); else next.delete(key); setParams(next);
  }
  function select(id: number | null) { const next = new URLSearchParams(params); if (id) next.set("review", String(id)); else next.delete("review"); setParams(next); }
  function paginate(nextPage: number) { const next = new URLSearchParams(params); next.delete("review"); next.set("page", String(nextPage)); setParams(next); }
  return <div className="page"><PageHeader title="合并前审查" subtitle="默认查看每个 MR 的最新版本，旧版本按需展开" />
    <form className="premerge-filters" key={query.toString()} onSubmit={(event) => { event.preventDefault(); filter("mr_iid", String(new FormData(event.currentTarget).get("mr_iid") ?? "").trim()); }}>
      <SelectField label="项目" value={params.get("repository_id") ?? "all"} onValueChange={(value) => filter("repository_id", value === "all" ? "" : value)} options={[{ value: "all", label: "全部项目" }, ...(repositories.data ?? []).map((item) => ({ value: String(item.id), label: item.name }))]} />
      <SelectField label="状态" value={params.get("status") ?? "all"} onValueChange={(value) => filter("status", value === "all" ? "" : value)} options={[{ value: "all", label: "全部状态" }, ...Object.entries(premergeLabels).map(([value, label]) => ({ value, label }))]} />
      <label>MR IID<input name="mr_iid" type="number" min="1" defaultValue={params.get("mr_iid") ?? ""} placeholder="全部 MR" /></label><button className="button button-secondary">查询 MR</button>
    </form>
    <label className="checkbox-label version-toggle"><input type="checkbox" checked={params.get("latest_only") === "false"} onChange={(event) => filter("latest_only", event.target.checked ? "false" : "")} />包含历史版本（旧版本不代表当前结论）</label>
    <QueryState loading={reviews.isLoading} error={reviews.error || repositories.error} onRetry={() => { void reviews.refetch(); void repositories.refetch(); }} />
    {selected && <PremergeDetail key={selected} token={token} id={selected} onClose={() => select(null)} />}
    <section className="section"><div className="table-scroll responsive-table"><table><thead><tr><th>项目 / MR</th><th>提交版本</th><th>状态</th><th>发现</th><th>接收时间</th><th aria-label="操作" /></tr></thead><tbody>
      {reviews.data?.items.map((review) => { const result = parsePremergeResult(review.result_json); return <tr key={review.id}><td data-label="项目 / MR">{review.repository_name}<small className="table-sub">MR !{review.mr_iid}</small></td><td data-label="提交版本" className="mono" title={review.head_sha}>{review.head_sha.slice(0, 12)}</td><td data-label="状态">{premergeLabels[review.status]}</td><td data-label="发现">{review.status === "superseded" ? "旧版本" : result.valid ? `${result.comments.length} 条（以覆盖结论为准）` : "尚无有效结果"}</td><td data-label="接收时间">{formatTime(review.created_at)}</td><td data-label="操作"><button className="button button-secondary" onClick={() => select(review.id)}>详情 #{review.id}</button></td></tr>; })}
      {!reviews.isLoading && !reviews.error && reviews.data?.items.length === 0 && <tr><td colSpan={6} className="empty-row">当前条件下没有审查记录。需要接入时请在<Link to="/repositories">项目配置</Link>开启合并前审查。</td></tr>}
    </tbody></table></div></section>
    <div className="pagination" aria-label="合并前审查分页"><span>共 {reviews.data?.total ?? 0} 条 · 第 {page} / {pages} 页</span><button className="button button-secondary" disabled={page <= 1 || reviews.isFetching} onClick={() => paginate(page - 1)}>上一页</button><button className="button button-secondary" disabled={page >= pages || reviews.isFetching} onClick={() => paginate(page + 1)}>下一页</button></div>
  </div>;
}
