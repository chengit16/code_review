/** @description 管理审计只读查询；分页搜索保留在独立 URL 参数，不记录请求内容或凭据。 */
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { apiRequest } from "../api/client";
import type { AuditPage } from "../api/types";
import { ListSearch, ListTime } from "../ui/ListControls";
import { ListTable } from "../ui/ListTable";
import { Pagination } from "../ui/Pagination";
import { QueryState } from "../ui/QueryState";

/** 隐藏维护视图不轮询；审计不可在列表修改，授权仍由服务端负责。 */
export function AuditLogPanel({ token, active = true }: {
  /** 内存会话。 */ token: string;
  /** 当前分区可见时读取。 */ active?: boolean;
}) {
  const [params, setParams] = useSearchParams();
  const page = Math.max(1, Number(params.get("audit_page")) || 1);
  const pageSize = [25, 50, 100].includes(Number(params.get("audit_page_size"))) ? Number(params.get("audit_page_size")) : 25;
  const q = params.get("audit_q") ?? "";
  const query = useQuery({ queryKey: ["audit-logs", page, pageSize, q], enabled: active,
    queryFn: ({ signal }) => apiRequest<AuditPage>(token, `/api/audit-logs?${new URLSearchParams({ page: String(page), page_size: String(pageSize), q })}`, { signal }), refetchInterval: active ? 10000 : false });
  function update(key: string, value: string) {
    const next = new URLSearchParams(params); if (value) next.set(`audit_${key}`, value); else next.delete(`audit_${key}`);
    if (key !== "page") next.delete("audit_page"); setParams(next);
  }
  return <section className="section list-surface"><div className="section-head"><h2>管理操作审计</h2><span>{query.error ? "—" : query.data?.total ?? "—"} 条</span></div>
    <p className="form-note">只展示脱敏的操作人、动作、对象与结果，不保存请求内容、密码或密钥。</p>
    <div className="list-toolbar"><ListSearch key={q} label="搜索审计" value={q} onSearch={(value) => update("q", value)} placeholder="操作人、动作、对象类型或编号" /></div>
    <QueryState loading={query.isLoading} error={query.error} onRetry={() => void query.refetch()} />
    <ListTable rowKey="id" dataSource={query.data?.items ?? []} loading={query.isFetching} pagination={false} scroll={{ x: 750 }} locale={{ emptyText: query.error ? "无法读取审计" : "暂无匹配操作" }} columns={[
      { title: "时间", key: "time", width: 140, render: (_, entry) => <ListTime value={entry.created_at} /> },
      { title: "操作者", key: "actor", width: 130, render: (_, entry) => entry.actor_name ?? "旧记录" },
      { title: "操作", dataIndex: "action", key: "action" },
      { title: "对象", key: "object", render: (_, entry) => `${entry.object_type}${entry.object_id !== null ? ` #${entry.object_id}` : ""}` },
      { title: "结果", key: "outcome", width: 100, render: (_, entry) => entry.outcome === "success" ? "成功" : entry.outcome },
    ]} />
    <Pagination label="审计日志分页" total={query.error ? undefined : query.data?.total} page={page} pageSize={pageSize} disabled={query.isFetching || !!query.error} onPage={(value) => update("page", String(value))} onPageSize={(value) => update("page_size", String(value))} />
  </section>;
}
