/** @description 保护管理网关故障的错误语义、关联信息与写请求不自动重试边界。 */
import { expect, it, vi } from "vitest";

import { apiRequest } from "../api/client";

it("管理代理返回 HTML 502 时说明操作结果未知，不自动重试保存", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("<h1>Bad Gateway</h1>", {
    status: 502,
    headers: { "X-Request-ID": "synthetic-request-id" },
  }));
  await expect(apiRequest("", "/api/model-profiles", { method: "POST", body: "{}" })).rejects.toMatchObject({
    status: 502,
    requestId: "synthetic-request-id",
    message: expect.stringContaining("无法确认本次操作是否完成"),
  });
  expect(fetch).toHaveBeenCalledTimes(1);
});

it("JSON 错误仍保留服务端提供的诊断与错误码", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ detail: {
    message: "合成代理不可达", code: "gateway_unavailable",
  } }), { status: 502 }));
  await expect(apiRequest("", "/api/model-profiles")).rejects.toMatchObject({
    status: 502, code: "gateway_unavailable", message: "合成代理不可达",
  });
});
