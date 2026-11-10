/** @description 管理员运行工作台；URL 定位四个视图，保留已访问表单，仅激活当前视图查询。 */
import { useIsFetching, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Tabs } from "antd";
import { RefreshCw } from "lucide-react";
import { lazy, Suspense } from "react";
import { useSearchParams } from "react-router-dom";

import { apiRequest } from "../api/client";
import { PageHeader } from "../ui/PageHeader";
import { RouteButton } from "../ui/RouteButton";
import { QueryState } from "../ui/QueryState";
import { OperationsRuntime } from "./operations/OperationsRuntime";
import type { OperationsSnapshot } from "./operations/types";

// 表格和维护弹窗按分区加载，默认运行页不提前下载次要区域的实现。
const AlertsPanel = lazy(() => import("./AlertsPanel").then((module) => ({ default: module.AlertsPanel })));
const ReviewPerformance = lazy(() => import("./ReviewPerformance").then((module) => ({ default: module.ReviewPerformance })));
const OperationsMaintenance = lazy(() => import("./operations/OperationsMaintenance").then((module) => ({ default: module.OperationsMaintenance })));

const views = ["runtime", "performance", "alerts", "maintenance"] as const;
type View = typeof views[number];
const queryKeys: Record<View, string[]> = {
  runtime: ["operations", "worker-scheduler-config"], performance: ["operations"],
  alerts: ["alerts", "notification-targets"],
  maintenance: ["operations", "maintenance-preview", "service-addresses", "deployment-summary", "reconciliation", "audit-logs"],
};

/** 保留同页草稿和浏览器历史，不将保存配置等同 Worker 应用或评审成功。 */
export function OperationsPage({ token }: { /** 内存管理会话，服务端仍负责授权。 */ token: string }) {
  const [params, setParams] = useSearchParams();
  const requested = params.get("tab");
  const active: View = views.find((view) => view === requested) ?? "runtime";
  const client = useQueryClient();
  const currentQueries = (key: readonly unknown[]) => queryKeys[active].includes(String(key[0]));
  const fetching = useIsFetching({ predicate: (query) => currentQueries(query.queryKey) }) > 0;
  // 隐藏视图不轮询；已访问面板由 Tabs 保留，不能用卸载表单来节省查询。
  const metrics = useQuery({ queryKey: ["operations"], enabled: active !== "alerts",
    queryFn: ({ signal }) => apiRequest<OperationsSnapshot>(token, "/api/operations", { signal }), refetchInterval: active === "alerts" ? false : 30000 });
  const received = Math.max(0, ...client.getQueryCache().findAll({ predicate: (query) => currentQueries(query.queryKey) }).map((query) => query.state.dataUpdatedAt));
  const state = <QueryState loading={metrics.isLoading} error={metrics.error} onRetry={() => void metrics.refetch()} />;
  return <div className="page operations-page">
    <PageHeader title="运行监控" subtitle="实时运行优先 · 历史性能、告警和维护各自归位" actions={
      <Button icon={<RefreshCw size={16} />} loading={fetching} onClick={() => void client.refetchQueries({ type: "active", predicate: (query) => currentQueries(query.queryKey) })}>刷新当前视图</Button>
    } />
    <div className="row-actions"><RouteButton to="/config-history">配置历史</RouteButton><RouteButton to="/improvements">平台改进记录</RouteButton></div>
    <p className="operations-received" aria-live="polite">{fetching ? "当前视图更新中；保留上次数据与未保存输入" : received ? `本机最近接收：${new Date(received).toLocaleTimeString("zh-CN")}（不代表业务发生时间）` : "当前视图尚未成功接收数据"}</p>
    <Tabs size="small" tabBarGutter={12} activeKey={active} destroyOnHidden={false} onChange={(key) => { const next = new URLSearchParams(params); next.set("tab", key); setParams(next); }} items={[
      { key: "runtime", label: "运行与并发", children: <>{state}<OperationsRuntime data={metrics.data} token={token} active={active === "runtime"} /></> },
      { key: "performance", label: "性能分析", children: <>{state}{metrics.data && <Suspense fallback={<QueryState loading error={null} />}><ReviewPerformance groups={metrics.data.performance_7d} /></Suspense>}</> },
      { key: "alerts", label: "告警与通知", children: <Suspense fallback={<QueryState loading error={null} />}><AlertsPanel token={token} active={active === "alerts"} /></Suspense> },
      { key: "maintenance", label: "维护与审计", children: <>{state}<Suspense fallback={<QueryState loading error={null} />}><OperationsMaintenance token={token} data={metrics.data} active={active === "maintenance"} /></Suspense></> },
    ]} />
  </div>;
}
