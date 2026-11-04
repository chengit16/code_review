/** @description 保护模型新增与编辑无字段校验保存；网络仅返回合成配置，不发起模型连接。 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { expect, it, vi } from "vitest";

import { SettingsPage } from "../pages/SettingsPage";

it("空字段、未完成地址和任意单价均可新增与编辑保存", async () => {
  const writes: { method: string; body: Record<string, unknown> }[] = [];
  let profiles: Record<string, unknown>[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url, options) => {
    if (String(url).includes("connection-checks")) return new Response("[]");
    if (options?.method === "POST" || options?.method === "PATCH") {
      const body = JSON.parse(String(options.body));
      writes.push({ method: options.method, body });
      const profile = { id: 1, enabled: 0, has_api_key: false, version: 1, ...body };
      profiles = [profile];
      return new Response(JSON.stringify(profile));
    }
    return new Response(JSON.stringify(profiles));
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter([{ path: "/", element: <SettingsPage token="" /> }]);
  render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "新增模型" }));
  await user.type(screen.getByLabelText("Base URL"), "尚未完成");
  await user.type(screen.getByLabelText("输入单价（每百万 Token）"), "待确认");
  await user.click(screen.getByRole("button", { name: "保存模型" }));
  expect(await screen.findByText("模型已保存，请在列表中启用")).toBeVisible();
  expect(writes[0].body).toMatchObject({ name: "", model: "", api_key: "", base_url: "尚未完成", input_price_per_million: "待确认", output_price_per_million: null });
  await user.click(await screen.findByRole("button", { name: /^编辑$/ }));
  await user.clear(screen.getByLabelText("Base URL"));
  await user.click(screen.getByRole("button", { name: "保存模型" }));
  expect(await screen.findByText("模型配置已更新")).toBeVisible();
  expect(writes[1]).toMatchObject({ method: "POST", body: { name: "", model: "", base_url: "" } });
  expect(writes[1].body).not.toHaveProperty("api_key");
});

it("保存遇到代理 502 时保留全部草稿，不自动重复创建模型", async () => {
  const writes: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (_url, options) => {
    if (options?.method === "POST") {
      writes.push(String(options.body));
      return new Response("<h1>Bad Gateway</h1>", { status: 502 });
    }
    return new Response("[]");
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter([{ path: "/", element: <SettingsPage token="" /> }]);
  render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "新增模型" }));
  await user.type(screen.getByLabelText("配置名称"), "合成配置");
  await user.type(screen.getByLabelText("Base URL"), "未完成地址");
  await user.type(screen.getByLabelText("API Key"), "synthetic-key");
  await user.click(screen.getByRole("button", { name: "保存模型" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("无法确认本次操作是否完成");
  expect(screen.getByLabelText("配置名称")).toHaveValue("合成配置");
  expect(screen.getByLabelText("Base URL")).toHaveValue("未完成地址");
  expect(screen.getByLabelText("API Key")).toHaveValue("synthetic-key");
  expect(writes).toHaveLength(1);
});
