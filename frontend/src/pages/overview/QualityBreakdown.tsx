/** @description 同分母项目与类别处置分析；只呈现证据和样本入口，不自动评判模型好坏。 */
import { Segmented } from "antd";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import type { ReviewQuality } from "../../api/effectiveness";
import { ListTable } from "../../ui/ListTable";
import { formatCategory } from "../../ui/format";

import { qualityRatio, qualitySampleHref } from "./qualityView";

/** 先按误报条数排序，低反馈样本不按比例排名。 */
export function QualityBreakdown({ quality }: {
  /** 缺失表示旧服务，不能伪造空样本。 */ quality?: ReviewQuality;
}) {
  const [mode, setMode] = useState("category");
  const [params] = useSearchParams();
  const rows = quality ? (mode === "category" ? (quality.categories).map((row) => ({ ...row, id: undefined })) : quality.projects)
    .map((row) => ({ ...row, key: row.id ?? row.name })) : [];
  return <section className="overview-panel quality-breakdown" aria-label="优化方向">
    <div className="section-head"><h2>优化方向</h2><Segmented aria-label="质量分析维度" value={mode} onChange={setMode} options={[{ value: "category", label: "按类别" }, { value: "project", label: "按项目" }]} /></div>
    <p className="quality-caption">按误报条数排序，不按小样本比例评优劣。忽略与未评价不参与误报比例分母；旧版修复标记按未评价处理。</p>
    {!quality ? <p>当前服务暂不提供质量分组，请升级 API。</p> : <ListTable rowKey="key" dataSource={rows} pagination={{ pageSize: 5, hideOnSinglePage: true, showSizeChanger: false }} scroll={{ x: 800 }} locale={{ emptyText: "本期暂无有效发现样本" }} columns={[
      { title: mode === "category" ? "类别" : "项目", key: "name", width: 160, render: (_, row) => mode === "category" ? formatCategory(row.name) : row.name },
      { title: "样本", key: "action", render: (_, row) => <Link to={qualitySampleHref(params, quality, { category: mode === "category" ? row.name : undefined, repositoryId: row.id })}>查看样本</Link> },
      { title: "发现", dataIndex: "total", key: "total" },
      { title: "有帮助", dataIndex: "helpful", key: "helpful" },
      { title: "误报", dataIndex: "false_positive", key: "false_positive" },
      { title: "忽略", dataIndex: "ignored", key: "ignored" },
      { title: "未评价", dataIndex: "unmarked", key: "unmarked" },
      { title: "误报占比", key: "rate", render: (_, row) => qualityRatio(row.false_positive, row.helpful + row.false_positive, 5) },
    ]} />}
  </section>;
}
