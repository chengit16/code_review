/** @description 保护当前页选择范围、批量确认、冲突草稿和只读边界；网络仅返回合成问题。 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ReviewIssuesPage } from "../pages/ReviewIssuesPage";

function renderIssues(canEdit = true, conflict = false) {
  const request = vi.spyOn(globalThis, "fetch").mockImplementation(async (url, options) => {
    const path = String(url);
    if (options?.method === "POST") return new Response(JSON.stringify(conflict
      ? { detail: "问题状态已变化，本次未更新" }
      : { status: "ignored", updated: 2, unchanged: 0 }), { status: conflict ? 409 : 200 });
    const ids = path.includes("page=2") ? [3] : [1, 2];
    const items = ids.map((id) => ({ id, repository_id: 1, repository_name: "合成项目", status: "open",
      path: `src/${id}.py`, content: "合成发现", severity: "high", category: null,
      first_seen_at: "2026-01-01", last_seen_at: "2026-01-01", closed_at: null,
      occurrence_count: 1, merged_into_id: null }));
    return new Response(JSON.stringify(path.startsWith("/api/review-issues?") ? { items, total: 30, page_size: 25 } : []));
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<MemoryRouter initialEntries={["/issues"]}><QueryClientProvider client={queryClient}>
    <ReviewIssuesPage token="" canEdit={canEdit} />
  </QueryClientProvider></MemoryRouter>);
  return request;
}

describe("问题批量处理", () => {
  it("全选仅提交本页显式编号、状态快照和统一说明，成功清空选择", async () => {
    const request = renderIssues();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();
    await screen.findByRole("checkbox", { name: "选择问题 1" });
    await user.click(screen.getByRole("checkbox", { name: "全选当前页" }));
    await user.type(screen.getByLabelText("批量处理说明"), "统一核查：非缺陷");
    await user.click(screen.getByRole("button", { name: "批量标记已忽略" }));
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining("所选 2 条问题"));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("更新 2 条"));
    const post = request.mock.calls.find(([, options]) => options?.method === "POST");
    expect(post?.[0]).toBe("/api/review-issues/batch-update");
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({
      targets: [{ id: 1, expected_status: "open" }, { id: 2, expected_status: "open" }],
      status: "ignored", note: "统一核查：非缺陷",
    });
    expect(screen.getByLabelText("批量处理说明")).toHaveValue("");
    expect(screen.getByRole("checkbox", { name: "选择问题 1" })).not.toBeChecked();
  });

  it("取消确认不提交，勾选和说明保留", async () => {
    const request = renderIssues();
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("checkbox", { name: "选择问题 1" }));
    await user.type(screen.getByLabelText("批量处理说明"), "核查说明");
    await user.click(screen.getByRole("button", { name: "批量标记已修复" }));
    expect(request.mock.calls.filter(([, options]) => options?.method === "POST")).toHaveLength(0);
    expect(screen.getByRole("checkbox", { name: "选择问题 1" })).toBeChecked();
    expect(screen.getByLabelText("批量处理说明")).toHaveValue("核查说明");
  });

  it("409 冲突保留勾选和说明，刷新清除旧快照但保留说明", async () => {
    renderIssues(true, true);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("checkbox", { name: "选择问题 1" }));
    await user.type(screen.getByLabelText("批量处理说明"), "保留说明");
    await user.click(screen.getByRole("button", { name: "批量标记已忽略" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("状态已变化");
    expect(screen.getByRole("checkbox", { name: "选择问题 1" })).toBeChecked();
    expect(screen.getByLabelText("批量处理说明")).toHaveValue("保留说明");
    await user.click(screen.getByRole("button", { name: "刷新问题" }));
    expect(screen.getByRole("checkbox", { name: "选择问题 1" })).not.toBeChecked();
    expect(screen.getByLabelText("批量处理说明")).toHaveValue("保留说明");
  });

  it("换页清空选择，回到原页不会复活旧勾选", async () => {
    renderIssues();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("checkbox", { name: "选择问题 1" }));
    await user.click(screen.getByRole("button", { name: "下一页" }));
    expect(await screen.findByRole("checkbox", { name: "选择问题 3" })).not.toBeChecked();
    expect(screen.getByRole("button", { name: "批量标记已修复" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "上一页" }));
    expect(await screen.findByRole("checkbox", { name: "选择问题 1" })).not.toBeChecked();
  });

  it("只读账号没有选择框和批量动作", async () => {
    renderIssues(false);
    await screen.findByRole("button", { name: "查看问题 1" });
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "批量处理问题" })).not.toBeInTheDocument();
  });
});
