/** @description 验证缺少 AbortSignal 静态方法时的请求、超时、取消和资源清理；不调用外部服务。 */
import { afterEach, expect, it, vi } from "vitest";

import { apiRequest } from "../api/client";
import { createRequestSignal } from "../api/requestSignal";

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

it("缺少 AbortSignal.any/timeout 时正常请求，成功后移除监听和计时器", async () => {
  vi.useFakeTimers(); vi.stubGlobal("AbortSignal", {});
  const parent = new AbortController();
  const remove = vi.spyOn(parent.signal, "removeEventListener");
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response('{"ok":true}'));
  await expect(apiRequest("", "/api/test", { signal: parent.signal })).resolves.toEqual({ ok: true });
  expect(fetch).toHaveBeenCalledOnce();
  expect(remove).toHaveBeenCalledWith("abort", expect.any(Function));
  expect(vi.getTimerCount()).toBe(0);
});

it("已取消信号立即传递，既不计时也不伪装成超时", () => {
  vi.useFakeTimers();
  const parent = new AbortController(); parent.abort();
  const request = createRequestSignal(parent.signal);
  expect(request.signal.aborted).toBe(true);
  expect(request.hasTimedOut()).toBe(false);
  expect(vi.getTimerCount()).toBe(0);
  request.dispose(); request.dispose();
});

it("调用方后续取消会中止请求，超过截止时间仍保留主动取消分类", async () => {
  vi.useFakeTimers();
  const parent = new AbortController();
  const request = createRequestSignal(parent.signal);
  parent.abort();
  await vi.advanceTimersByTimeAsync(30000);
  expect(request.signal.aborted).toBe(true);
  expect(request.hasTimedOut()).toBe(false);
  request.dispose();
});

it("到期后标注超时并取消，主动调用释放后不会再取消", async () => {
  vi.useFakeTimers();
  const expired = createRequestSignal(null, 10);
  const finished = createRequestSignal(null, 10); finished.dispose();
  await vi.advanceTimersByTimeAsync(10);
  expect(expired.signal.aborted).toBe(true);
  expect(expired.hasTimedOut()).toBe(true);
  expect(finished.signal.aborted).toBe(false);
  expired.dispose();
});

it("网络等待超时转为明确 API 错误，不重发写请求", async () => {
  vi.useFakeTimers();
  const fetch = vi.spyOn(globalThis, "fetch").mockImplementation((_url, options) => new Promise((_resolve, reject) => {
    options?.signal?.addEventListener("abort", () => reject(new DOMException("合成取消", "AbortError")), { once: true });
  }));
  const checked = expect(apiRequest("", "/api/test", { method: "POST" })).rejects.toMatchObject({ status: 0, code: "timeout" });
  await vi.advanceTimersByTimeAsync(30000); await checked;
  expect(fetch).toHaveBeenCalledOnce();
  expect(vi.getTimerCount()).toBe(0);
});

it("响应体读取也受截止时间约束，不误报为 JSON 格式错误", async () => {
  vi.useFakeTimers();
  vi.spyOn(globalThis, "fetch").mockImplementation(async (_url, options) => {
    const response = new Response("{}");
    vi.spyOn(response, "json").mockImplementation(() => new Promise((_resolve, reject) => {
      options?.signal?.addEventListener("abort", () => reject(new DOMException("合成取消", "AbortError")), { once: true });
    }));
    return response;
  });
  const checked = expect(apiRequest("", "/api/test")).rejects.toMatchObject({ code: "timeout" });
  await vi.advanceTimersByTimeAsync(30000); await checked;
  expect(vi.getTimerCount()).toBe(0);
});

it("调用方主动取消不转换为网络错误，失败路径仍清理资源", async () => {
  vi.useFakeTimers();
  const parent = new AbortController();
  vi.spyOn(globalThis, "fetch").mockImplementation((_url, options) => new Promise((_resolve, reject) => {
    options?.signal?.addEventListener("abort", () => reject(new DOMException("合成取消", "AbortError")), { once: true });
  }));
  const checked = expect(apiRequest("", "/api/test", { signal: parent.signal })).rejects.toMatchObject({ name: "AbortError" });
  parent.abort(); await checked;
  expect(vi.getTimerCount()).toBe(0);
});
