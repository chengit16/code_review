/** @description 日期筛选保护本地日历边界、整天结束及非法日期拒绝，不依赖业务时钟。 */
import { expect, it } from "vitest";

import { localDateInput, utcDateInput } from "../ui/listDates";

it("同一天的创建范围包含本地零点至当天末尾，并可回显原日期", () => {
  const start = utcDateInput("2026-11-13", "start"), end = utcDateInput("2026-11-13", "end");
  expect(start).toBe(new Date(2026, 10, 13, 0, 0, 0, 0).toISOString());
  expect(end).toBe(new Date(2026, 10, 13, 23, 59, 59, 999).toISOString());
  expect(localDateInput(start)).toBe("2026-11-13");
  expect(localDateInput(end)).toBe("2026-11-13");
});

it("跨月和闰年日期按日历构造，非法日期不会被自动挪到下月", () => {
  expect(localDateInput(utcDateInput("2024-02-29", "end"))).toBe("2024-02-29");
  expect(() => utcDateInput("2026-02-29", "start")).toThrow("请选择有效日期");
  expect(() => utcDateInput("2026-11-31", "end")).toThrow("请选择有效日期");
  expect(() => utcDateInput("2026-11-13T08:00", "start")).toThrow("请选择有效日期");
  expect(utcDateInput("", "end")).toBe("");
  expect(localDateInput("invalid")).toBe("");
});
