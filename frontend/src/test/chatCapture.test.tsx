/** @description 使用合成响应验证聊天收件箱的权限失败、健康提示、关联冲突与撤权版本，不读取真实聊天。 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type { ChatInbox } from "../api/chatCapture";
import { ChatCapturePanel } from "../pages/ChatCapturePanel";

const initial: ChatInbox = {
  bindings: [{ id: 1, thread_id: "synthetic", enabled: true, version: 3, since_ms: 1000,
    last_checked_at: null, last_success_at: null, last_error_code: "source_unavailable", last_message_ms: null, last_scan_count: 0 }],
  items: [{ id: 2, binding_id: 1, turn_id: "turn", message_id: "message", role: "user", classification: "pending", excerpt: "合成待核实线索",
    source_ms: 2000, improvement_id: null, version: 4, created_at: "2026-11-07" }],
  total: 1, pending: 1, page: 1, page_size: 25,
};

function panel() {
  render(<MemoryRouter><QueryClientProvider client={new QueryClient({ defaultOptions: {
    queries: { retry: false }, mutations: { retry: false },
  } })}><ChatCapturePanel token="" /></QueryClientProvider></MemoryRouter>);
  fireEvent.click(screen.getByText(/^聊天自动受理与待核实收件箱/));
}

describe("混合聊天记录", () => {
  it("失败和过期不伪装健康，暂停带版本；不展示已部署结论", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockImplementation(async (_url, options) => new Response(JSON.stringify(
      options?.method === "PUT" ? { status: "saved" } : initial,
    )));
    panel();
    expect(await screen.findByRole("alert")).toHaveTextContent("source_unavailable");
    fireEvent.click(screen.getByRole("button", { name: "暂停采集 #1" }));
    await waitFor(() => expect(fetch.mock.calls.some((call) => call[1]?.method === "PUT")).toBe(true));
    const call = fetch.mock.calls.find((entry) => entry[1]?.method === "PUT");
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ enabled: false, expected_version: 3 });
    expect(screen.getByText(/验证和部署仍以实际证据为准/)).toBeVisible();
  });

  it("关联冲突保留输入，提交来源版本且不覆盖正式事实", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockImplementation(async (_url, options) => options?.method === "POST"
      ? new Response(JSON.stringify({ detail: "线索已更新" }), { status: 409 })
      : new Response(JSON.stringify({ ...initial, bindings: [] })));
    panel();
    const input = await screen.findByLabelText("来源 #2 关联记录编号");
    fireEvent.change(input, { target: { value: "11" } });
    fireEvent.click(screen.getByRole("button", { name: "关联已有记录" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("输入已保留");
    expect(input).toHaveValue(11);
    const call = fetch.mock.calls.find((entry) => entry[1]?.method === "POST");
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ expected_version: 4, improvement_id: 11, promote: false });
  });

  it("未绑定显式提示，分页条数确实影响请求", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ ...initial, bindings: [], items: [], total: 0 })));
    panel();
    expect(await screen.findByText("尚未绑定会话，不会自动读取其他聊天。")).toBeVisible();
    fireEvent.change(screen.getByLabelText("每页条数"), { target: { value: "50" } });
    await waitFor(() => expect(fetch.mock.calls.some((call) => String(call[0]).includes("page_size=50"))).toBe(true));
  });

  it("权限查询失败不显示零消息或健康状态", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ detail: "仅管理员可查看" }), { status: 403 }));
    panel();
    expect(await screen.findByRole("alert")).toHaveTextContent("仅管理员可查看");
    expect(screen.queryByText(/尚无摄取记录/)).not.toBeInTheDocument();
  });
});
