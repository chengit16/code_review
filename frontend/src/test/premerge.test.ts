/** @description 验证合并前结果解析与覆盖证明，损坏或不完整工件不得显示通过。 */
import { describe, expect, it } from "vitest";

import { parsePremergeResult } from "../api/premerge";

const item = { item_id: "one", path: "src/app.py" };
const result = (coverage = { selected: [item], completed: [item], reused: [], failed: [], waived: [] }) => JSON.stringify({ comments: [], manifest: { terminal_state: "complete", coverage } });

describe("合并前覆盖证明", () => {
  it("完整且无发现才允许展示无问题", () => {
    expect(parsePremergeResult(result())).toMatchObject({ valid: true, completeCoverage: true, comments: [] });
  });
  it("缺少覆盖、重复或遗漏项不能视为完整", () => {
    expect(parsePremergeResult('{"comments":[]}').completeCoverage).toBe(false);
    expect(parsePremergeResult(result({ selected: [item], completed: [], reused: [], failed: [], waived: [] })).completeCoverage).toBe(false);
    expect(parsePremergeResult(result({ selected: [item], completed: [item, item], reused: [], failed: [], waived: [] })).completeCoverage).toBe(false);
  });
  it("损坏结果和错误发现结构不抛渲染异常", () => {
    for (const text of [null, "{invalid", '{"comments":[null]}', '{"comments":[{"path":4,"content":"错误"}]}']) {
      expect(parsePremergeResult(text)).toMatchObject({ valid: false, completeCoverage: false, comments: [] });
    }
  });
});
