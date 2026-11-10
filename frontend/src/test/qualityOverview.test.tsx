/** @description 质量计数、比例、旧接口降级、同源周桶和样本条件回归；使用合成响应。 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { expect, it, vi } from "vitest";

import type { EffectivenessSnapshot, ReviewQuality } from "../api/effectiveness";
import { DesignProvider } from "../app/DesignProvider";
import { QualityBreakdown } from "../pages/overview/QualityBreakdown";
import { QualityOverview } from "../pages/overview/QualityOverview";
import { QualitySamples } from "../pages/overview/QualitySamples";
import { QualityTrend } from "../pages/overview/QualityTrend";
import { qualityBuckets, qualityRatio } from "../pages/overview/qualityView";

const counts = { total: 10, helpful: 4, false_positive: 1, ignored: 0, unmarked: 5 };
const quality: ReviewQuality = { summary: counts, since: "2026-11-02 00:00:00", until: "2026-11-09 00:00:00", unavailable_sources: 0,
  trend: [{ ...counts, day: "2026-11-08" }], categories: [{ ...counts, name: "security" }], projects: [{ ...counts, name: "合成项目", id: 1 }] };
const data: EffectivenessSnapshot = { days: 7, quality, current_status_counts: { open: 5, fixed: 2, ignored: 3, merged: 1 },
  summary: { reviews: 4, failed_reviews: 0, generated: 20, published: 2, new_issues: 2, new_still_open: 1, fixed: 1, ignored: 1, open_now: 5, feedback_marked: 7, false_positive: 1 }, trend: [{ day: "2026-11-08", new: 2, fixed: 1 }], categories: [], projects: [] };

function Location() { return <output data-testid="location">{useLocation().search}</output>; }
function show(child: React.ReactNode, path = "/?repository_id=1&days=7") {
  return render(<DesignProvider><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={[path]}>{child}<Location /></MemoryRouter></QueryClientProvider></DesignProvider>);
}

it("并排柱纵轴依据单类最大值而非总量，数据表仍展示同源总发现", async () => {
  show(<QualityTrend quality={quality} days={7} />);
  expect(screen.getByRole("img", { name: /四类反馈按日期并排/ })).toHaveAccessibleName(/纵轴 0 至 8 条/);
  await userEvent.click(screen.getByRole("button", { name: "查看反馈数据" }));
  const rows = within(screen.getByRole("table", { name: "反馈价值数据（UTC）" })).getAllByRole("row");
  expect(within(rows[1]).getAllByRole("cell").map((cell) => cell.textContent)).toEqual(["2026-11-08", "4", "1", "0", "5", "10"]);
  expect(screen.queryByText("历史修复", { exact: true })).not.toBeInTheDocument();
});

it("首页只保留反馈与同集合处理进度，入口保留 UTC 窗口和项目", async () => {
  show(<QualityOverview data={data} days={7} repositoryId="1" />);
  expect(screen.queryByRole("radio", { name: "反馈价值" })).not.toBeInTheDocument();
  expect(screen.getByText("50%（5/10）")).toBeVisible();
  expect(screen.getByRole("link", { name: "已处理 5 条" })).toHaveAttribute("href", expect.stringContaining("handling=handled"));
  expect(screen.getByRole("link", { name: "待处理 5 条" })).toHaveAttribute("href", expect.stringContaining("handling=pending"));
  const helpful = screen.getByRole("link", { name: "查看有帮助 4 条发现" });
  expect(helpful.getAttribute("href")).toContain("/findings?");
  expect(helpful.getAttribute("href")).toContain("feedback=helpful");
  expect(helpful.getAttribute("href")).toContain("since=2026-11-02");
  expect(helpful.getAttribute("href")).toContain("repository_id=1");
  expect(screen.queryByText("当前问题 · 不限时间")).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "问题变化" })).not.toBeInTheDocument();
  await userEvent.click(screen.getByText("反馈统计口径"));
  await waitFor(() => expect(screen.getByText(/20%（1\/5）/)).toBeVisible());
  expect(screen.getByRole("region", { name: "反馈趋势图，可横向滚动" })).toBeVisible();
  expect(screen.queryByRole("button", { name: /展开反馈趋势|收起反馈趋势/ })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "查看反馈数据" }));
  expect(screen.getByRole("table", { name: "反馈价值数据（UTC）" })).toBeVisible();
});

it("旧接口明确缺失，不以历史处置补反馈计数", () => {
  show(<QualityOverview data={{ ...data, quality: undefined }} days={7} repositoryId="" />);
  expect(screen.getByText(/缺失不代表零反馈/)).toBeVisible();
  expect(screen.queryByRole("link", { name: /查看有帮助/ })).not.toBeInTheDocument();
  expect(screen.queryByText("问题状态")).not.toBeInTheDocument();
});

it("零样本、小样本与来源缺失明确呈现，不制造准确率", () => {
  expect(qualityRatio(0, 0)).toBe("—（0 样本）");
  expect(qualityRatio(0, 10)).toBe("0%（0/10）");
  expect(qualityRatio(1, 4, 5)).toBe("样本不足（1/4）");
  show(<QualityOverview data={{ ...data, quality: { ...quality, summary: { total: 10, helpful: 0, false_positive: 0, ignored: 2, unmarked: 8 }, unavailable_sources: 2 } }} days={7} repositoryId="" />);
  expect(screen.getByText("20%（2/10）")).toBeVisible();
  expect(screen.getByRole("alert")).toHaveTextContent("2 个来源记录待核实");
});

it("优化方向可以按项目切换，查看样本不丢失维度", async () => {
  show(<QualityBreakdown quality={quality} />);
  const table = screen.getByRole("region", { name: "优化方向" });
  expect(within(table).getByRole("link", { name: "查看样本" }).getAttribute("href")).toContain("category=security");
  await userEvent.click(within(table).getByText("按项目", { exact: true }));
  expect(within(table).getByText("合成项目")).toBeVisible();
  expect(within(table).getByRole("link", { name: "查看样本" }).getAttribute("href")).toContain("repository_id=1");
});

it("样本失败保留范围且可重试，清除仅影响样本筛选", async () => {
  let fail = true;
  const requests: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    requests.push(String(input));
    return new Response(JSON.stringify(fail ? { detail: "合成样本读取失败" } : { items: [], total: 0, page: 1, page_size: 10 }), { status: fail ? 503 : 200 });
  });
  show(<QualitySamples token="" days={7} repositoryId="1" />, "/?repository_id=1&days=7&sample_open=1&sample_category=security&sample_feedback=helpful&sample_since=2026-11-02%2000:00:00&sample_until=2026-11-09%2000:00:00");
  expect(await screen.findByRole("alert")).toHaveTextContent("合成样本读取失败");
  expect(requests[0]).toContain("repository_id=1");
  expect(requests[0]).toContain("category=security");
  expect(screen.getByTestId("location")).toHaveTextContent("sample_feedback=helpful");
  fail = false;
  await userEvent.click(screen.getByRole("button", { name: "重新加载" }));
  expect(await screen.findByText("当前条件没有发现样本")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "清除样本筛选" }));
  expect(screen.getByTestId("location")).toHaveTextContent("repository_id=1&days=7");
  expect(screen.getByTestId("location").textContent).not.toContain("sample_category");
});

it("质量周桶跨年保留边界并累加四类而非平均百分比", () => {
  const rows = Array.from({ length: 9 }, (_, index) => ({ total: index, helpful: index, false_positive: 0, ignored: 0, unmarked: 0, day: new Date(Date.UTC(2025, 11, 28 + index)).toISOString().slice(0, 10) }));
  const buckets = qualityBuckets(rows, 90);
  expect(buckets.map((row) => [row.start, row.end, row.total])).toEqual([["2025-12-28", "2026-01-03", 21], ["2026-01-04", "2026-01-05", 15]]);
  expect(buckets.every((row) => row.helpful + row.false_positive + row.ignored + row.unmarked === row.total)).toBe(true);
  expect(qualityBuckets([], 90)).toEqual([]);
});
