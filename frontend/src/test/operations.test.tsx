/** @description 合成接口验证分区懒查询、原始执行口径、草稿刷新与旧版缺失；不访问真实服务。 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";

import { DesignProvider } from "../app/DesignProvider";
import { OperationsPage } from "../pages/OperationsPage";

const snapshot = {
  execution_jobs: { queued: 2, running: 3 }, jobs: { queued: 90, running: 99, failed: 4, partial: 1 }, events: {}, deliveries: {}, retry_count: 7,
  oldest_pending_at: null, disk_free_bytes: 10 * 1024 ** 3, orphan_artifacts: 0,
  backup: { last_at: null, healthy: true, age_seconds: 100 }, alerts: ["存在失败或部分完成的评审"],
};
function page(initial = "/operations", data: object = snapshot) {
  const calls: string[] = [];
  const fetch = vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => {
    const path = String(url); calls.push(path);
    if (data instanceof Error && path.endsWith("/operations")) return new Response(JSON.stringify({ detail: data.message }), { status: 503 });
    const response = path.endsWith("/operations") ? data : path.endsWith("/worker-scheduler/config") ? { model_task_concurrency: 1, version: 1 }
      : path.endsWith("/alerts") ? { config: { enabled: false, target_id: null, queue_minutes: 30 }, deliveries: [] } : [];
    return new Response(JSON.stringify(response));
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<DesignProvider><QueryClientProvider client={client}><MemoryRouter initialEntries={[initial]}><OperationsPage token="" /></MemoryRouter></QueryClientProvider></DesignProvider>);
  return { client, calls, fetch };
}

it("默认页使用原始执行计数，昂贵维护和告警请求不提前执行", async () => {
  const { calls } = page();
  await screen.findByText("2", { selector: ".operations-number" });
  expect(screen.getByText("3", { selector: ".operations-number" })).toBeVisible();
  expect(screen.getByText("5", { selector: ".operations-number" })).toBeVisible();
  expect(screen.queryByText("运维风险待核对")).not.toBeInTheDocument();
  expect(calls.some((url) => /maintenance|alerts|audit|reconciliation/.test(url))).toBe(false);
});

it("切换分区与当前视图刷新不清空并发草稿，隐藏配置查询不被失效重新拉取", async () => {
  const { client, calls } = page();
  const user = userEvent.setup();
  const capacity = await screen.findByRole("spinbutton", { name: "模型任务并发上限（1～10）" });
  await user.clear(capacity); await user.type(capacity, "7");
  await user.click(screen.getByRole("tab", { name: "告警与通知" }));
  await screen.findByRole("checkbox", { name: "主动飞书告警" });
  const count = calls.filter((url) => url.endsWith("worker-scheduler/config")).length;
  await act(async () => { await client.invalidateQueries({ queryKey: ["worker-scheduler-config"] }); });
  expect(calls.filter((url) => url.endsWith("worker-scheduler/config"))).toHaveLength(count);
  await user.click(screen.getByRole("tab", { name: "运行与并发" }));
  expect(await screen.findByRole("spinbutton", { name: "模型任务并发上限（1～10）" })).toHaveValue(7);
  await user.click(screen.getByRole("button", { name: "刷新当前视图" }));
  await waitFor(() => expect(capacity).toHaveValue(7));
});

it("告警后台更新不重建编辑器，跨分区保留阈值草稿", async () => {
  const { client } = page("/operations?tab=alerts");
  const user = userEvent.setup();
  const threshold = await screen.findByRole("spinbutton", { name: "队列等待阈值（分钟）" });
  await user.clear(threshold); await user.type(threshold, "71");
  act(() => client.setQueryData(["alerts"], { config: { enabled: false, target_id: null, queue_minutes: 60 }, deliveries: [] }));
  expect(threshold).toHaveValue(71);
  await user.click(screen.getByRole("tab", { name: "运行与并发" }));
  await user.click(screen.getByRole("tab", { name: "告警与通知" }));
  expect(await screen.findByRole("spinbutton", { name: "队列等待阈值（分钟）" })).toHaveValue(71);
});

it("旧版未返回原始执行状态时不挪用有效结论或显示假零", async () => {
  const { execution_jobs: _, ...old } = snapshot;
  void _;
  page("/operations?tab=invalid", old);
  await screen.findByText(/历史评审待关注 5 项/);
  expect(screen.getByRole("tab", { name: "运行与并发" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getAllByText("未知", { selector: ".operations-number" })).toHaveLength(2);
});

it("监控读取失败有恢复入口，未知不冒充零或正常", async () => {
  page("/operations", new Error("合成监控读取失败"));
  expect(await screen.findByRole("alert")).toHaveTextContent("合成监控读取失败");
  expect(screen.getByRole("button", { name: "重新加载" })).toBeVisible();
  expect(screen.getAllByText("未知", { selector: ".operations-number" })).toHaveLength(3);
  expect(screen.queryByText(/历史评审待关注 0 项/)).toBeNull();
});
