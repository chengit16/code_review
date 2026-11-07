/** @description 七天固定分组表格与本地筛选；不合成总体分位数，不将缺失用量当零费用。 */
import { Collapse, Select, Table } from "antd";
import type { TableColumnsType } from "antd";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import type { PerformanceGroup } from "../api/reviewExecution";
import { Status } from "../ui/Status";
import { secondsText } from "./JobExecution";

function quantiles(p50: number | null, p95: number | null, samples: number) {
  return <>{samples ? `${secondsText(p50)} / ${secondsText(p95)}` : "无有效样本"}<small className="operations-table-note">{samples} 个样本</small></>;
}

const columns: TableColumnsType<PerformanceGroup> = [
  { title: "项目", dataIndex: "repository_id", render: (id: number) => `项目 #${id}` },
  { title: "有效结论", dataIndex: "status", render: (status: string) => <Status value={status} /> },
  { title: "原始规模", dataIndex: "size_bucket", render: (bucket: string) => bucket === "unknown" ? "规模未知" : `${bucket} 文件` },
  { title: "任务", dataIndex: "count" },
  { title: "成功执行 P50 / P95", render: (_, group) => quantiles(group.execution_p50_seconds, group.execution_p95_seconds, group.execution_samples) },
  { title: "首次排队 P50 / P95", render: (_, group) => quantiles(group.queue_p50_seconds, group.queue_p95_seconds, group.queue_samples) },
];

/** 筛选只作用于服务端已有聚合，展开次要统计并始终保留有效样本数。 */
export function ReviewPerformance({ groups = [] }: { /** 近七天按项目、有效结论和原始 Git 文件数分组。 */ groups?: PerformanceGroup[] }) {
  const [params, setParams] = useSearchParams();
  const repository = params.get("performance_repository") ?? undefined;
  const status = params.get("performance_status") ?? undefined;
  const size = params.get("performance_size") ?? undefined;
  const [page, setPage] = useState(1);
  const setFilter = (key: string, value: string | undefined) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    setParams(next); setPage(1);
  };
  const filtered = groups.filter((group) => (!repository || String(group.repository_id) === repository) && (!status || group.status === status) && (!size || group.size_bucket === size));
  return <section className="operations-performance">
    <h2>近 7 天评审耗时与输入规模</h2>
    <p className="operations-caption">固定近七天 · 按当前有效结论分组 · 原始 Git 文件规模 · 展开查看超时、重试与用量</p>
    <div className="operations-performance-filters">
      <Select aria-label="性能项目筛选" placeholder="全部项目" allowClear value={repository} options={[...new Set(groups.map((group) => group.repository_id))].sort((a, b) => a - b).map((id) => ({ value: String(id), label: `项目 #${id}` }))} onChange={(value) => setFilter("performance_repository", value)} />
      <Select aria-label="性能状态筛选" placeholder="全部结论" allowClear value={status} options={[...new Set(groups.map((group) => group.status))].map((value) => ({ value, label: <Status value={value} /> }))} onChange={(value) => setFilter("performance_status", value)} />
      <Select aria-label="性能规模筛选" placeholder="全部规模" allowClear value={size} options={[...new Set(groups.map((group) => group.size_bucket))].map((value) => ({ value, label: value === "unknown" ? "规模未知" : `${value} 文件` }))} onChange={(value) => setFilter("performance_size", value)} />
    </div>
    <Table<PerformanceGroup> rowKey={(group) => `${group.repository_id}-${group.status}-${group.size_bucket}`} columns={columns} dataSource={filtered} size="small" scroll={{ x: 800 }}
      locale={{ emptyText: groups.length ? "没有符合筛选的分组" : "近七天暂无分组样本" }}
      pagination={{ current: Math.min(page, Math.max(1, Math.ceil(filtered.length / 10))), pageSize: 10, showSizeChanger: false, onChange: setPage, showTotal: (total) => `${total} 个分组` }}
      expandable={{ expandedRowRender: (group) => <div className="operations-performance-detail">
        <span>超时 {group.timeout_count} / {group.count}（{(group.timeout_rate * 100).toFixed(1)}%）</span>
        <span>整批重试 {group.retry_count} 次</span><span>已知 Token 下限 {group.known_tokens.toLocaleString("zh-CN")}</span>
        <span>未知用量任务 {group.unknown_usage_count} 个；缺失不代表无费用</span>
      </div> }} />
    <Collapse items={[{ key: "method", label: "统计说明与历史缺失边界", children: <>
      <p>执行分位数仅统计完整时间记录的初审成功任务，不含补审、跳过。首次排队单独统计；零样本显示无有效样本，有样本但缺失时间显示未知。分位数采用最近秩法，小样本不代表稳定 P95。</p>
      <p>不对各分组 P50/P95 求平均，不支持任意日期或按天趋势。原始 Git 文件数不是 OCR 选中文件数；已知 Token 仅为下限，不能跨币种合并费用。</p>
    </> }]} />
  </section>;
}
