/** @description 按需加载维护工具；清理确认冻结目标，取消不写入，实际范围由服务端重新核验。 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { App, Button, Card, Collapse, InputNumber } from "antd";
import { useState } from "react";

import { apiRequest } from "../../api/client";
import { QueryState } from "../../ui/QueryState";
import { formatTime } from "../../ui/format";
import { AuditLogPanel } from "../AuditLogPanel";
import { ReconciliationPanel } from "../ReconciliationPanel";
import { ServiceAddresses } from "../ServiceAddresses";
import type { OperationsSnapshot } from "./types";

/** 保留已访问维护工具的状态，隐藏后停用查询和轮询，不自动清理。 */
export function OperationsMaintenance({ token, data, active }: {
  /** 内存管理凭据，API 负责鉴权。 */ token: string;
  /** 只读磁盘、备份与候选事实。 */ data?: OperationsSnapshot;
  /** 维护视图是否可见。 */ active: boolean;
}) {
  const [days, setDays] = useState<number | null>(90);
  const [message, setMessage] = useState("");
  const [expanded, setExpanded] = useState<string[]>([]);
  const { modal } = App.useApp();
  const client = useQueryClient();
  const valid = days !== null && Number.isInteger(days) && days >= 7 && days <= 3650;
  const preview = useQuery({ queryKey: ["maintenance-preview", days], enabled: active && valid,
    queryFn: ({ signal }) => apiRequest<{ count: number; bytes: number }>(token, `/api/maintenance/preview?days=${days}`, { signal }) });
  const prune = useMutation({ retry: false, mutationFn: (retention: number) => apiRequest<{ count: number }>(token, `/api/maintenance/prune?days=${retention}`, { method: "POST" }),
    onSuccess: (result) => { setMessage(`已清理 ${result.count} 个旧工件目录`); void client.invalidateQueries({ queryKey: ["maintenance-preview"] }); void client.invalidateQueries({ queryKey: ["operations"] }); } });
  const orphan = useMutation({ retry: false, mutationFn: () => apiRequest<{ count: number }>(token, "/api/maintenance/orphans/prune", { method: "POST" }),
    onSuccess: (result) => { setMessage(`已清理 ${result.count} 个已删除项目目录`); void client.invalidateQueries({ queryKey: ["operations"] }); } });
  return <div className="operations-maintenance">
    {data && <Card title="存储与备份"><dl className="operation-facts">
      <div><dt>可用空间</dt><dd>{(data.disk_free_bytes / 1024 ** 3).toFixed(1)} GB</dd></div>
      <div><dt>最近成对备份</dt><dd>{formatTime(data.backup.last_at)}</dd></div>
      <div><dt>副本检查</dt><dd>{data.backup.healthy ? "副本检查通过" : "待检查"}{data.backup.age_seconds != null && data.backup.age_seconds > 48 * 3600 ? " · 超过 48 小时" : ""}</dd></div>
    </dl><p className="operations-caption">仅检查 SQLite 副本和配对私有配置存在性，不代表完整恢复演练或全部工件已备份。</p></Card>}
    <Card title="工件清理">
      <div className="operations-cleanup-row"><label htmlFor="artifact-retention">评审工件保留天数</label><InputNumber id="artifact-retention" min={7} max={3650} precision={0} value={days} onChange={setDays} disabled={prune.isPending} />
        <span>{valid ? preview.data ? `${preview.data.count} 个候选目录 · ${(preview.data.bytes / 1024 ** 2).toFixed(1)} MB` : "尚无可用预览" : "请输入 7～3650 的整数"}</span>
        <Button danger disabled={!valid || !preview.data?.count || preview.isFetching || !!preview.error} loading={prune.isPending} onClick={() => {
          if (!valid || days === null || !preview.data) return;
          const retention = days;
          modal.confirm({ title: "确认清理旧评审工件", content: `清理 ${preview.data.count} 个超过 ${retention} 天的终态评审工件？任务和报告摘要保留；服务端会重新核验候选范围。`, okText: "确认清理", cancelText: "取消", okButtonProps: { danger: true }, onOk: () => prune.mutateAsync(retention).then(() => undefined) });
        }}>清理工件</Button>
      </div>
      <div className="operations-cleanup-row"><span>已删除项目待清理：{data?.orphan_artifacts ?? "未知"} 个任务目录</span><Button danger disabled={!data?.orphan_artifacts} loading={orphan.isPending} onClick={() => modal.confirm({ title: "确认清理遗留目录", content: `将永久清理 ${data?.orphan_artifacts} 个已删除项目关联的遗留任务目录；数据库记录不会恢复，正在使用的目录会跳过。`, okText: "确认清理", cancelText: "取消", okButtonProps: { danger: true }, onOk: () => orphan.mutateAsync().then(() => undefined) })}>清理遗留目录</Button></div>
      {message && <p role="status">{message}</p>}<QueryState loading={preview.isFetching} error={preview.error || prune.error || orphan.error} />
    </Card>
    <ServiceAddresses token={token} active={active} />
    <Collapse activeKey={expanded} onChange={(keys) => setExpanded(Array.isArray(keys) ? keys : [keys])} items={[
      { key: "reconciliation", label: "数据对账与诊断包", children: <ReconciliationPanel token={token} active={active && expanded.includes("reconciliation")} /> },
      { key: "audit", label: "管理操作审计", children: <AuditLogPanel token={token} active={active && expanded.includes("audit")} /> },
    ]} />
  </div>;
}
