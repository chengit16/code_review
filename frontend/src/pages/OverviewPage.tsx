/** @description 概览只读编排；健康与运行数据独立容错，不执行恢复或问题处置。 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "antd";
import { RefreshCw } from "lucide-react";
import { useRef, useState } from "react";
import { Link } from "react-router-dom";

import { apiRequest } from "../api/client";
import { getOverview } from "../api/overview";
import type { Health } from "../api/types";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { Status } from "../ui/Status";

import { ReviewEffectivenessSection } from "./ReviewEffectivenessSection";
import { CurrentWork } from "./overview/CurrentWork";
import { ReadStatus } from "./overview/ReadStatus";
import { RecentReviews } from "./overview/RecentReviews";

/** 手动刷新聚合实际结果；后台轮询不反复播报或移动焦点。 */
export function OverviewPage({ token, canEdit = false }: {
  /** 内存会话。 */ token: string;
  /** 只控制管理导航，服务端仍负责授权。 */ canEdit?: boolean;
}) {
  const client = useQueryClient();
  const [refreshing, setRefreshing] = useState(false);
  const [message, setMessage] = useState("");
  const refreshLock = useRef(false);
  const health = useQuery({ queryKey: ["health"], queryFn: ({ signal }) => apiRequest<Health>(token, "/api/health", { signal }), refetchInterval: 10000 });
  const overview = useQuery({ queryKey: ["overview"], queryFn: ({ signal }) => getOverview(token, signal),
    refetchInterval: (query) => (query.state.data?.activity?.total ?? (query.state.data?.summary.running ?? 0) + (query.state.data?.summary.queued ?? 0)) > 0 ? 5000 : 30000 });
  async function handleRefresh() {
    if (refreshLock.current) return;
    refreshLock.current = true;
    setRefreshing(true);
    setMessage("");
    // 每份结果分别判断，失败保留缓存；不能用最新成功资源掩盖其他失败。
    try {
      const results = await Promise.allSettled([
        health.refetch({ cancelRefetch: false, throwOnError: true }),
        overview.refetch({ cancelRefetch: false, throwOnError: true }),
        client.refetchQueries({ queryKey: ["review-effectiveness"], type: "active" }, { cancelRefetch: false, throwOnError: true }),
      ]);
      setMessage(results.some((result) => result.status === "rejected") ? "部分读取失败，请查看各区提示；已成功的数据仍保留。" : "概览读取完成");
    } finally {
      refreshLock.current = false;
      setRefreshing(false);
    }
  }
  const confirmedWorker = !health.isError && health.data?.worker;
  const data = overview.data;
  return <div className="page overview-page"><PageHeader title="运行概览" subtitle="先看运行异常与代码问题，再查看最近评审" actions={
    <div className="overview-header-actions"><span>Worker {health.isLoading ? "正在检测" : <Status value={confirmedWorker || "unknown"} />}</span>
      <ReadStatus label="健康" updatedAt={health.dataUpdatedAt} fetching={health.isFetching} />
      <Button icon={<RefreshCw size={16} />} loading={refreshing} disabled={refreshing} onClick={() => void handleRefresh()}>刷新概览</Button>
    </div>
  } />
    <p className="overview-manual-result" role="status">{message}</p>
    {health.isError ? <div className="overview-notice" role="alert">暂时无法确认 Worker 当前状态；{health.data ? <>上次检测：{health.data.worker === "running" ? "运行中" : "未运行"}。<ReadStatus label="健康" updatedAt={health.dataUpdatedAt} fetching={health.isFetching} /></> : "尚无成功检测记录。"}<Button onClick={() => void health.refetch()}>重新检测</Button></div> : confirmedWorker === "stopped" && <div className="overview-notice">Worker 未运行，队列可能等待处理。{canEdit ? <Link to="/operations?tab=runtime">查看运行监控</Link> : "请联系管理员核对启动指引。"}不要反复重新评审。</div>}
    <ReadStatus label="运行数据" updatedAt={overview.dataUpdatedAt} fetching={overview.isFetching} />
    {overview.isError && data && <p role="alert">运行数据刷新失败，当前显示上次成功读取的数据。<Button onClick={() => void overview.refetch()}>重新读取</Button></p>}
    <QueryState loading={overview.isLoading} error={!data ? overview.error : null} onRetry={() => void overview.refetch()} />
    {data && <><CurrentWork data={data} /><RecentReviews jobs={data.recent} />
      <section className="overview-facts" aria-label="运行概况">
        {canEdit ? <Link to="/repositories">已配置项目 {data.summary.repositories}</Link> : <span>已配置项目 {data.summary.repositories}</span>}
        <Link to="/jobs?view=active">{data.activity ? <>活动任务 {data.activity.total}（排队 {data.activity.queued} · 运行 {data.activity.running}）</> : "活动任务汇总暂不可用"}</Link>
        <Link to="/jobs?status=complete">已完成 {data.summary.complete} / 全部历史 {data.summary.total} 个任务</Link>
        <span>历史失败 {data.summary.historical_failed} 个任务（含已恢复记录），不等于当前运行异常</span>
      </section>
    </>}
    <ReviewEffectivenessSection token={token} />
  </div>;
}
