/** @description 项目反馈概况与首页共用有效发现集合和 UTC 窗口，不混入历史开放问题。 */
import { Link, useSearchParams } from "react-router-dom";

import type { ReviewQuality } from "../../api/effectiveness";
import { ListTable } from "../../ui/ListTable";

import { qualitySampleHref } from "./qualityView";

/** 项目按本期未评价发现排序，所有入口沿用明确窗口。 */
export function ProjectSummary({ quality }: {
  /** 缺失时不把旧问题数替代成反馈数。 */ quality?: ReviewQuality;
}) {
  const [params] = useSearchParams();
  const rows = [...(quality?.projects ?? [])].sort((a, b) => b.unmarked - a.unmarked || a.name.localeCompare(b.name) || a.id - b.id);
  return <section className="overview-panel overview-projects" aria-label="项目概况">
    <div className="section-head"><h2>项目概况</h2><span>按本期待反馈发现排序 · {rows.length} 个项目</span></div>
    {!quality ? <p>反馈聚合待升级</p> : <ListTable rowKey="id" pagination={rows.length > 5 ? { pageSize: 5, showSizeChanger: false } : false} scroll={{ x: 640 }} dataSource={rows} locale={{ emptyText: "本期暂无有效发现" }} columns={[
      { title: "项目", key: "name", render: (_, row) => <Link to={qualitySampleHref(params, quality, { repositoryId: row.id })}>{row.name}</Link> },
      { title: "本期发现", dataIndex: "total" },
      { title: "待反馈发现", key: "pending", render: (_, row) => <Link to={qualitySampleHref(params, quality, { repositoryId: row.id, handling: "pending" })}>{row.unmarked}</Link> },
      { title: "已处理", key: "handled", render: (_, row) => row.total - row.unmarked },
      { title: "有帮助", dataIndex: "helpful" }, { title: "误报", dataIndex: "false_positive" }, { title: "忽略", dataIndex: "ignored" },
    ]} />}
  </section>;
}
