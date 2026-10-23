/** @description 管理写操作审计记录；只展示服务端脱敏字段，不记录请求体或凭据。 */

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { apiRequest } from "../api/client";
import type { AuditPage } from "../api/types";
import { Pagination } from "../ui/Pagination";
import { QueryState } from "../ui/QueryState";
import { formatTime } from "../ui/format";

/** 最近审计记录分页展示；只读账号可查看，修改权限仍由 API 控制。 */
export function AuditLogPanel({ token }: { /** 内存中的管理口令或会话。 */ token: string }) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const query = useQuery({
    queryKey: ["audit-logs", page, pageSize],
    queryFn: ({ signal }) => apiRequest<AuditPage>(token, `/api/audit-logs?page=${page}&page_size=${pageSize}`, { signal }),
    refetchInterval: 10000,
  });
  const data = query.data;
  return <section className="section"><div className="section-head"><h2>管理操作审计</h2><span>{data?.total ?? 0} 条</span></div>
    <p className="form-note">记录操作者、操作对象、结果与时间；不保存请求内容、密码或密钥。</p>
    <QueryState loading={query.isLoading} error={query.error} onRetry={() => void query.refetch()} />
    {data && <><div className="table-scroll responsive-table"><table><thead><tr><th>时间</th><th>操作者</th><th>操作</th><th>对象</th><th>结果</th></tr></thead><tbody>
      {data.items.map((entry) => <tr key={entry.id}><td data-label="时间">{formatTime(entry.created_at)}</td><td data-label="操作者">{entry.actor_name ?? "旧记录"}</td><td data-label="操作" className="mono">{entry.action}</td><td data-label="对象">{entry.object_type}{entry.object_id !== null ? ` #${entry.object_id}` : ""}</td><td data-label="结果">{entry.outcome === "success" ? "成功" : entry.outcome}</td></tr>)}
      {data.items.length === 0 && <tr><td colSpan={5} className="empty-row">暂无管理操作</td></tr>}
    </tbody></table></div>
      <Pagination label="审计日志分页" total={data.total} page={page} pageSize={pageSize} disabled={query.isFetching}
        onPage={setPage} onPageSize={(size) => { setPageSize(size); setPage(1); }} />
    </>}
  </section>;
}
