/** @description 概览可信状态与刷新回归；仅使用合成响应，不连接业务服务。 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";

import { DesignProvider } from "../app/DesignProvider";
import { OverviewPage } from "../pages/OverviewPage";

const overview = { summary: { repositories: 1, queued: 0, running: 0, complete: 2, attention: 0, historical_failed: 1, notification_failed: 0, total: 3 }, todo: { events_attention: 0, premerge_failed: 0, premerge_partial: 0 }, recent: [] };
function setup(canEdit = false, initialFailure = false) {
  let failing = initialFailure;
  let dataFailure = false;
  let release: (() => void) | undefined;
  let delay: Promise<void> | undefined;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const path = String(input);
    if (path === "/api/health") {
      await delay;
      return new Response(JSON.stringify(failing ? { detail: "合成读取失败" } : { status: "ok", worker: "stopped" }), { status: failing ? 503 : 200 });
    }
    if (path === "/api/overview") return new Response(JSON.stringify(dataFailure ? { detail: "合成概览失败" } : overview), { status: dataFailure ? 503 : 200 });
    if (path === "/api/repositories") return new Response("[]");
    return new Response(JSON.stringify(dataFailure ? { detail: "合成效果失败" } : { days: 30, summary: { reviews: 0, failed_reviews: 0, new_issues: 0, fixed: 0, generated: 0, published: 0, new_still_open: 0, open_now: 0, ignored: 0, feedback_marked: 0, false_positive: 0 }, trend: [{ day: "2026-11-08", new: 2, fixed: 1 }], categories: [], projects: [] }), { status: dataFailure ? 503 : 200 });
  });
  render(<DesignProvider><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><OverviewPage token="" canEdit={canEdit} /></MemoryRouter></QueryClientProvider></DesignProvider>);
  return { fail: () => { failing = true; }, failData: () => { dataFailure = true; }, delay: () => { delay = new Promise<void>((resolve) => { release = resolve; }); }, release: () => release?.() };
}

it("首次读取不以未知健康和未返回计数伪装零态", async () => {
  setup();
  expect(screen.getByText(/Worker 正在检测/)).toBeVisible();
  expect(screen.queryByRole("heading", { name: "当前工作" })).not.toBeInTheDocument();
  await screen.findByRole("heading", { name: "当前工作" });
});

it("健康首次失败无缓存时明确无检测记录，其他资源正常展示", async () => {
  setup(false, true);
  expect(await screen.findByText(/尚无成功检测记录/)).toBeVisible();
  expect(screen.queryByText(/Worker 未运行，队列可能等待处理/)).not.toBeInTheDocument();
  expect(await screen.findByRole("heading", { name: "最近评审" })).toBeVisible();
});

it("概览与效果刷新失败分别保留旧数据，不更新它们的成功读取时间", async () => {
  const control = setup();
  await screen.findByRole("heading", { name: "当前工作" });
  await screen.findByRole("button", { name: "查看趋势数据" });
  const dataRead = document.querySelectorAll(".overview-read")[1]?.textContent;
  control.failData();
  await userEvent.click(screen.getByRole("button", { name: "刷新概览" }));
  expect(await screen.findByText(/运行数据刷新失败/)).toBeVisible();
  expect(await screen.findByText(/效果统计刷新失败/)).toBeVisible();
  expect(await screen.findByText(/部分读取失败/)).toBeVisible();
  expect(document.querySelectorAll(".overview-read")[1]?.textContent).toBe(dataRead);
  expect(screen.getByRole("heading", { name: "最近评审" })).toBeVisible();
});

it("健康缓存失败后不再确认停止，独立成功数据保留且读者不显示管理入口", async () => {
  const control = setup();
  expect(await screen.findByText(/Worker 未运行，队列可能等待处理/)).toBeVisible();
  expect(screen.queryByRole("link", { name: "查看运行监控" })).not.toBeInTheDocument();
  control.fail();
  await userEvent.click(screen.getByRole("button", { name: "刷新概览" }));
  expect(await screen.findByText(/暂时无法确认 Worker 当前状态/)).toBeVisible();
  expect(screen.queryByText(/Worker 未运行，队列可能等待处理/)).not.toBeInTheDocument();
  expect(await screen.findByText(/部分读取失败/)).toBeVisible();
  expect(screen.getByRole("heading", { name: "最近评审" })).toBeVisible();
  expect(screen.getByText("当前服务暂不提供汇总")).toBeVisible();
});

it("手动刷新延迟时禁止重复请求，完成后解锁并保留成功读取时间", async () => {
  const control = setup(true);
  await screen.findByRole("link", { name: "查看运行监控" });
  control.delay();
  const button = screen.getByRole("button", { name: "刷新概览" });
  await userEvent.click(button);
  expect(button).toBeDisabled();
  control.release();
  await waitFor(() => expect(button).not.toBeDisabled());
  expect(await screen.findByText("概览读取完成")).toBeVisible();
  expect(screen.getAllByText(/成功读取于/).length).toBeGreaterThanOrEqual(3);
});

it("趋势表默认折叠，键盘可展开读取与图表同源的精确数据", async () => {
  setup();
  const button = await screen.findByRole("button", { name: "查看趋势数据" });
  expect(button).toHaveAttribute("aria-expanded", "false");
  button.focus();
  await userEvent.keyboard("{Enter}");
  expect(button).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("table", { name: "问题变化数据（UTC）" })).toBeVisible();
  expect(screen.getByRole("cell", { name: "2026-11-08" })).toBeVisible();
});

it("周桶跨年与末周保留真实边界，零值不丢失", async () => {
  const { trendBuckets } = await import("../pages/overview/IssueTrend");
  const rows = Array.from({ length: 9 }, (_, index) => ({ day: new Date(Date.UTC(2025, 11, 28 + index)).toISOString().slice(0, 10), new: index, fixed: 0 }));
  expect(trendBuckets(rows, 90)).toEqual([
    { start: "2025-12-28", end: "2026-01-03", new: 21, fixed: 0 },
    { start: "2026-01-04", end: "2026-01-05", new: 15, fixed: 0 },
  ]);
  expect(trendBuckets(rows, 7)).toHaveLength(9);
  expect(trendBuckets([], 90)).toEqual([]);
});
