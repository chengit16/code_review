/** @description 运行视图突出初审队列、模型槽和并发，分离历史结论与运维风险；不推测告警语义。 */
import { Alert, Card, Collapse } from "antd";
import { Link } from "react-router-dom";

import { formatTime } from "../../ui/format";
import { WorkerConcurrency } from "../WorkerConcurrency";
import { WorkerExecution } from "../WorkerExecution";
import type { OperationsSnapshot } from "./types";

/** 使用服务端执行状态而非有效结论统计，缺失或查询失败不展示假零。 */
export function OperationsRuntime({ data, token, active }: {
  /** 上次成功快照，读取失败可保留旧数据。 */ data?: OperationsSnapshot;
  /** 内存管理凭据。 */ token: string;
  /** 当前视图可见时才轮询并发配置。 */ active: boolean;
}) {
  const attention = data ? (data.jobs.failed ?? 0) + (data.jobs.partial ?? 0) : undefined;
  const infrastructure = data ? [
    ...(data.disk_free_bytes < 2 * 1024 ** 3 ? ["可用磁盘空间少于 2 GB"] : []),
    ...(!data.backup.healthy || data.backup.age_seconds == null || data.backup.age_seconds > 48 * 3600 ? ["最近备份缺失、副本检查未通过或超过 48 小时；请到维护与审计核对"] : []),
  ] : [];
  return <>
    <div className="operations-summary" aria-label="运行指标">
      {[
        ["初审排队", data?.execution_jobs ? data.execution_jobs.queued ?? 0 : "未知", `最早待处理 ${formatTime(data?.oldest_pending_at ?? null)}`],
        ["初审运行", data?.execution_jobs ? data.execution_jobs.running ?? 0 : "未知", "原始执行状态，不含补审与合并前审查"],
        ["模型执行 / 已应用上限", `${data?.scheduler?.running_model_tasks ?? "未知"} / ${data?.scheduler?.applied_concurrency ?? "未知"}`, "模型诊断、初审及补审共用容量"],
        ["待关注评审", attention ?? "未知", "全历史当前有效结论：失败与部分覆盖"],
      ].map(([title, value, note]) => <Card key={String(title)} size="small"><span className="operations-caption">{title}</span><strong className="operations-number">{value}</strong><small>{note}</small></Card>)}
    </div>
    {data && <div className="operations-attention">
      <Alert type="info" showIcon title={`历史评审待关注 ${attention} 项 · 初审通知失败 ${data.deliveries.failed ?? 0} 项`} description={<>
        这些记录不代表系统当前宕机；补审排队/运行 {data.recovery_jobs ? (data.recovery_jobs.queued ?? 0) + (data.recovery_jobs.running ?? 0) : "未知"}，补充通知失败 {data.recovery_deliveries ? data.recovery_deliveries.failed ?? 0 : "未知"}。<Link to="/jobs?view=attention">查看待关注任务</Link> · <Link to="/jobs?view=notification_failed">查看初审通知失败</Link>
      </>} />
      {infrastructure.length > 0 && <Alert type="warning" showIcon title="运维风险待核对" description={<>{infrastructure.join("；")}。<Link to="/operations?tab=maintenance">进入维护与审计</Link></>} />}
    </div>}
    <div className="operations-runtime-grid">
      <div className="operations-slots"><WorkerExecution snapshot={data?.scheduler} /></div>
      <Card title="模型任务并发设置" className="operations-capacity"><WorkerConcurrency token={token} active={active} execution={data?.scheduler} /></Card>
    </div>
    {data && <Collapse className="operations-extra" items={[{ key: "summary", label: `服务端完整摘要（含历史问题）· ${data.alerts.length} 项`, children: <>
      <p>原文保留供核对，不从告警文本推测系统故障或自动执行恢复。初审历史整批重试 {data.retry_count} 次。</p>
      {data.alerts.length ? <ul>{data.alerts.map((alert, index) => <li key={`${index}-${alert}`}>{alert}</li>)}</ul> : <p>当前没有达到服务端告警阈值的项目。</p>}
      <Link to="/operations?tab=alerts">配置主动告警与查看通知</Link>
    </> }]} />}
  </>;
}
