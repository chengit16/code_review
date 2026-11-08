/** @description 最近八个任务保留状态、问题处置、耗时尝试与创建事实；不推算全局数量。 */
import { Link } from "react-router-dom";

import type { ReviewJob } from "../../api/types";
import { ListTime } from "../../ui/ListControls";
import { ListTable } from "../../ui/ListTable";
import { Status } from "../../ui/Status";
import { shortSha } from "../../ui/format";
import { JobTimeFacts } from "../JobExecution";
import { IssueSummary } from "../jobs/TaskIssueSummary";

/** 复用任务主列表事实组件，手机也保留所有核心字段。 */
export function RecentReviews({ jobs }: { /** 服务端最近任务投影。 */ jobs: ReviewJob[] }) {
  return <section className="section" aria-labelledby="recent-reviews-title"><div className="section-head"><h2 id="recent-reviews-title">最近评审</h2><Link to="/jobs">查看全部</Link></div>
    <ListTable rowKey="id" dataSource={jobs} pagination={false} scroll={{ x: 1050 }} locale={{ emptyText: "暂无任务，请联系管理员核对项目接入" }} columns={[
      { title: "任务 / 来源", key: "source", width: 230, render: (_, job) => <><Link className="list-primary" to={`/jobs/${job.id}`}>#{job.id} · {job.repository_name}</Link><span className="list-secondary">{job.mr_iid > 0 ? `MR !${job.mr_iid}` : "默认分支 Push"} · {shortSha(job.commit_sha)}</span></> },
      { title: "执行状态", key: "status", width: 110, render: (_, job) => <Status value={job.list_status ?? job.effective_status ?? job.status} /> },
      { title: "问题处置", key: "issues", render: (_, job) => <IssueSummary job={job} detailPath={(id) => `/jobs/${id}`} /> },
      { title: "耗时 / 尝试", key: "duration", width: 185, render: (_, job) => <JobTimeFacts job={job} compact /> },
      { title: "创建时间", key: "time", width: 140, render: (_, job) => <ListTime value={job.created_at} /> },
      { title: "操作", key: "action", width: 75, render: (_, job) => <Link to={`/jobs/${job.id}`} aria-label={`查看任务 ${job.id}`}>详情</Link> },
    ]} /><p className="form-note">仅展示最近 8 个任务，不代表全部任务、当前队列或全量待处置问题。</p>
  </section>;
}
