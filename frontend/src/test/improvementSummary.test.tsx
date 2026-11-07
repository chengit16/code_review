/** @description 验证复盘口径、失败恢复、URL 条件及异步隔离；只使用合成 API 投影。 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, useLocation, useNavigate } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import * as api from "../api/improvementSummary";
import type { ImprovementDistribution, ImprovementSummary } from "../api/improvementSummary";
import { ImprovementSummaryPanel } from "../pages/ImprovementSummaryPanel";
import { categoryLabels, codeLabels, deploymentLabels, kindLabels, progressLabels, verificationLabels } from "../pages/improvementFields";

function zeros(labels: Record<string, string>) { return Object.fromEntries(Object.keys(labels).map((key) => [key, 0])); }
function distribution(): ImprovementDistribution {
  return { total: 0, by_status: zeros(progressLabels), by_category: zeros(categoryLabels),
    by_code_state: zeros(codeLabels), by_verification_state: zeros(verificationLabels), by_deployment_state: zeros(deploymentLabels) };
}
function summary(): ImprovementSummary {
  const empty = () => ({ total: 0, items: [] });
  return { archived_records: 0, archived_themes: 0, generated_at: "2026-11-06T00:00:00Z", timezone: "Asia/Shanghai", start_date: "2026-11-01", end_date: "2026-11-03", category: null,
    records: { ...distribution(), by_kind: zeros(kindLabels), linked_records: 0 },
    themes: { total: 0, by_status: { planned: 0, active: 0, paused: 0, completed: 0, deferred: 0 }, by_category: zeros(categoryLabels),
      phases: { ...distribution(), by_status: { planned: 0, active: 0, completed: 0, deferred: 0 } } },
    activity: [{ date: "2026-11-01", records_created: 0, record_updates: 0, themes_created: 0, theme_updates: 0 }],
    unresolved: empty(), verification_attention: empty(), deployment_pending: empty(), unfinished_themes: empty() };
}
function panel(url = "/improvements?view=summary") {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={[url]}><ImprovementSummaryPanel token="" /><LocationProbe /></MemoryRouter></QueryClientProvider>);
}
function LocationProbe() {
  const location = useLocation();
  const navigate = useNavigate();
  return <><output aria-label="当前测试地址">{location.search}</output><button type="button" onClick={() => void navigate(-1)}>测试返回</button></>;
}

describe("平台复盘汇总", () => {
  it("空样本占比显示缺失，不以零统计宣称没有问题", async () => {
    vi.spyOn(api, "getImprovementSummary").mockResolvedValue(summary());
    panel();
    await screen.findByText("当前分类暂无台账或主题，统计为零不表示项目没有问题。");
    expect(within(screen.getByRole("article", { name: "已解决占比" })).getByText("—")).toBeVisible();
    expect(screen.getByText(/日期只影响活动趋势/)).toBeVisible();
    expect(screen.queryByText(/NaN|Infinity/)).not.toBeInTheDocument();
  });

  it("本地通过与部署独立展示，分类明细跳转只携带对应累计条件", async () => {
    const result = summary();
    result.category = "stability";
    result.records.total = 1;
    result.records.by_status.resolved = 1;
    result.records.by_verification_state.passed = 1;
    result.records.by_deployment_state.not_deployed = 1;
    result.deployment_pending = { total: 1, items: [{ id: 7, title: "待部署的合成事项", status: "resolved", archived_at: null, updated_at: result.generated_at }] };
    vi.spyOn(api, "getImprovementSummary").mockResolvedValue(result);
    panel("/improvements?view=summary&summary_category=stability&summary_start_date=2026-11-01");
    await screen.findByRole("heading", { name: "部署待确认（1）" });
    expect(within(screen.getByRole("article", { name: "已解决占比" })).getByText("100.0%")).toBeVisible();
    expect(within(screen.getByRole("region", { name: /^本地验证$/ })).getByText("本地验证通过")).toBeVisible();
    expect(within(screen.getByRole("region", { name: /^部署生效$/ })).getByText("未部署")).toBeVisible();
    expect(screen.getByRole("link", { name: /^已解决$/ })).toHaveAttribute("href", "/improvements?archive=all&category=stability&status=resolved");
    expect(screen.getByRole("link", { name: /待部署的合成事项/ })).toHaveAttribute("href", "/improvements/7");
  });

  it("日期应用保留其他视图条件，刷新或返回可恢复已应用 URL", async () => {
    const read = vi.spyOn(api, "getImprovementSummary").mockResolvedValue(summary());
    panel("/improvements?view=summary&q=保留问题筛选&theme_page=2");
    await screen.findByRole("article", { name: "当前台账记录" });
    fireEvent.change(screen.getByLabelText("活动开始日期"), { target: { value: "2026-11-01" } });
    fireEvent.change(screen.getByLabelText("活动结束日期"), { target: { value: "2026-11-03" } });
    fireEvent.click(screen.getByRole("button", { name: "应用复盘条件" }));
    await waitFor(() => expect(screen.getByLabelText("当前测试地址")).toHaveTextContent("summary_start_date=2026-11-01"));
    const params = new URLSearchParams(screen.getByLabelText("当前测试地址").textContent ?? "");
    expect(params.get("q")).toBe("保留问题筛选");
    expect(params.get("theme_page")).toBe("2");
    await waitFor(() => expect(read.mock.calls.at(-1)?.[1].get("end_date")).toBe("2026-11-03"));
    fireEvent.click(screen.getByRole("button", { name: "测试返回" }));
    expect(screen.getByLabelText("活动开始日期")).toHaveValue("");
  });

  it("快速切换日期后，旧请求晚到不能覆盖新统计", async () => {
    let resolveOld: (value: ImprovementSummary) => void = () => undefined;
    const old = new Promise<ImprovementSummary>((resolve) => { resolveOld = resolve; });
    const fresh = summary();
    fresh.records.total = 5;
    vi.spyOn(api, "getImprovementSummary").mockImplementation((_token, params) => params.has("start_date") ? Promise.resolve(fresh) : old);
    panel();
    fireEvent.change(screen.getByLabelText("活动开始日期"), { target: { value: "2026-11-01" } });
    fireEvent.click(screen.getByRole("button", { name: "应用复盘条件" }));
    await waitFor(() => expect(within(screen.getByRole("article", { name: "当前台账记录" })).getByText("5")).toBeVisible());
    await act(async () => resolveOld(summary()));
    expect(within(screen.getByRole("article", { name: "当前台账记录" })).getByText("5")).toBeVisible();
  });

  it("查询或刷新失败不伪装为零或继续展示旧统计，重试仅重新读取", async () => {
    const read = vi.spyOn(api, "getImprovementSummary").mockResolvedValueOnce(summary()).mockRejectedValueOnce(new Error("合成汇总失败")).mockResolvedValue(summary());
    panel();
    await screen.findByRole("article", { name: "当前台账记录" });
    fireEvent.click(screen.getByRole("button", { name: "刷新统计" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("合成汇总失败");
    expect(screen.queryByRole("article", { name: "当前台账记录" })).not.toBeInTheDocument();
    expect(screen.queryByText(/当前分类暂无台账/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "重新加载" }));
    await screen.findByRole("article", { name: "当前台账记录" });
    expect(read).toHaveBeenCalledTimes(3);
  });

  it("条件尚未提交时也可以重置草稿，不残留未应用日期", async () => {
    vi.spyOn(api, "getImprovementSummary").mockResolvedValue(summary());
    panel();
    await screen.findByRole("article", { name: "当前台账记录" });
    fireEvent.change(screen.getByLabelText("活动开始日期"), { target: { value: "2026-11-01" } });
    fireEvent.click(screen.getByRole("button", { name: "重置条件" }));
    expect(screen.getByLabelText("活动开始日期")).toHaveValue("");
  });
});
