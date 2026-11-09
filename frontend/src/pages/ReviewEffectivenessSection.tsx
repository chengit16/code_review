/** @description 项目首页的业务数据展示；统计由父页统一筛选和读取，不操作问题状态。 */
import { Collapse } from "antd";
import { Link } from "react-router-dom";

import type { EffectivenessSnapshot } from "../api/effectiveness";

import { ProblemDistributions } from "./overview/ProblemDistributions";
import { ProjectSummary } from "./overview/ProjectSummary";
import { QualityBreakdown } from "./overview/QualityBreakdown";
import { QualityOverview } from "./overview/QualityOverview";

/** 期间流量与当前存量分开标注；人工标记修复不是系统验收结论。 */
export function ReviewEffectivenessSection({ data, days, repositoryId }: {
  /** 同一次业务读取快照。 */ data: EffectivenessSnapshot;
  /** 当前 UTC 统计窗口。 */ days: number;
  /** 空值表示全部项目，导航沿用当前项目范围。 */ repositoryId: string;
}) {
  const summary = data.summary;
  const scope = repositoryId ? `&repository_id=${encodeURIComponent(repositoryId)}` : "";
  return <section className="overview-analytics" aria-label="项目数据">
    <section className="overview-kpis" aria-label="项目核心指标">
      <div><span>本期评审数</span><strong>{summary.reviews}</strong><small>次终态评审 · 近 {days} 天</small></div>
      <div><span>本期新问题</span><strong>{summary.new_issues}</strong><small>按首次发现计数</small></div>
      <div><span>当前待处置</span><Link to={`/issues?status=open${scope}`} aria-label={`查看当前待处置 ${summary.open_now} 个问题`}><strong>{summary.open_now}</strong></Link><small>当前存量 · 不限时间</small></div>
      <div><span>本期人工标记修复</span><strong>{summary.fixed}</strong><small>人工结论 · 未经系统验证</small></div>
    </section>
    <QualityOverview data={data} days={days} repositoryId={repositoryId} />
    <section className="overview-diagnostics" aria-labelledby="overview-diagnosis-title">
      <div className="overview-diagnosis-heading"><h2 id="overview-diagnosis-title">问题诊断</h2><p>查看当前风险与本期发现构成，按项目定位需要跟进的问题。</p></div>
      <div className="overview-diagnosis-grid"><ProblemDistributions kind="severity" data={data} repositoryId={repositoryId} />
        <QualityBreakdown quality={data.quality} /></div>
    </section>
    <ProjectSummary projects={data.projects} />
    <Collapse className="overview-analysis" items={[{ key: "details", label: "更多效果分析与统计口径", children: <>
      <dl className="overview-extra-facts"><div><dt>生成 / 发布</dt><dd>{summary.generated} / {summary.published}</dd><small>发布仅指 GitLab 行内评论成功</small></div>
        <div><dt>人工反馈误报率</dt><dd>{summary.feedback_marked >= 5 ? `${Math.round(summary.false_positive / summary.feedback_marked * 100)}%` : "数据不足"}</dd><small>{summary.false_positive} / {summary.feedback_marked} 条有帮助或误报评价，至少 5 条才展示比例</small></div>
        <div><dt>本期其他记录</dt><dd>失败评审 {summary.failed_reviews} 次 · 问题忽略 {summary.ignored} 个</dd></div></dl>
      <p>本期评审按完成时间统计，包含完成、覆盖不完整、失败和跳过的任务，不等于成功评审数。新问题按问题编号去重、首次发现时间统计；重复出现不重复新增。</p>
      <p>修复数来自本期关闭且当前仍为已修复的人工标记（含批量操作），不代表系统已验证代码修复；未再次出现不会自动计为修复。当前待处置含暂停项目的历史开放问题，不受时间窗口影响。</p>
      <p>质量分析仅统计当前终态评审的有效发现：初审按完成时间，补审主发现按来源出现时间入窗；不计历史尝试、候选重复来源或初审镜像。未评价、忽略及历史修复反馈不参与误报占比分母，不能把其余反馈自动称为准确率。优化方向按同集合发现类别归类，不推断单条规则效果。</p>
    </> }]} />
  </section>;
}
