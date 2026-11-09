/** @description 项目风险排序表；复用统一列表，旧服务缺少新增指标时显示未知。 */
import { Link } from "react-router-dom";

import type { EffectivenessSnapshot } from "../../api/effectiveness";
import { ListTable } from "../../ui/ListTable";

/** 所有项目在同一表内分页，按当前待处置降序，不重复渲染排名与明细。 */
export function ProjectSummary({ projects }: {
  /** 当前项目范围及时间窗口的聚合。 */ projects: EffectivenessSnapshot["projects"];
}) {
  const rows = [...projects].sort((a, b) => b.open_issues - a.open_issues || a.name.localeCompare(b.name) || a.id - b.id);
  return <section className="overview-panel overview-projects" aria-label="项目概况">
    <div className="section-head"><h2>项目概况</h2><span>按当前待处置排序 · {rows.length} 个项目</span></div>
    <ListTable rowKey="id" pagination={rows.length > 5 ? { pageSize: 5, showSizeChanger: false, hideOnSinglePage: true } : false} scroll={{ x: 640 }} dataSource={rows} locale={{ emptyText: "暂无项目" }} columns={[
      { title: "项目", key: "name", width: 160, render: (_, item) => <Link to={`/issues?repository_id=${item.id}&status=open`}>{item.name}</Link> },
      { title: "本期评审", key: "reviews", render: (_, item) => item.reviews ?? "—" },
      { title: "本期新问题", dataIndex: "new_issues", key: "new" },
      { title: "当前待处置", dataIndex: "open_issues", key: "open" },
      { title: "严重 / 高危", key: "risk", render: (_, item) => item.critical_issues === undefined || item.high_issues === undefined ? "—" : `${item.critical_issues} / ${item.high_issues}` },
      { title: "本期人工标记修复", dataIndex: "fixed_issues", key: "fixed" },
    ]} />
  </section>;
}
