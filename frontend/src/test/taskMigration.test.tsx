/** @description 任务迁移保护筛选集中提交、冻结编号、取消无写入和请求失败不重放；接口全部合成。 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ConfigProvider } from "antd";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";

import { DesignProvider } from "../app/DesignProvider";
import { TaskFilters } from "../pages/TaskFilters";
import { TaskSelectionBar } from "../pages/TaskSelectionBar";

it("未应用筛选不会检索，折叠后保留高级输入、UTC 时间与每页条数", async () => {
  const apply = vi.fn();
  const user = userEvent.setup();
  render(<DesignProvider><TaskFilters params={new URLSearchParams("page=3&page_size=50&view=attention&sha=abcd")}
    repositories={[]} onApply={apply} /></DesignProvider>);
  const branch = screen.getByLabelText("分支", { exact: true });
  await user.type(branch, "main");
  await user.type(screen.getByLabelText("起始时间", { exact: true }), "2026-01-01T08:00");
  await user.click(screen.getByText("更多筛选（提交、分支、时间）"));
  expect(apply).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "查询" }));
  const params = apply.mock.calls[0][0] as URLSearchParams;
  expect(params.get("sha")).toBe("abcd");
  expect(params.get("target_branch")).toBe("main");
  expect(params.get("page_size")).toBe("50");
  expect(params.get("view")).toBe("attention");
  expect(params.has("page")).toBe(false);
  expect(params.get("since")).toBe(new Date("2026-01-01T08:00").toISOString());
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
