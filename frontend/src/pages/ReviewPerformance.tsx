/** @description 展示近七天分组统计及样本数；不以跳过任务替代正常模型耗时样本。 */
import type { PerformanceGroup } from "../api/reviewExecution";
import { Status } from "../ui/Status";
import { secondsText } from "./JobExecution";

/** 缺失或样本不足时如实展示，不承诺统计值已经稳定。 */
export function ReviewPerformance({ groups = [] }: { /** 服务端按项目、状态、原始规模分组的事实。 */ groups?: PerformanceGroup[] }) {
  return <section className="section"><div className="section-head"><h2>近 7 天评审耗时与输入规模</h2></div><p className="coverage-note">状态按当前有效结论分组；执行分位数仅统计完整时间记录的初审成功任务，不含补审；排队单独统计，跳过不混入正常模型执行。分位数采用最近秩法，小样本不代表稳定 P95。规模为原始 Git 文件数，不是 OCR 选中文件数。</p><div className="performance-groups">{groups.map((group) => <article key={`${group.repository_id}-${group.status}-${group.size_bucket}`} className="attempt-evidence"><h3>项目 #{group.repository_id} · {group.size_bucket === "unknown" ? "规模未知" : `${group.size_bucket} 文件`} <Status value={group.status} /></h3><dl className="execution-grid"><div><dt>任务 / 超时</dt><dd>{group.count} / {group.timeout_count}（本组超时占比 {(group.timeout_rate * 100).toFixed(1)}%）</dd></div><div><dt>成功执行 P50 / P95</dt><dd>{secondsText(group.execution_p50_seconds)} / {secondsText(group.execution_p95_seconds)}（{group.execution_samples} 个样本）</dd></div><div><dt>首次排队 P50 / P95</dt><dd>{secondsText(group.queue_p50_seconds)} / {secondsText(group.queue_p95_seconds)}（{group.queue_samples} 个样本）</dd></div><div><dt>整批重试 / 未知用量任务</dt><dd>{group.retry_count} / {group.unknown_usage_count}</dd></div><div><dt>已知 Token</dt><dd>{group.known_tokens.toLocaleString("zh-CN")}（下限）</dd></div></dl></article>)}{!groups.length && <p className="empty-inline">近七天暂无分组样本</p>}</div></section>;
}
