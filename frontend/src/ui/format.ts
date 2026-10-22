/** @description 管理台表格与详情页共用的短标识和时间格式。 */

/** 将完整 SHA 缩短为便于扫描的形式，完整值仍可在详情中访问。 */
export function shortSha(value: string | null): string {
  return value ? value.slice(0, 10) : "—";
}

/** 将后端 UTC 时间转成当前设备的本地时间。 */
export function formatTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value.includes("T") ? value : `${value.replace(" ", "T")}Z`);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", { hour12: false });
}

function parseServerTime(value: string): Date {
  return new Date(value.includes("T") ? value : `${value.replace(" ", "T")}Z`);
}

/** 按任务实际起止时间显示耗时；运行中任务以当前时间为终点。 */
export function formatDuration(
  startedAt: string | null | undefined,
  finishedAt: string | null | undefined,
  now = new Date(),
): string {
  if (!startedAt) return "—";
  const start = parseServerTime(startedAt);
  const end = finishedAt ? parseServerTime(finishedAt) : now;
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return "—";
  const totalSeconds = Math.max(0, Math.floor((end.getTime() - start.getTime()) / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours) return `${hours} 小时 ${minutes} 分`;
  if (minutes) return `${minutes} 分 ${seconds} 秒`;
  return `${seconds} 秒`;
}

/** 展示按实际 Token 与任务单价快照计算的消费金额。 */
export function formatCost(
  cost: { currency: "CNY" | "USD"; total: string } | null | undefined,
): string {
  if (!cost) return "—";
  const amount = Number(cost.total);
  if (!Number.isFinite(amount)) return "—";
  const symbol = cost.currency === "CNY" ? "¥" : "$";
  if (amount > 0 && amount < 0.000001) return `<${symbol}0.000001`;
  return `${symbol}${amount.toLocaleString("zh-CN", {
    minimumFractionDigits: 4,
    maximumFractionDigits: 6,
  })}`;
}

const severityLabels: Record<string, string> = {
  critical: "严重",
  high: "高危",
  medium: "中危",
  low: "低危",
};

const categoryLabels: Record<string, string> = {
  bug: "缺陷",
  correctness: "正确性",
  documentation: "文档",
  maintainability: "可维护性",
  performance: "性能",
  reliability: "可靠性",
  security: "安全",
  style: "代码风格",
  other: "其他",
};

/** 将 OCR 严重级别转换为管理台中文标签，未知值保留原文以便排查。 */
export function formatSeverity(value: string | null | undefined): string {
  return value ? severityLabels[value] ?? value : "未分级";
}

/** 将 OCR 问题分类转换为管理台中文标签，未知值保留原文以免丢失信息。 */
export function formatCategory(value: string | null | undefined): string {
  return value ? categoryLabels[value] ?? value : "未分类";
}
