/** @description 验证独立忽略的冻结目标、草稿、失败、权限展示与真实 Service 请求，不混写反馈。 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DesignProvider } from "../app/DesignProvider";
import { IssueStateActions } from "../pages/IssueStateActions";
import type { IssueStateActionsProps } from "../pages/IssueStateActions";
import { useFindingDisposition } from "../pages/useFindingDisposition";
import type { FindingDisposition } from "../pages/useFindingDisposition";

function renderActions(overrides: Partial<IssueStateActionsProps> = {}) {
  const onDisposition = vi.fn().mockResolvedValue({ updated: 1 });
  const props = { index: 3, issueId: 42, issueStatus: "open" as const, canSubmit: true, onDisposition, ...overrides };
  const result = render(<DesignProvider><IssueStateActions {...props} /></DesignProvider>);
  return { ...result, props, onDisposition };
}

describe("独立忽略", () => {
  it("先确认再提交，保留原反馈及冻结问题，不随轮询漂移", async () => {
    const { props, rerender, onDisposition } = renderActions();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /^已忽略$/ }));
    expect(onDisposition).not.toHaveBeenCalled();
    const dialog = within(screen.getByRole("dialog"));
    await user.type(dialog.getByLabelText("处理说明（选填）"), "已评估，暂不处理");
    rerender(<DesignProvider><IssueStateActions {...props} issueId={99} issueStatus="fixed" /></DesignProvider>);
    expect(screen.getByRole("dialog")).toHaveTextContent("跟进问题 #42");
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "确认忽略" }));
    await waitFor(() => expect(onDisposition).toHaveBeenCalledWith({ target: { id: 42, expected_status: "open" }, status: "ignored", note: "已评估，暂不处理" }));
    expect(screen.getAllByRole("button", { pressed: true })).toHaveLength(1);
  });

  it("取消不提交，失败保留说明且不乐观显示已忽略", async () => {
    const write = vi.fn().mockRejectedValue(new Error("状态已变化"));
    renderActions({ onDisposition: write });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /^已忽略$/ }));
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "取消" }));
    expect(write).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: /^已忽略$/ }));
    const dialog = within(screen.getByRole("dialog"));
    await user.type(dialog.getByLabelText("处理说明（选填）"), "保留此说明");
    await user.click(dialog.getByRole("button", { name: "确认忽略" }));
    expect(await dialog.findByRole("alert")).toHaveTextContent("状态已变化");
    expect(dialog.getByLabelText("处理说明（选填）")).toHaveValue("保留此说明");
    expect(screen.getByRole("button", { name: "已忽略" })).toHaveAttribute("aria-pressed", "false");
    expect(write).toHaveBeenCalledOnce();
  });

  it("保存时锁定重复提交和关闭，恢复不撤销误报反馈", async () => {
    let finish: (() => void) | undefined;
    const write = vi.fn<(input: FindingDisposition) => Promise<void>>(() => new Promise<void>((resolve) => { finish = resolve; }));
    renderActions({ issueStatus: "ignored", onDisposition: write });
    const user = userEvent.setup();
    expect(screen.getByRole("button", { name: "已忽略" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "已修复" })).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "待处理" }));
    const dialog = within(screen.getByRole("dialog"));
    await user.click(dialog.getByRole("button", { name: "确认恢复" }));
    expect(dialog.getByRole("button", { name: "确认恢复" })).toBeDisabled();
    expect(dialog.getByRole("button", { name: "取消" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "误报" })).toBeDisabled();
    await act(async () => finish?.());
    expect(write).toHaveBeenCalledOnce();
    expect(write.mock.calls[0][0]).toMatchObject({ target: { id: 42, expected_status: "ignored" }, status: "open" });
  });

  it.each([{ issueId: undefined }, { issueStatus: undefined }, { issueStatus: "merged" as const }, { canSubmit: false }, { onDisposition: undefined }])("不完整或不可编辑目标禁用忽略：%j", (overrides) => {
    renderActions(overrides);
    expect(screen.getByRole("button", { name: /^已忽略$/ })).toBeDisabled();
  });

  it("Service 只发显式处置 POST 并刷新共享问题及总览，不发反馈请求", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ status: "ignored", updated: 1, unchanged: 0 })));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const invalidate = vi.spyOn(client, "invalidateQueries");
    function Harness() {
      const mutation = useFindingDisposition("synthetic-token");
      return <IssueStateActions index={0} issueId={42} issueStatus="open" canSubmit={!mutation.isPending} onDisposition={(input) => mutation.mutateAsync(input)} />;
    }
    render(<QueryClientProvider client={client}><DesignProvider><Harness /></DesignProvider></QueryClientProvider>);
    await userEvent.click(screen.getByRole("button", { name: /^已忽略$/ }));
    await userEvent.click(screen.getByRole("button", { name: "确认忽略" }));
    await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: ["overview"] }));
    expect(fetch).toHaveBeenCalledOnce();
    expect(fetch.mock.calls[0][0]).toBe("/api/review-issues/batch-update");
    expect(fetch.mock.calls[0][1]?.method).toBe("POST");
    expect(JSON.parse(String(fetch.mock.calls[0][1]?.body))).toMatchObject({ targets: [{ id: 42, expected_status: "open" }], status: "ignored" });
    for (const key of ["job", "jobs", "review-issues", "review-issue", "review-effectiveness"]) expect(invalidate).toHaveBeenCalledWith({ queryKey: [key] });
  });
});
