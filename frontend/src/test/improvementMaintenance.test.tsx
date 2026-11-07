/** @description 只模拟维护 API，验证实际执行事实、策略保存、冲突草稿及失败不伪装成功。 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { MaintenanceStatus } from "../api/improvementMaintenance";
import { ImprovementMaintenancePanel } from "../pages/ImprovementMaintenancePanel";

const initial: MaintenanceStatus = {
  enabled: false, archive_after_days: 30, version: 1, source_configured: true,
  last_checked_at: null, last_success_at: null, last_error_code: "",
  last_result: { sync: { created: 0, updated: 0, unchanged: 0, conflicts: [] },
    archived_records: 0, archived_themes: 0 }, candidate_records: 2, candidate_themes: 1,
};

function panel() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: {
    queries: { retry: false }, mutations: { retry: false },
  } })}><ImprovementMaintenancePanel token="" /></QueryClientProvider>);
  fireEvent.click(screen.getByText(/^自动归档与台账同步/));
}

describe("自动维护", () => {
  it("保存成功只表明策略保存，不声称归档已完成", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockImplementation(async (_url, options) => new Response(JSON.stringify(
      options?.method === "PUT" ? { ...initial, enabled: true, version: 2 } : initial,
    )));
    panel();
    await screen.findByLabelText("启用自动归档");
    expect(screen.getByText(/当前候选：问题 2 条、主题 1 个/)).toBeVisible();
    fireEvent.click(screen.getByLabelText("启用自动归档"));
    fireEvent.click(screen.getByRole("button", { name: "保存归档策略" }));
    expect(await screen.findByText(/策略已保存，后台下轮执行/)).toBeVisible();
    const call = fetch.mock.calls.find((item) => item[1]?.method === "PUT");
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ enabled: true, archive_after_days: 30, expected_version: 1 });
  });

  it("版本冲突保留天数和开关草稿，不显示保存成功", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (_url, options) => options?.method === "PUT"
      ? new Response(JSON.stringify({ detail: "策略版本已更新" }), { status: 409 })
      : new Response(JSON.stringify(initial)));
    panel();
    await screen.findByLabelText("启用自动归档");
    fireEvent.change(screen.getByLabelText("连续无更新天数"), { target: { value: "60" } });
    fireEvent.click(screen.getByLabelText("启用自动归档"));
    fireEvent.click(screen.getByRole("button", { name: "保存归档策略" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("策略版本已更新");
    expect(screen.getByLabelText("连续无更新天数")).toHaveValue(60);
    expect(screen.getByLabelText("启用自动归档")).toBeChecked();
    expect(screen.queryByText(/策略已保存/)).not.toBeInTheDocument();
  });

  it("同步冲突显示来源编号及整轮跳过，不把旧成功时间描述成本轮成功", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ ...initial,
      last_error_code: "source_conflict", last_result: { ...initial.last_result,
        sync: { ...initial.last_result.sync, conflicts: ["PI-20261106-001"] } },
    })));
    panel();
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("自动归档已跳过本轮"));
    expect(screen.getByText(/待核对来源：PI-20261106-001/)).toBeVisible();
  });

  it("状态请求失败不显示默认关闭或零候选", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ detail: "服务不可用" }), { status: 503 }));
    panel();
    expect(await screen.findByRole("alert")).toHaveTextContent("服务不可用");
    expect(screen.queryByLabelText("启用自动归档")).not.toBeInTheDocument();
    expect(screen.queryByText(/当前候选/)).not.toBeInTheDocument();
  });
});
