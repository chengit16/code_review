/** @description 验证安全与普通 HTTP 环境下的 UUID v4，不允许弱随机或缺少安全源时提交。 */
import { afterEach, expect, it, vi } from "vitest";

import { createCommandId } from "../api/commandId";

afterEach(() => vi.unstubAllGlobals());

it("安全上下文保留原生 UUID 方法及接收者", () => {
  const source = { randomUUID() { expect(this).toBe(source); return "12345678-1234-4234-8234-123456789abc"; } };
  vi.stubGlobal("crypto", source);
  expect(createCommandId()).toBe("12345678-1234-4234-8234-123456789abc");
});

it("普通 HTTP 缺少 randomUUID 时使用安全随机字节并固定版本和变体", () => {
  const fill = vi.fn((bytes: Uint8Array) => bytes.fill(255));
  vi.stubGlobal("crypto", { getRandomValues: fill });
  expect(createCommandId()).toBe("ffffffff-ffff-4fff-bfff-ffffffffffff");
  expect(fill).toHaveBeenCalledOnce();
});

it("兼容分支多次生成不同且符合 UUID v4 格式的标识", () => {
  const source = globalThis.crypto;
  vi.stubGlobal("crypto", { getRandomValues: source.getRandomValues.bind(source) });
  const ids = Array.from({ length: 100 }, createCommandId);
  expect(new Set(ids).size).toBe(100);
  for (const id of ids) expect(id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
});

it.each([undefined, {}])("缺少安全随机源时明确失败，不回退 Math.random", (source) => {
  vi.stubGlobal("crypto", source);
  const weak = vi.spyOn(Math, "random");
  expect(createCommandId).toThrow("浏览器无法生成安全的请求标识");
  expect(weak).not.toHaveBeenCalled();
});
