/** @description 当前开放分级及本期出现类别的横向数量图；文字保留精确数值和范围。 */
import { Link, useSearchParams } from "react-router-dom";

import type { EffectivenessSnapshot, SeverityLevel } from "../../api/effectiveness";
import { formatCategory } from "../../ui/format";
import { qualitySampleHref } from "./qualityView";

const levels: Array<[SeverityLevel, string]> = [["critical", "严重"], ["high", "高危"], ["medium", "中危"], ["low", "低危"], ["unclassified", "未分级"]];

/** 数量条统一按本图最大值缩放，不将出现次数伪装为去重问题占比。 */
export function ProblemDistributions({ kind, data, repositoryId }: {
  /** 当前分级或本期类别。 */ kind: "severity" | "category";
  /** 同源统计快照；缺分级摘要时明确不可用。 */ data: EffectivenessSnapshot;
  /** 项目筛选沿用到严重级别的问题入口。 */ repositoryId: string;
}) {
  const isSeverity = kind === "severity";
  const [params] = useSearchParams();
  const quality = data.quality;
  const current = quality?.pending_severity ? { severity_counts: quality.pending_severity, open_count: quality.summary.unmarked } : undefined;
  const title = isSeverity ? "待反馈严重级别" : "问题类别分布";
  const scope = new URLSearchParams(params);
  if (repositoryId) scope.set("repository_id", repositoryId);
  const rows = isSeverity ? levels.map(([key, label]) => ({ key, label, count: current?.severity_counts[key] ?? 0 }))
    : data.categories.map((item) => ({ key: item.category, label: formatCategory(item.category), count: item.generated }));
  const max = Math.max(1, ...rows.map((row) => row.count));
  return <section className={`overview-panel overview-distribution ${isSeverity ? "overview-severity" : "overview-category"}`} aria-label={title}>
    <div className="section-head"><h2>{title}</h2><span>{isSeverity ? "同一窗口 · 未评价发现" : "本期出现次数 · 前 20 类"}</span></div>
    {isSeverity && !current ? <p>当前服务暂不提供分级汇总</p> : <>
      {(!isSeverity && !rows.length) || (isSeverity && current?.open_count === 0) ? <p className="overview-empty">{isSeverity ? "本期没有待反馈发现" : "本期没有发现记录"}</p> : null}
      <ul className="overview-bars">{rows.map((row) => <li key={row.key} className={`overview-bar-${row.key}`}>
        <div>{isSeverity && quality ? <Link to={qualitySampleHref(scope, quality, { handling: "pending", severity: row.key })}>{row.label}</Link> : <span>{row.label}</span>}<strong>{row.count}</strong></div>
        <div className="overview-bar-track" aria-hidden="true"><span style={{ width: `${row.count / max * 100}%` }} /></div>
      </li>)}</ul>
    </>}
  </section>;
}
