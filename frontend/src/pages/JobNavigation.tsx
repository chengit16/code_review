/** @description 任务详情的连续导航，沿用列表筛选并处理首尾、加载与失败，不执行写操作。 */

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ChevronLeft, ChevronRight, RefreshCw } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import { getTaskNeighbors } from "../api/tasks";

/** 按服务端降序列表切换任务，只读用户也可使用；返回列表保留来源页码。 */
export function JobNavigation({ token, id, back }: {
  /** 仅随同源请求发送的内存口令。 */ token: string;
  /** 当前任务编号，查询键随任务切换隔离旧响应。 */ id: number;
  /** 列表来源地址，包含生效的筛选与分页；直接访问时为 /jobs。 */ back: string;
}) {
  const navigate = useNavigate();
  const search = back.startsWith("/jobs?") ? back.slice(5) : "";
  const query = useQuery({
    queryKey: ["job-neighbors", id, search],
    queryFn: ({ signal }) => getTaskNeighbors(token, id, new URLSearchParams(search), signal),
    // Worker 会改变筛选命中，定时刷新邻项；失败时不沿用上次的导航目标。
    refetchInterval: 5000,
    enabled: Number.isSafeInteger(id) && id > 0,
  });
  function handleNavigate(nextId: number | null | undefined) {
    if (nextId != null) navigate(`/jobs/${nextId}${search}`, { state: { back } });
  }

  return <div className="job-navigation">
    <div className="job-navigation-row">
      <Link className="back-link" to={back}><ArrowLeft size={16} aria-hidden="true" />返回任务列表</Link>
      <nav className="job-navigation-actions" aria-label="相邻任务" aria-busy={query.isLoading}>
        <button type="button" className="button button-secondary" title={query.isLoading ? "正在查找上一条" : query.data?.previous_id == null ? "已到第一条" : `上一条：任务 #${query.data.previous_id}`} disabled={query.isLoading || query.isError || query.data?.previous_id == null} onClick={() => handleNavigate(query.data?.previous_id)}><ChevronLeft size={16} aria-hidden="true" />上一条</button>
        <button type="button" className="button button-secondary" title={query.isLoading ? "正在查找下一条" : query.data?.next_id == null ? "已到最后一条" : `下一条：任务 #${query.data.next_id}`} disabled={query.isLoading || query.isError || query.data?.next_id == null} onClick={() => handleNavigate(query.data?.next_id)}>下一条<ChevronRight size={16} aria-hidden="true" /></button>
      </nav>
    </div>
    {query.isLoading && <span className="job-navigation-status" role="status">正在查找相邻任务…</span>}
    {query.error && <div className="job-navigation-error" role="alert"><span>相邻任务加载失败：{query.error.message}</span><button type="button" className="icon-button" title="重新加载相邻任务" aria-label="重新加载相邻任务" disabled={query.isFetching} onClick={() => void query.refetch()}><RefreshCw size={16} /></button></div>}
  </div>;
}
