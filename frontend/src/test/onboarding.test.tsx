/** @description 项目连接清单保护未知、版本失效及通知跳过；全为合成响应，不触发外部测试。 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";

import { DesignProvider } from "../app/DesignProvider";
import { OnboardingPage } from "../pages/OnboardingPage";

const effective = { model: { id: 7, complete: true, name: "合成模型", source: "global" }, latest_job: null };
function mount(responses: Record<string, object | Error> = {}) {
  const calls: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    calls.push(`${init?.method ?? "GET"} ${input}`);
    const key = String(input).split("/").pop() ?? "";
    const value = responses[key] ?? [];
    return new Response(JSON.stringify(value instanceof Error ? { detail: value.message } : value), { status: value instanceof Error ? 503 : 200 });
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<DesignProvider><QueryClientProvider client={client}><MemoryRouter><OnboardingPage token="" /></MemoryRouter></QueryClientProvider></DesignProvider>);
  return { client, calls };
}

it("独立项目可走完准备清单，未选择通知允许跳过；历史记录不冒充真实验收", async () => {
  const { calls } = mount({ "model-profiles": [{ id: 7 }], repositories: [{ id: 1, name: "甲", enabled: 1 }, { id: 2, name: "未接通的乙" }],
    "effective-configuration": effective, "connection-checks": [
      { id: 1, kind: "git", repository_id: 1, status: "passed", config_current: true },
      { id: 2, kind: "gitlab", repository_id: 1, status: "passed", config_current: true },
      { id: 3, kind: "model", model_profile_id: 7, status: "passed", config_current: true },
    ] });
  expect(await screen.findByText("4 / 4")).toBeVisible();
  expect(screen.getByText(/此项目未选择通知，允许跳过/)).toBeVisible();
  expect(screen.getByText(/连接准备已完成，请继续核对真实试运行/)).toBeVisible();
  expect(screen.getByRole("link", { name: "测试项目连接" })).toHaveAttribute("href", "/repositories?repository=1&section=connection");
  expect(calls.every((call) => call.startsWith("GET "))).toBe(true);
});

it("读取失败显示待确认并可恢复，不把缺失配置当作零进度", async () => {
  const responses = { "model-profiles": new Error("合成读取失败") as object, repositories: [{ id: 1 }], "effective-configuration": effective };
  mount(responses);
  expect(await screen.findByText("待确认", { selector: "strong" })).toBeVisible();
  expect(screen.queryByText("0 / 4")).toBeNull();
  expect(await screen.findByText(/合成读取失败/)).toBeVisible();
  responses["model-profiles"] = [{ id: 7 }];
  await userEvent.click(screen.getByRole("button", { name: "重新读取模型" }));
  expect(await screen.findByText("2 / 4")).toBeVisible();
});

it("最新失败及配置变动使准备失效，不能使用旧通过或其他模型目标", async () => {
  const { client } = mount({ "model-profiles": [{ id: 7 }], repositories: [{ id: 1, has_feishu_webhook: true, feishu_target_id: 8 }], "effective-configuration": effective,
    "connection-checks": [
      { id: 1, kind: "git", repository_id: 1, status: "passed", config_current: true },
      { id: 2, kind: "gitlab", repository_id: 1, status: "passed", config_current: true },
      { id: 9, kind: "git", repository_id: 1, status: "failed", config_current: true },
      { id: 3, kind: "model", model_profile_id: 6, status: "passed", config_current: true },
      { id: 4, kind: "feishu", notification_target_id: 8, status: "passed", config_current: false },
    ] });
  expect(await screen.findByText("1 / 4")).toBeVisible();
  act(() => client.setQueryData(["connection-checks"], [
    { id: 10, kind: "git", repository_id: 1, status: "passed", config_current: true },
    { id: 11, kind: "gitlab", repository_id: 1, status: "passed", config_current: true },
    { id: 12, kind: "model", model_profile_id: 7, status: "passed", config_current: true },
    { id: 13, kind: "feishu", notification_target_id: 8, status: "passed", config_current: true },
  ]));
  expect(await screen.findByText("4 / 4")).toBeVisible();
  act(() => client.setQueryData(["effective-configuration", 1], { ...effective, model: { ...effective.model, id: 99 } }));
  expect(await screen.findByText("3 / 4")).toBeVisible();
});
