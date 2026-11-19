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

/** 完整带时区时间回显为设备本地日期；不以 UTC 日期替代用户所选日。 */
export function localDateInput(value: string | null): string {
  return localTimeInput(value).slice(0, 10);
}

/** 日期筛选包含起止两天；按本地日历构造边界，兼容夏令时和跨月。 */
export function utcDateInput(value: string, boundary: "start" | "end"): string {
  if (!value) return "";
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) throw new Error("请选择有效日期");
  const [year, month, day] = value.split("-").map(Number);
  const date = new Date(year, month - 1, day);
  if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) throw new Error("请选择有效日期");
  if (boundary === "end") date.setHours(23, 59, 59, 999);
  return date.toISOString();
}
