/** @description 任务迁移保护筛选集中提交、冻结编号、取消无写入和请求失败不重放；接口全部合成。 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConfigProvider } from "antd";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";

import { DesignProvider } from "../app/DesignProvider";
import { TaskFilters } from "../pages/TaskFilters";
import { TaskSelectionBar } from "../pages/TaskSelectionBar";

it("单日筛选集中提交且包含整天，旧链接条件与每页条数保留", async () => {
  const apply = vi.fn();
  const user = userEvent.setup();
  render(<DesignProvider><TaskFilters params={new URLSearchParams("page=3&page_size=50&view=attention&issue_state=open&sha=abcd")}
    repositories={[]} onApply={apply} /></DesignProvider>);
  expect(screen.queryByLabelText("分支", { exact: true })).not.toBeInTheDocument();
  expect(screen.queryByLabelText("提交 SHA", { exact: true })).not.toBeInTheDocument();
  await user.type(screen.getByLabelText("创建日期", { exact: true }), "2026-01-01");
  await user.tab();
  expect(screen.queryByText(/更多筛选/)).not.toBeInTheDocument();
  expect(apply).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "查询" }));
  const params = apply.mock.calls[0][0] as URLSearchParams;
  expect(params.get("sha")).toBe("abcd");
  expect(params.get("page_size")).toBe("50");
  expect(params.get("view")).toBe("attention");
  expect(params.get("issue_state")).toBe("open");
  expect(params.has("page")).toBe(false);
  expect(params.get("since")).toBe(new Date(2026, 0, 1).toISOString());
  expect(params.get("until")).toBe(new Date(2026, 0, 1, 23, 59, 59, 999).toISOString());
});

it("旧范围未经修改继续生效，清空筛选仅保留每页条数", async () => {
  const apply = vi.fn();
  const user = userEvent.setup();
  const original = new URLSearchParams("page_size=50&page=3&sha=abcd&target_branch=main&notification_failed=true&since=2026-11-01T00:00:00Z&until=2026-11-03T23:59:59Z");
  render(<DesignProvider><TaskFilters params={original} repositories={[]} onApply={apply} /></DesignProvider>);
  expect(screen.getByLabelText("创建日期", { exact: true })).toHaveValue("");
  await user.click(screen.getByRole("button", { name: "查询" }));
  const params = apply.mock.calls[0][0] as URLSearchParams;
  expect(params.get("since")).toBe(original.get("since"));
  expect(params.get("until")).toBe(original.get("until"));
  expect(params.get("notification_failed")).toBe("true");
  expect(params.get("target_branch")).toBe("main");
  expect(params.has("page")).toBe(false);
  await user.click(screen.getByRole("button", { name: "清空筛选" }));
  expect((apply.mock.calls[1][0] as URLSearchParams).toString()).toBe("page_size=50");
});

it("打开后外部选择变化不改变冻结编号，网络失败不自动重试", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ detail: "合成网络边界失败" }), { status: 502 }));
  const user = userEvent.setup();
  const accepted = vi.fn();
  const pending = vi.fn();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: 3 } } });
  function node(ids: number[]) {
    // JSDOM 不执行真实布局动画；只在此测试关闭动效，焦点与可见性另由浏览器验收。
    return <ConfigProvider theme={{ token: { motion: false } }}><DesignProvider><QueryClientProvider client={client}><MemoryRouter><TaskSelectionBar token="" ids={ids} disabled={false}
      onClear={() => {}} onAccepted={accepted} onPendingChange={pending} /></MemoryRouter></QueryClientProvider></DesignProvider></ConfigProvider>;
  }
  const view = render(node([901]));
  await user.click(screen.getByRole("button", { name: "重审所选任务" }));
  expect(fetch).not.toHaveBeenCalled();
  view.rerender(node([902]));
  await waitFor(() => expect(screen.getByText("#901")).toBeVisible());
  await user.click(screen.getByRole("button", { name: "确认重审" }));
  expect(await screen.findByText(/所选任务已保留，请先核对是否已入队/)).toBeVisible();
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(JSON.parse(fetch.mock.calls[0][1]?.body as string)).toEqual({ ids: [901] });
  expect(accepted).not.toHaveBeenCalled();
  await waitFor(() => expect(pending).toHaveBeenLastCalledWith(false));
});
