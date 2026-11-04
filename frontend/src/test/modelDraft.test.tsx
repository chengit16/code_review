/** @description 保护模型新增与编辑无字段校验保存；网络仅返回合成配置，不发起模型连接。 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
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

it("自动读取模型目录后允许选择模型标识再保存", async () => {
  const writes: Record<string, unknown>[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url, options) => {
    if (String(url).includes("model-catalog")) {
      return new Response(JSON.stringify({ models: ["catalog-model-a", "catalog-model-b"] }));
    }
    if (String(url).includes("model-profiles") && options?.method === "POST") {
      const body = JSON.parse(String(options.body));
      writes.push(body);
      return new Response(JSON.stringify({ id: 1, enabled: 0, has_api_key: true, version: 1, ...body }));
    }
    return new Response("[]");
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter([{ path: "/", element: <SettingsPage token="" /> }]);
  render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "新增模型" }));
  await user.type(screen.getByLabelText("API Key"), "synthetic-key");
  await user.click(screen.getByRole("button", { name: "自动获取模型" }));
  Element.prototype.scrollIntoView = vi.fn();
  fireEvent.click(await screen.findByLabelText("选择模型"));
  fireEvent.click(await screen.findByRole("option", { name: "catalog-model-b" }));
  await user.click(screen.getByRole("button", { name: "保存模型" }));
  expect(await screen.findByText("模型已保存，请在列表中启用")).toBeVisible();
  expect(writes[0]).toMatchObject({ model: "catalog-model-b", api_key: "synthetic-key" });
});

it("编辑时留空密钥可以获取模型，并展示具体鉴权错误", async () => {
  let catalogBody: unknown;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url, options) => {
    if (String(url).includes("model-catalog")) {
      catalogBody = JSON.parse(String(options?.body));
      return new Response(JSON.stringify({ detail: "获取模型列表失败（HTTP 401）：API Key 鉴权失败" }), { status: 502 });
    }
    if (String(url).includes("model-profiles")) return new Response(JSON.stringify([{
      id: 7, name: "公司", provider: "openai", base_url: "https://model.test/v1",
      model: "model-a", price_currency: "CNY", has_api_key: true, enabled: 1,
    }]));
    return new Response("[]");
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter([{ path: "/", element: <SettingsPage token="" /> }]);
  render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "编辑 公司" }));
  expect(screen.getByLabelText("API Key")).toHaveValue("");
  await user.click(screen.getByRole("button", { name: "自动获取模型" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("HTTP 401");
  expect(catalogBody).toEqual({ profile_id: 7, provider: "openai", base_url: "https://model.test/v1", api_key: "" });
  expect(screen.getByLabelText("模型标识")).toHaveValue("model-a");
});
