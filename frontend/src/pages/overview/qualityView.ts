/** @description 质量展示的计数、样本链接和周桶纯函数；不计算跨粒度质量评分。 */
import type { FeedbackKind, QualityCounts, ReviewQuality } from "../../api/effectiveness";

/** 四种互斥处置共用标签；未知来源单独提示，不作为可写状态。 */
export const dispositionSeries = [
  { key: "open", label: "待处理" }, { key: "fixed", label: "已修复" },
  { key: "ignored", label: "已忽略" }, { key: "false_positive", label: "误报" },
] as const;

/** 图表、文字和表格共用的反馈语义与颜色。 */
export const feedbackSeries: Array<{ key: keyof Omit<QualityCounts, "total">; label: string; feedback: FeedbackKind }> = [
  { key: "helpful", label: "有帮助", feedback: "helpful" },
  { key: "false_positive", label: "误报", feedback: "false_positive" },
  { key: "ignored", label: "忽略", feedback: "ignored" },
  { key: "unmarked", label: "未评价", feedback: "unmarked" },
];

/** 比例始终附带分母；五条门槛不代表统计置信度。 */
export function qualityRatio(numerator: number, denominator: number, minimum = 1) {
  return denominator < minimum ? denominator ? `样本不足（${numerator}/${denominator}）` : "—（0 样本）"
    : `${Math.round(numerator / denominator * 100)}%（${numerator}/${denominator}）`;
}

/** 90 天七行一桶，只加计数，不平均百分比。 */
export function qualityBuckets(rows: ReviewQuality["trend"], days: number) {
  const result = [];
  const size = days === 90 ? 7 : 1;
  for (let index = 0; index < rows.length; index += size) {
    const group = rows.slice(index, index + size);
    const counts = group.reduce<QualityCounts>((sum, row) => ({ total: sum.total + row.total,
      helpful: sum.helpful + row.helpful, false_positive: sum.false_positive + row.false_positive,
      ignored: sum.ignored + row.ignored, unmarked: sum.unmarked + row.unmarked }),
    { total: 0, helpful: 0, false_positive: 0, ignored: 0, unmarked: 0 });
    result.push({ ...counts, start: group[0].day, end: group[group.length - 1].day });
  }
  return result;
}

/** 保留首页范围与显式 UTC 窗口，样本筛选进入地址栏并可前后退。 */
export function qualitySampleHref(params: URLSearchParams, quality: ReviewQuality,
  filters: { feedback?: FeedbackKind; status?: string; category?: string; repositoryId?: number } = {}) {
  const next = new URLSearchParams(params);
  for (const key of [...next.keys()]) if (key.startsWith("sample_")) next.delete(key);
  next.set("sample_open", "1");
  next.set("sample_since", quality.since);
  next.set("sample_until", quality.until);
  if (filters.feedback) next.set("sample_feedback", filters.feedback);
  if (filters.status) next.set("sample_status", filters.status);
  if (filters.category) next.set("sample_category", filters.category);
  if (filters.repositoryId) next.set("sample_repository", String(filters.repositoryId));
  return `?${next}`;
}
