/** @description 概览只读编排；健康与运行数据独立容错，不执行恢复或问题处置。 */
import { useQuery } from "@tanstack/react-query";
import { Button, Segmented } from "antd";
import { RefreshCw } from "lucide-react";
import { useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { apiRequest } from "../api/client";
import { getEffectiveness } from "../api/effectiveness";
import { getOverview } from "../api/overview";
import type { Health, Repository } from "../api/types";
import { ListSelect } from "../ui/ListControls";
import { PageHeader } from "../ui/PageHeader";
import { QueryState } from "../ui/QueryState";
import { Status } from "../ui/Status";

import { ReviewEffectivenessSection } from "./ReviewEffectivenessSection";
import { ReadStatus } from "./overview/ReadStatus";
import { QualitySamples } from "./overview/QualitySamples";
import { RuntimeSummary } from "./overview/RuntimeSummary";

/** 手动刷新聚合实际结果；后台轮询不反复播报或移动焦点。 */
export function OverviewPage({ token, canEdit = false }: {
  /** 内存会话。 */ token: string;
  /** 只控制管理导航，服务端仍负责授权。 */ canEdit?: boolean;
}) {
  const [params, setParams] = useSearchParams();
  const repositoryId = params.get("repository_id") ?? "";
  const days = [7, 30, 90].includes(Number(params.get("days"))) ? Number(params.get("days")) : 30;
  const query = new URLSearchParams({ days: String(days) });
  if (repositoryId) query.set("repository_id", repositoryId);
  // 项目与时间进入查询键，切换时不把旧范围的数据冒充新范围。
  const metrics = useQuery({ queryKey: ["review-effectiveness", query.toString()],
    queryFn: ({ signal }) => getEffectiveness(token, query.toString(), signal), refetchInterval: 30000 });
  const repositories = useQuery({ queryKey: ["repositories"],
    queryFn: ({ signal }) => apiRequest<Repository[]>(token, "/api/repositories", { signal }) });
  function updateFilter(key: string, value: string) {
    const next = new URLSearchParams(params);
    for (const name of [...next.keys()]) if (name.startsWith("sample_")) next.delete(name);
    if (value) next.set(key, value); else next.delete(key);
    setParams(next);
  }
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
        metrics.refetch({ cancelRefetch: false, throwOnError: true }),
      ]);
      setMessage(results.some((result) => result.status === "rejected") ? "部分读取失败，请查看各区提示；已成功的数据仍保留。" : "概览读取完成");
    } finally {
      refreshLock.current = false;
      setRefreshing(false);
    }
  }
  const confirmedWorker = !health.isError && health.data?.worker;
  const data = overview.data;
  return <div className="page overview-page"><PageHeader title="项目总览" subtitle="评审价值、反馈质量与当前风险" actions={
    <div className="overview-header-actions"><Segmented aria-label="统计时间" value={String(days)} disabled={refreshing} onChange={(value) => updateFilter("days", String(value))} options={[{ value: "7", label: "近 7 天" }, { value: "30", label: "近 30 天" }, { value: "90", label: "近 90 天" }]} />
      <Button icon={<RefreshCw size={16} />} loading={refreshing} disabled={refreshing} onClick={() => void handleRefresh()}>刷新概览</Button>
    </div>
  } />
    {canEdit && repositories.isSuccess && repositories.data.length === 0 && <p className="coverage-note">先接入第一个项目，再查看评审与反馈。<Link to="/onboarding">开始项目接入</Link></p>}
    <section className="overview-toolbar" aria-label="总览筛选">
      <ListSelect label="项目" value={repositoryId || "all"} disabled={refreshing} onValueChange={(value) => updateFilter("repository_id", value === "all" ? "" : value)} options={[{ value: "all", label: "全部项目" }, ...(repositories.data ?? []).map((item) => ({ value: String(item.id), label: item.name }))]} />
      <ReadStatus label="项目统计" updatedAt={metrics.dataUpdatedAt} fetching={metrics.isFetching} />
      <Link className="overview-tasks-link" to={repositoryId ? `/jobs?repository_id=${encodeURIComponent(repositoryId)}` : "/jobs"}>查看评审任务</Link>
    </section>
    <p className="overview-manual-result" role="status">{message}</p>
    {health.isError ? <div className="overview-notice" role="alert">暂时无法确认 Worker 当前状态；{health.data ? <>上次检测：{health.data.worker === "running" ? "运行中" : "未运行"}。<ReadStatus label="健康" updatedAt={health.dataUpdatedAt} fetching={health.isFetching} /></> : "尚无成功检测记录。"}<Button onClick={() => void health.refetch()}>重新检测</Button></div> : confirmedWorker === "stopped" && <div className="overview-notice">Worker 未运行，队列可能等待处理。{canEdit ? <Link to="/operations?tab=runtime">查看运行监控</Link> : "请联系管理员核对启动指引。"}不要反复重新评审。</div>}
    {overview.isError && data && <p role="alert">运行数据刷新失败，当前显示上次成功读取的数据。<Button onClick={() => void overview.refetch()}>重新读取</Button></p>}
    <QueryState loading={overview.isLoading} error={!data ? overview.error : null} onRetry={() => void overview.refetch()} />
    <RuntimeSummary data={data} workerStatus={<><span>全平台 Worker {health.isLoading ? "正在检测" : <Status value={confirmedWorker || "unknown"} />}</span>
      <ReadStatus label="健康" updatedAt={health.dataUpdatedAt} fetching={health.isFetching} /></>} readStatus={<ReadStatus label="运行数据" updatedAt={overview.dataUpdatedAt} fetching={overview.isFetching} />} />
    {repositories.isError && <p role="alert">项目选项读取失败，当前 URL 范围仍保留。<Button onClick={() => void repositories.refetch()}>重读项目选项</Button></p>}
    <QueryState loading={metrics.isLoading} error={!metrics.data ? metrics.error : null} onRetry={() => void metrics.refetch()} />
    {metrics.isError && metrics.data && <p role="alert">项目统计刷新失败，当前显示上次成功读取的数据。<Button onClick={() => void metrics.refetch()}>重新读取统计</Button></p>}
    {metrics.data && <ReviewEffectivenessSection data={metrics.data} days={days} repositoryId={repositoryId} />}
    {params.get("sample_open") === "1" && <QualitySamples token={token} days={days} repositoryId={repositoryId} />}
  </div>;
}
