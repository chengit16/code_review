/** @description 列表时间筛选在设备本地输入与带时区 UTC 参数之间转换，不修改持久化时间。 */

/** 将 URL 中完整时间转为本地分钟输入，非法值不伪造日期。 */
export function localTimeInput(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

/** 提交时显式携带时区，空值表示清除，非法日期拒绝提交。 */
export function utcTimeInput(value: string): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) throw new Error("时间无效");
  return date.toISOString();
}
