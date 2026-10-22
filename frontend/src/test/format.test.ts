/** @description 验证 OCR 枚举在管理台中的中文展示。 */

import { describe, expect, it } from "vitest";

import {
  formatCategory,
  formatCost,
  formatDuration,
  formatSeverity,
} from "../ui/format";

describe("评审标签格式化", () => {
  it("翻译已知的严重级别和问题分类", () => {
    expect(formatSeverity("low")).toBe("低危");
    expect(formatCategory("documentation")).toBe("文档");
    expect(formatCategory("bug")).toBe("缺陷");
  });

  it("保留未知值并处理空值", () => {
    expect(formatSeverity("custom")).toBe("custom");
    expect(formatSeverity(null)).toBe("未分级");
    expect(formatCategory(undefined)).toBe("未分类");
  });

  it("展示任务耗时与按币种计算的消费", () => {
    expect(formatDuration("2026-09-29 09:33:43", "2026-09-29 09:40:51")).toBe("7 分 8 秒");
    expect(formatDuration(null, null)).toBe("—");
    expect(formatCost({ currency: "CNY", total: "3" })).toBe("¥3.0000");
    expect(formatCost(null)).toBe("—");
  });
});
