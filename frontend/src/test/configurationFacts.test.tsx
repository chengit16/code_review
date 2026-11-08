/** @description 配置辅助查询失败和缓存刷新失败不能冒充未配置或关闭；不执行真实认证切换。 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";

import { DesignProvider } from "../app/DesignProvider";
import { FeishuHooksPage } from "../pages/FeishuHooksPage";
import { RepositoriesPage } from "../pages/RepositoriesPage";
import { UsersPage } from "../pages/UsersPage";

function mount(node: ReactNode, responses: Record<string, object | Error>) {
  const writes: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    if (init?.method && init.method !== "GET") writes.push(init.method);
    const value = responses[String(input)] ?? [];
    return new Response(JSON.stringify(value instanceof Error ? { detail: value.message } : value), { status: value instanceof Error ? 503 : 200 });
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<DesignProvider><QueryClientProvider client={client}><MemoryRouter>{node}</MemoryRouter></QueryClientProvider></DesignProvider>);
  return { client, writes };
}

it("认证方式失败时不展示可切换的默认关闭控件，恢复后才允许操作", async () => {
  const responses = { "/api/auth/mode": new Error("合成认证读取失败") as object, "/api/auth/users": [] };
  const { client, writes } = mount(<UsersPage token="" />, responses);
  expect(await screen.findByText("认证方式读取失败，状态未知")).toBeVisible();
  expect(screen.queryByRole("checkbox", { name: "启用多人账号登录" })).toBeNull();
  responses["/api/auth/mode"] = { users_enabled: true };
  await userEvent.click(screen.getByRole("button", { name: "重新读取认证方式" }));
  expect(await screen.findByRole("checkbox", { name: "启用多人账号登录" })).toBeChecked();
  responses["/api/auth/mode"] = new Error("合成刷新失败");
  await act(async () => { await client.invalidateQueries({ queryKey: ["management-auth-mode"] }); });
  expect(await screen.findByText("认证方式读取失败，状态未知")).toBeVisible();
  expect(screen.queryByRole("checkbox", { name: "启用多人账号登录" })).toBeNull();
  expect(writes).toEqual([]);
});

it("仓库辅助查询失败不显示待重新测试或未配置，独立重试不改变仓库", async () => {
  const responses: Record<string, object | Error> = {
    "/api/repositories": [{ id: 1, name: "合成仓库", feishu_target_id: 8, enabled: 1 }],
    "/api/notification-targets": new Error("合成通道读取失败"), "/api/repository-readiness": new Error("合成接入读取失败"),
  };
  const { writes } = mount(<RepositoriesPage token="" />, responses);
  expect(await screen.findByText("接入状态待确认")).toBeVisible();
  expect(await screen.findByText("飞书配置待确认")).toBeVisible();
  expect(screen.queryByText("待重新测试")).toBeNull();
  expect(screen.queryByText("未配置")).toBeNull();
  responses["/api/repository-readiness"] = [{ repository_id: 1, status: "ready" }];
  await userEvent.click(screen.getByRole("button", { name: "重新读取接入状态" }));
  expect(await screen.findByText("已验证")).toBeVisible();
  expect(screen.getByText("飞书配置待确认")).toBeVisible();
  expect(writes).toEqual([]);
});

it("通知页关联仓库失败不显示尚未关联，恢复后才展示真实空关联", async () => {
  const responses: Record<string, object | Error> = {
    "/api/repositories": new Error("合成仓库读取失败"),
    "/api/notification-targets": [{ id: 8, name: "合成通道", repository_count: 0 }],
  };
  const { writes } = mount(<FeishuHooksPage token="" />, responses);
  expect(await screen.findByText("关联仓库待确认")).toBeVisible();
  expect(screen.queryByText("尚未关联仓库")).toBeNull();
  responses["/api/repositories"] = [];
  await userEvent.click(screen.getByRole("button", { name: "重新读取关联仓库" }));
  await waitFor(() => expect(screen.getByText("尚未关联仓库")).toBeVisible());
  expect(writes).toEqual([]);
});
