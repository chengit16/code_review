/** @description 保护问题提交人列表、历史证据与缺失状态；只使用合成接口响应。 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";

import { ReviewIssuesPage } from "../pages/ReviewIssuesPage";

function renderIssues(canEdit: boolean, empty = false) {
  const items = ["合成作者乙", null, "   "].map((author, index) => ({
    id: index + 1, repository_id: 1, repository_name: "合成项目", status: "open",
    commit_author: author, path: "app.py", content: `合成发现 ${index + 1}`,
    severity: "high", category: null, occurrence_count: 2,
    first_seen_at: "2026-01-01", last_seen_at: "2026-01-02", merged_into_id: null,
  }));
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => {
    const path = String(url);
    if (path.startsWith("/api/review-issues?")) return new Response(JSON.stringify({
      items: empty ? [] : items, total: empty ? 0 : items.length, page_size: 25,
    }));
    if (path === "/api/review-issues/1") return new Response(JSON.stringify({
      ...items[0], occurrences: ["合成作者乙", "合成作者甲", null].map((author, index) => ({
        id: index + 1, job_id: index + 1, attempt_number: 1, mr_iid: 7,
        commit_sha: "a".repeat(40), commit_author: author, path: "app.py",
        recovery_id: index === 1 ? 7 : null, start_line: 4, created_at: "2026-01-01",
      })), events: [],
    }));
    return new Response("[]");
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<MemoryRouter initialEntries={["/issues"]}><QueryClientProvider client={client}>
    <ReviewIssuesPage token="" canEdit={canEdit} />
  </QueryClientProvider></MemoryRouter>);
}

it.each([true, false])("管理员或只读列表显示提交人与缺失状态（可编辑：%s）", async (canEdit) => {
  renderIssues(canEdit);
  await screen.findByRole("button", { name: "查看问题 1" });
  expect(screen.getByRole("columnheader", { name: "提交人" })).toBeVisible();
  const rows = screen.getAllByRole("row").slice(1);
  expect(within(rows[0]).getByRole("cell", { name: "合成作者乙" })).toBeVisible();
  expect(within(rows[1]).getByRole("cell", { name: "未记录" })).toBeVisible();
  expect(within(rows[2]).getByRole("cell", { name: "未记录" })).toBeVisible();
  expect(within(rows[0]).getAllByRole("cell")).toHaveLength(canEdit ? 9 : 8);
});

it("出现记录分别显示对应提交人，不把最新作者套用到历史提交", async () => {
  renderIssues(false);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "查看问题 1" }));
  const drawer = await screen.findByRole("dialog", { name: "问题 #1" });
  expect(await within(drawer).findByText("提交人：合成作者乙")).toBeVisible();
  expect(within(drawer).getByText("提交人：合成作者甲")).toBeVisible();
  expect(within(drawer).getByText("提交人：未记录")).toBeVisible();
  expect(within(drawer).getByRole("link", { name: /补审 #7（候选来源）/ })).toHaveAttribute("href", "/jobs/2");
  expect(within(drawer).getAllByRole("link", { name: /初审/ })).toHaveLength(2);
});

it.each([true, false])("空列表占满新增列后的表格（可编辑：%s）", async (canEdit) => {
  renderIssues(canEdit, true);
  const cell = await screen.findByRole("cell", { name: "当前筛选下没有问题" });
  expect(cell).toHaveAttribute("colspan", canEdit ? "9" : "8");
});
