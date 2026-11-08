/** @description 接入引导保护未知状态、按目标最新记录和接收证据；全部接口合成，不执行外部测试。 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { expect, it, vi } from "vitest";

import { DesignProvider } from "../app/DesignProvider";
import { OnboardingPage } from "../pages/OnboardingPage";

function mount(responses: Record<string, object | Error | Promise<Response>> = {}) {
  const calls: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    calls.push(`${init?.method ?? "GET"} ${input}`);
    const key = String(input).split("/").pop() ?? "";
    const value = responses[key] ?? [];
    if (value instanceof Promise) return value;
    if (value instanceof Error) return new Response(JSON.stringify({ detail: value.message }), { status: 503 });
    return new Response(JSON.stringify(value));
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<DesignProvider><QueryClientProvider client={client}><MemoryRouter initialEntries={["/onboarding"]}><Routes>
    <Route path="/onboarding" element={<OnboardingPage token="" />} /><Route path="/settings" element={<p>内部设置路由</p>} />
  </Routes></MemoryRouter></QueryClientProvider></DesignProvider>);
  return { client, calls, responses };
}

it("显示已保存配置进度，Ant Design 链接保持内部导航", async () => {
  mount({ "model-profiles": [{ id: 1, enabled: 1 }], "notification-targets": [{ id: 1 }] });
  expect(await screen.findByText("2 / 5")).toBeVisible();
  expect(screen.getByRole("link", { name: "稍后再做" })).toHaveAttribute("href", "/");
  await userEvent.click(screen.getByRole("link", { name: "前往模型设置" }));
  expect(await screen.findByText("内部设置路由")).toBeVisible();
});

it("首次加载不显示假零进度，失败可按查询恢复且只发送 GET", async () => {
  let release: (response: Response) => void = () => {};
  const held = new Promise<Response>((resolve) => { release = resolve; });
  const { responses, calls } = mount({ "model-profiles": held });
  expect(screen.getByText(/接入进度待确认/)).toBeVisible();
  expect(screen.queryByText("0 / 5")).toBeNull();
  await act(async () => { release(new Response(JSON.stringify({ detail: "合成读取失败" }), { status: 503 })); });
  expect(await screen.findByText("模型读取失败，状态未知")).toBeVisible();
  expect(screen.queryByText("0 / 5")).toBeNull();
  responses["model-profiles"] = [{ enabled: 1 }];
  await userEvent.click(screen.getByRole("button", { name: "重新读取模型" }));
  expect(await screen.findByText("1 / 5")).toBeVisible();
  expect(calls.every((call) => call.startsWith("GET "))).toBe(true);
});

it("生成回调地址和历史通过不冒充接入完成；按目标取最新测试", async () => {
  const checks = [
    { id: 10, kind: "git", repository_id: 1, status: "failed" },
    { id: 1, kind: "git", repository_id: 1, status: "passed" },
    { id: 2, kind: "gitlab", repository_id: 1, status: "passed" },
    { id: 3, kind: "feishu", repository_id: 1, status: "passed" },
    { id: 4, kind: "model", repository_id: null, status: "passed" },
  ];
  const { client } = mount({ "model-profiles": [{ enabled: 1 }], "notification-targets": [{ id: 1 }],
    repositories: [{ id: 1, enabled: 1, webhook_url: "/callback", last_webhook_at: null }], "connection-checks": checks });
  expect(await screen.findByText("3 / 5")).toBeVisible();
  expect(screen.getByText(/只有地址不能确认已接通/)).toBeVisible();
  expect(screen.queryByText(/各目标最近测试记录通过/)).toBeNull();
  act(() => client.setQueryData(["connection-checks"], checks.filter((check) => check.id !== 10)));
  expect(await screen.findByText(/各目标最近测试记录通过/)).toBeVisible();
  expect(screen.getByText(/未绑定当前配置版本/)).toBeVisible();
  expect(screen.queryByText(/接入清单已完成/)).toBeNull();
  act(() => client.setQueryData(["repositories"], [{ id: 1, enabled: 1, last_webhook_at: "2026-11-08 01:00:00" }]));
  expect(await screen.findByText("4 / 5")).toBeVisible();
  expect(screen.getByText("有接收记录")).toBeVisible();
});
