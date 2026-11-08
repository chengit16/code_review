/** @description 合并前 MR 版本检索与分页；默认每个 MR 只显示最新接收版本，失效结果保留历史。 */
import { useQuery } from "@tanstack/react-query";
import { Drawer, Table } from "antd";
import type { TableColumnsType } from "antd";
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
  const selected = Number(params.get("review")) || null;
  function filter(key: string, value: string) {
    const next = new URLSearchParams(params); next.delete("page"); next.delete("review");
    if (value) next.set(key, value); else next.delete(key); setParams(next);
  }
  function select(id: number | null) { const next = new URLSearchParams(params); if (id) next.set("review", String(id)); else next.delete("review"); setParams(next); }
  function paginate(nextPage: number) { const next = new URLSearchParams(params); next.delete("review"); next.set("page", String(nextPage)); setParams(next); }
  const columns: TableColumnsType<PremergeReview> = [
    { title: "项目 / MR", key: "source", width: 190, render: (_: unknown, item) => <>{item.repository_name}<small className="table-sub">MR !{item.mr_iid}</small></> },
    { title: "提交版本", dataIndex: "head_sha", key: "head_sha", width: 145, render: (value: string) => <span className="mono" title={value}>{value.slice(0, 12)}</span> },
    { title: "状态", dataIndex: "status", key: "status", width: 110, render: (value: PremergeReview["status"]) => premergeLabels[value] },
    { title: "发现", key: "findings", width: 150, render: (_: unknown, item) => { const result = parsePremergeResult(item.result_json); return item.status === "superseded" ? "旧版本" : result.valid ? `${result.comments.length} 条（以覆盖结论为准）` : "尚无有效结果"; } },
    { title: "接收时间", dataIndex: "created_at", key: "created_at", width: 170, render: (value: string) => formatTime(value) },
    { title: "操作", key: "action", width: 110, render: (_: unknown, item) => <button className="button button-secondary" onClick={() => select(item.id)}>详情 #{item.id}</button> },
  ];
  return <div className="page"><PageHeader title="合并前审查" subtitle="默认查看每个 MR 的最新版本，旧版本按需展开" />
    <form className="premerge-filters" key={query.toString()} onSubmit={(event) => { event.preventDefault(); filter("mr_iid", String(new FormData(event.currentTarget).get("mr_iid") ?? "").trim()); }}>
      <SelectField label="项目" value={params.get("repository_id") ?? "all"} onValueChange={(value) => filter("repository_id", value === "all" ? "" : value)} options={[{ value: "all", label: "全部项目" }, ...(repositories.data ?? []).map((item) => ({ value: String(item.id), label: item.name }))]} />
      <SelectField label="状态" value={params.get("status") ?? "all"} onValueChange={(value) => filter("status", value === "all" ? "" : value)} options={[{ value: "all", label: "全部状态" }, ...Object.entries(premergeLabels).map(([value, label]) => ({ value, label }))]} />
      <label>MR IID<input name="mr_iid" type="number" min="1" defaultValue={params.get("mr_iid") ?? ""} placeholder="全部 MR" /></label><button className="button button-secondary">查询 MR</button>
    </form>
    <label className="checkbox-label version-toggle"><input type="checkbox" checked={params.get("latest_only") === "false"} onChange={(event) => filter("latest_only", event.target.checked ? "false" : "")} />包含历史版本（旧版本不代表当前结论）</label>
    <QueryState loading={reviews.isLoading} error={reviews.error || repositories.error} onRetry={() => { void reviews.refetch(); void repositories.refetch(); }} />
    {selected && <Drawer className="premerge-drawer" open placement="right" width={760} title={null} onClose={() => select(null)} destroyOnHidden><PremergeDetail key={selected} token={token} id={selected} onClose={() => select(null)} onOpenReview={select} /></Drawer>}
    <section className="section premerge-table-section"><Table rowKey="id" size="middle" columns={columns} dataSource={reviews.data?.items ?? []} loading={reviews.isFetching} locale={{ emptyText: reviews.error ? "无法读取审查记录" : <span>当前条件下没有审查记录。需要接入时请在<Link to="/repositories">项目配置</Link>开启合并前审查。</span> }} scroll={{ x: 850 }} pagination={{ current: page, pageSize: reviews.data?.page_size ?? 25, total: reviews.data?.total ?? 0, showSizeChanger: true, pageSizeOptions: [25, 50, 100], locale: { items_per_page: "条/页", prev_page: "上一页", next_page: "下一页", page: "页", jump_to: "跳至", page_size: "每页条数" }, showTotal: (total, range) => `${range[0]}-${range[1]} / ${total} 条`, disabled: reviews.isFetching || Boolean(reviews.error), onChange: (nextPage, size) => { if (size !== (reviews.data?.page_size ?? 25)) filter("page_size", String(size)); else paginate(nextPage); } }} /></section>
  </div>;
}
