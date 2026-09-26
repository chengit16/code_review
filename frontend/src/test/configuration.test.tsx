/** @description 保护配置编辑冲突时的草稿，以及部分评审的真实状态。 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { apiRequest } from "../api/client";
import { FeishuHooksPage } from "../pages/FeishuHooksPage";
import { FindingsPanel } from "../pages/FindingsPanel";
import { ModelUsage } from "../pages/ModelUsage";
import { Status } from "../ui/Status";

describe("配置与状态", () => {
  it("保存冲突保留草稿，可继续编辑", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (_url, options) =>
      new Response(JSON.stringify(options?.method === "POST" ? { detail: "配置冲突" } : []),
        { status: options?.method === "POST" ? 409 : 200 }),
    );
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={queryClient}><FeishuHooksPage token="" /></QueryClientProvider>);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "新增飞书配置" }));
    await user.type(screen.getByLabelText("配置名称"), "测试通知");
    await user.type(screen.getByLabelText("Webhook URL"), "https://open.feishu.cn/open-apis/bot/v2/hook/test");
    await user.click(screen.getByRole("button", { name: /^保存$/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("配置冲突");
    expect(screen.getByLabelText("配置名称")).toHaveValue("测试通知");
  });
  it("部分覆盖不显示完成", () => {
    render(<Status value="partial" />);
    expect(screen.getByText("部分完成")).toBeVisible();
    expect(screen.queryByText("已完成")).not.toBeInTheDocument();
  });
  it("请求失败保留状态与服务端原因", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ detail: "请先停止任务" }), { status: 409 }));
    await expect(apiRequest("", "/api/test")).rejects.toMatchObject({ status: 409, message: "请先停止任务" });
  });
  it("筛选后仍以原始发现索引提交反馈", async () => {
    const onFeedback = vi.fn();
    render(<FindingsPanel comments={[
      { path: "a.py", content: "低危", severity: "low" },
      { path: "b.py", content: "高危", severity: "high" },
    ]} feedback={{}} status="complete" coverageWaived={false} pending={false} onFeedback={onFeedback} />);
    const user = userEvent.setup();
    await user.click(within(screen.getByRole("group", { name: "发现 2 的反馈" })).getByRole("button", { name: "有帮助" }));
    expect(onFeedback).toHaveBeenCalledWith(1, "helpful");
  });
  it("用量与费用分别显示，缺失数据不推断金额", () => {
    const { rerender } = render(<ModelUsage result={{
      usage: { input_tokens: 500000, output_tokens: 250000, total_tokens: 750000 },
      estimated_cost: { currency: "CNY", input: "1", output: "2", total: "3" },
    }} />);
    expect(screen.getByText("500,000")).toBeVisible();
    expect(screen.getByText("250,000")).toBeVisible();
    expect(screen.getByText("¥3.0000")).toBeVisible();
    rerender(<ModelUsage result={{ usage: { total_tokens: 99 }, estimated_cost: null }} />);
    expect(screen.getByText("99")).toBeVisible();
    expect(screen.getAllByText("未提供", { selector: "strong" })).toHaveLength(3);
    expect(screen.queryByText("¥3.0000")).not.toBeInTheDocument();
    rerender(<ModelUsage result={{
      usage: { input_tokens: 1, output_tokens: 0 },
      estimated_cost: { currency: "CNY", input: "0.0000001", output: "0", total: "0.0000001" },
    }} />);
    expect(screen.getByText("<¥0.000001")).toBeVisible();
  });
});
