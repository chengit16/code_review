/** @description 列表按日筛选控件；设备本地日期转换为包含整天的 UTC 边界，不修改业务时间。 */
import { DatePicker } from "antd";
import dayjs from "dayjs";

import { localDateInput, utcDateInput } from "./listDates";

/** 两端可独立清空，父页决定立即查询或显式提交；保留可访问名称而不增加顶部标签。 */
export function ListDateRange({ since, until, onChange, disabled = false, label = "创建日期" }: {
  /** 已生效时间或当前草稿，须包含时区；空字符串表示不限。 */ since: string;
  /** 包含当日末尾的结束边界。 */ until: string;
  /** 返回新的 UTC 边界，空值表示清除该端。 */ onChange: (range: { since: string; until: string }) => void;
  /** 确认或保存期间锁定日期输入。 */ disabled?: boolean;
  /** 仅用于占位与可访问名称。 */ label?: string;
}) {
  const start = localDateInput(since), end = localDateInput(until);
  return <div className="list-date-range" role="group" aria-label={label}>
    <DatePicker aria-label={`${label}起始`} value={start ? dayjs(start) : null} placeholder={`${label}从`} format="YYYY-MM-DD" disabled={disabled} onChange={(value) => onChange({ since: value ? utcDateInput(value.format("YYYY-MM-DD"), "start") : "", until })} />
    <span aria-hidden="true">—</span>
    <DatePicker aria-label={`${label}结束`} value={end ? dayjs(end) : null} placeholder={`${label}至`} format="YYYY-MM-DD" disabled={disabled} onChange={(value) => onChange({ since, until: value ? utcDateInput(value.format("YYYY-MM-DD"), "end") : "" })} />
  </div>;
}
