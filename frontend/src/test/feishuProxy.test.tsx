/** @description 保护飞书编辑的 POST 兼容、凭据省略及代理失败保留草稿；仅使用合成响应。 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";

import { FeishuHooksPage } from "../pages/FeishuHooksPage";

it.each([200, 502])("编辑通过 POST 保存，响应 %s 时不重试、不提交空凭据", async (status) => {
  const writes: { path: string; method: string; body: unknown }[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url, options) => {
    const path = String(url);
    if (options?.method) {
      writes.push({ path, method: options.method, body: JSON.parse(String(options.body)) });
      return new Response(status === 502 ? "<h1>Bad Gateway</h1>" : '{"id":1}', { status });
    }
    return new Response(path === "/api/notification-targets"
      ? '[{"id":1,"name":"合成通道","repository_count":0,"has_signing_secret":true}]' : "[]");
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<MemoryRouter><QueryClientProvider client={client}>
    <FeishuHooksPage token="" />
  </QueryClientProvider></MemoryRouter>);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "编辑 合成通道" }));
  await user.clear(screen.getByLabelText("配置名称"));
  await user.type(screen.getByLabelText("配置名称"), "修改后通道");
  await user.click(screen.getByRole("button", { name: "保存通知通道" }));
  if (status === 502) {
    expect(await screen.findByRole("alert")).toHaveTextContent("无法确认本次操作是否完成");
    expect(screen.getByLabelText("配置名称")).toHaveValue("修改后通道");
  } else expect(await screen.findByRole("status")).toHaveTextContent("通知通道已保存，可在列表独立测试，再关联项目。");
  expect(writes).toEqual([{ path: "/api/notification-targets/1", method: "POST", body: { name: "修改后通道" } }]);
});
