/** @description 合并前 MR 版本检索与分页；默认每个 MR 只显示最新接收版本，失效结果保留历史。 */
import { useQuery } from "@tanstack/react-query";
import { Button, Checkbox, Drawer, Input, Tag } from "antd";
import type { TableColumnsType } from "antd";
import { Link, useSearchParams } from "react-router-dom";

import { apiRequest } from "../api/client";
import { premergeLabels } from "../api/premerge";
import type { PremergeReview } from "../api/premerge";
import type { Repository } from "../api/types";
import { ListSelect as SelectField, ListStatusNav, ListTime, ListToolbar, ListConditions } from "../ui/ListControls";
import { ListTable } from "../ui/ListTable";
import { PageHeader } from "../ui/PageHeader";
import { Pagination } from "../ui/Pagination";
import { QueryState } from "../ui/QueryState";
import { formatSeverity } from "../ui/format";

import { PremergeDetail } from "./PremergeDetail";

/** 列表与选中版本保存在 URL，可分享、刷新及返回；不触发外部评审。 */
export function PremergePage({ token }: { /** 内存凭据。 */ token: string }) {
  const [params, setParams] = useSearchParams();
  const query = new URLSearchParams(params); query.delete("review"); query.set("summary_only", "true");
  const reviews = useQuery({ queryKey: ["premerge-reviews", query.toString()], queryFn: ({ signal }) => apiRequest<{ items: PremergeReview[]; total: number; page: number; page_size: number; status_counts?: Record<string, number> }>(token, `/api/premerge-search?${query}`, { signal }),
    refetchInterval: (current) => current.state.data?.items.some((item) => ["queued", "running"].includes(item.status)) ? 10000 : 30000 });
  const repositories = useQuery({ queryKey: ["repositories"], queryFn: () => apiRequest<Repository[]>(token, "/api/repositories") });
  const page = Math.max(1, Number(params.get("page")) || 1);
  const selected = Number(params.get("review")) || null;
  function filter(key: string, value: string) {
    const next = new URLSearchParams(params); next.delete("page"); next.delete("review");
    if (value) next.set(key, value); else next.delete(key); setParams(next);
  }
  function select(id: number | null) { const next = new URLSearchParams(params); if (id) next.set("review", String(id)); else next.delete("review"); setParams(next); }
  function paginate(nextPage: number) { const next = new URLSearchParams(params); next.delete("review"); next.set("page", String(nextPage)); setParams(next); }
  const columns: TableColumnsType<PremergeReview> = [
    { title: "项目 / MR", key: "source", width: 240, render: (_: unknown, item) => <><span className="list-primary">{item.repository_name} · MR !{item.mr_iid}</span><span className="list-secondary mono">{item.head_sha.slice(0, 12)}</span></> },
    { title: "状态", dataIndex: "status", key: "status", width: 110, render: (value: PremergeReview["status"]) => <Tag color={value === "failed" ? "red" : "default"}>{premergeLabels[value] ?? value}</Tag> },
    { title: "覆盖 / 发现", key: "findings", render: (_: unknown, item) => {
      const summary = item.summary;
      if (item.status === "superseded") return "旧版本，不代表当前结论";
      if (!summary?.result_available) return "尚无有效结果 · 待核实";
      return <><span>{summary.findings_count} 条发现{summary.highest_severity ? ` · 最高${formatSeverity(summary.highest_severity)}` : ""}</span>
        <span className="list-secondary">{summary.coverage === "complete" ? "选中范围完整覆盖" : summary.coverage === "partial" ? "覆盖不完整" : "覆盖待核实"}{summary.excluded_count ? ` · 排除 ${summary.excluded_count}` : summary.excluded_count == null ? " · 排除范围待核实" : ""}{summary.waived_count ? ` · 豁免 ${summary.waived_count}` : ""}</span></>;
    } },
    { title: "接收时间", dataIndex: "created_at", key: "created_at", width: 170, render: (value: string) => <ListTime value={value} /> },
    { title: "操作", key: "action", width: 110, render: (_: unknown, item) => <Button type="link" onClick={() => select(item.id)}>详情 #{item.id}</Button> },
  ];
  return <div className="page"><PageHeader title="合并前审查" subtitle="默认查看每个 MR 的最新版本，旧版本按需展开" />
    <section className="list-surface"><ListStatusNav value={params.get("status") ?? "all"} labels={{ all: "全部", ...premergeLabels }} counts={reviews.error ? undefined : reviews.data?.status_counts} onChange={(value) => filter("status", value === "all" ? "" : value)} />
    <form className="list-toolbar" key={query.toString()} onSubmit={(event) => { event.preventDefault(); filter("mr_iid", String(new FormData(event.currentTarget).get("mr_iid") ?? "").trim()); }}>
      <SelectField label="项目" value={params.get("repository_id") ?? "all"} onValueChange={(value) => filter("repository_id", value === "all" ? "" : value)} options={[{ value: "all", label: "全部项目" }, ...(repositories.data ?? []).map((item) => ({ value: String(item.id), label: item.name }))]} />
      <label>MR IID<Input name="mr_iid" type="number" min="1" defaultValue={params.get("mr_iid") ?? ""} placeholder="全部 MR" /></label><Button htmlType="submit">查询 MR</Button><Button onClick={() => { const next = new URLSearchParams(params); for (const key of ["repository_id", "mr_iid", "status", "page", "latest_only", "review"]) next.delete(key); setParams(next); }}>重置</Button>
    </form>
    <ListToolbar advanced={<Checkbox className="version-toggle" checked={params.get("latest_only") === "false"} onChange={(event) => filter("latest_only", event.target.checked ? "false" : "")}>包含历史版本（旧版本不代表当前结论）</Checkbox>}>{null}</ListToolbar>
    <ListConditions items={[{ key: "repository_id", label: "项目", value: params.get("repository_id") ?? "" }, { key: "mr_iid", label: "MR", value: params.get("mr_iid") ?? "" }, { key: "latest_only", label: "版本范围", value: params.get("latest_only") === "false" ? "含历史版本" : "" }]} onClear={(key) => filter(key, "")} />
    <QueryState loading={reviews.isLoading} error={reviews.error || repositories.error} onRetry={() => { void reviews.refetch(); void repositories.refetch(); }} />
    {selected && <Drawer className="premerge-drawer" open placement="right" width={760} title={null} onClose={() => select(null)} destroyOnHidden><PremergeDetail key={selected} token={token} id={selected} onClose={() => select(null)} onOpenReview={select} /></Drawer>}
    <ListTable rowKey="id" columns={columns} dataSource={reviews.data?.items ?? []} loading={reviews.isFetching} locale={{ emptyText: reviews.error ? "无法读取审查记录" : <span>当前条件下没有审查记录。需要接入时请在<Link to="/repositories">项目配置</Link>开启合并前审查。</span> }} scroll={{ x: 820 }} pagination={false} />
    <Pagination label="合并前审查分页" page={page} pageSize={reviews.data?.page_size ?? 25} total={reviews.error ? undefined : reviews.data?.total} disabled={reviews.isFetching || Boolean(reviews.error)} onPage={paginate} onPageSize={(size) => filter("page_size", String(size))} />
    </section>
  </div>;
}
