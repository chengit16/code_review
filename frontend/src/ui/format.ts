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
