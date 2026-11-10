/** @description 当前发现主流程：服务端筛选、单项冻结版本、批量部分失败和只读权限；使用合成响应。 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";

import { DesignProvider } from "../app/DesignProvider";
import { ReviewFindingsPage } from "../pages/ReviewFindingsPage";

const row = { finding_id: "j1:a2:c0", job_id: 1, repository_id: 1, repository_name: "合成项目", source_attempt: 2, revision: 3, recovery_id: null, comment_index: 0, generated_at: "2026-11-09 00:00:00", category: "security", severity: "high", path: "src/main.py", excerpt: "检查授权边界", issue_id: 1, issue_status: "fixed", feedback: "unmarked", handling: "pending", commit_author: "合成提交人" };
function setup(canEdit = true, path = "/findings") {
  const requests: Array<{ path: string; body?: unknown }> = [];
  let listReads = 0;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    requests.push({ path: url, body: typeof init?.body === "string" ? JSON.parse(init.body) : undefined });
    if (url.includes("/batch-feedback")) return new Response(JSON.stringify({ updated: 1, results: [{ finding_id: row.finding_id, status: "updated" }, { finding_id: "j2:a2:c0", status: "conflict", code: "feedback_version_changed" }] }));
    if (url.includes("/finding-feedback/")) return new Response(JSON.stringify({ detail: { code: "feedback_version_changed" } }), { status: 409 });
    if (url.startsWith("/api/review-findings/")) return new Response(JSON.stringify({ ...row, content: "问题描述：检查授权边界\n修复建议：补充授权检查", start_line: 4 }));
    if (url.startsWith("/api/review-findings?")) {
      const revision = listReads++ ? 4 : 3;
      return new Response(JSON.stringify({ items: [{ ...row, revision }, { ...row, revision, finding_id: "j2:a2:c0", job_id: 2, excerpt: "检查第二条边界" }], total: 2, page: 1, page_size: 25 }));
    }
    return new Response(JSON.stringify([{ id: 1, name: "合成项目" }]));
  });
  render(<DesignProvider><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}><MemoryRouter initialEntries={[path]}><ReviewFindingsPage token="" canEdit={canEdit} /></MemoryRouter></QueryClientProvider></DesignProvider>);
  return requests;
}

it("默认待处理在服务端筛选，显式窗口和反馈沿用地址，不映射历史问题修复状态", async () => {
  const requests = setup(false, "/findings?handling=all&feedback=ignored&since=2026-11-01+00%3A00%3A00&until=2026-11-09+00%3A00%3A00");
  await screen.findByText("共 2 条发现");
  expect(requests.find((item) => item.path.startsWith("/api/review-findings?"))?.path).toContain("feedback=ignored");
  expect(requests[0].path).toContain("since=2026-11-01");
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  expect(screen.queryByText("已修复")).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "检查授权边界" }));
  expect(await screen.findByText("补充授权检查")).toBeVisible();
  expect(screen.queryByRole("button", { name: "有帮助" })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: /原问题 #1/ })).toHaveAttribute("href", "/issues?issue=1&status=all");
});

it("单项反馈冻结主身份及版本，409 保留输入并禁用重复提交直到显式核对", async () => {
  const requests = setup();
  await userEvent.click(await screen.findByRole("button", { name: "检查授权边界" }));
  const helpful = await screen.findByRole("button", { name: "有帮助" });
  await userEvent.click(helpful);
  expect(await screen.findByText(/操作目标和版本已保留/)).toBeVisible();
  expect(requests.find((item) => item.path.includes("/finding-feedback/"))).toEqual({ path: "/api/jobs/1/finding-feedback/j1%3Aa2%3Ac0", body: { source_attempt: 2, revision: 3, verdict: "helpful" } });
  expect(helpful).toBeDisabled();
  expect(requests.filter((item) => item.path.includes("/finding-feedback/"))).toHaveLength(1);
  await userEvent.click(screen.getByRole("button", { name: "刷新并重新核对" }));
  await waitFor(() => expect(helpful).toBeEnabled());
});

it("批量确认显示冻结目标，成功移除选择，冲突项保留旧版本等待人工重新勾选", async () => {
  const requests = setup();
  await screen.findByText("共 2 条发现");
  const rows = screen.getAllByRole("row");
  await userEvent.click(within(rows[1]).getByRole("checkbox"));
  await userEvent.click(within(rows[2]).getByRole("checkbox"));
  await userEvent.click(screen.getByRole("button", { name: "批量反馈" }));
  const dialog = await screen.findByRole("dialog");
  expect(dialog).toHaveTextContent("j1:a2:c0");
  expect(dialog).toHaveTextContent("j2:a2:c0");
  expect(dialog).toHaveTextContent("版本 2/3");
  await userEvent.click(within(dialog).getByRole("button", { name: "确认反馈" }));
  expect(await screen.findByText("批量反馈成功 1 条，失败 1 条。")).toBeVisible();
  expect(screen.getByText("已选 1 条")).toBeVisible();
  expect(screen.getByRole("button", { name: "批量反馈" })).toBeDisabled();
  const body = requests.find((item) => item.path.includes("batch-feedback"))?.body;
  expect(body).toEqual({ verdict: "helpful", targets: [{ job_id: 1, finding_id: "j1:a2:c0", source_attempt: 2, revision: 3 }, { job_id: 2, finding_id: "j2:a2:c0", source_attempt: 2, revision: 3 }] });
  await waitFor(() => expect(screen.getByRole("button", { name: "刷新并重新选择" })).toBeEnabled());
  await userEvent.click(screen.getByRole("button", { name: "刷新并重新选择" }));
  await waitFor(() => expect(screen.queryByText("已选 1 条")).not.toBeInTheDocument());
});

it("刷新列表后再增加勾选，原目标仍保留勾选时版本，不随新行替换", async () => {
  const requests = setup();
  await screen.findByText("共 2 条发现");
  await userEvent.click(within(screen.getAllByRole("row")[1]).getByRole("checkbox"));
  await userEvent.click(screen.getByRole("button", { name: "刷新发现" }));
  await waitFor(() => expect(requests.filter((item) => item.path.startsWith("/api/review-findings?"))).toHaveLength(2));
  await waitFor(() => expect(within(screen.getAllByRole("row")[2]).getByRole("checkbox")).toBeEnabled());
  await userEvent.click(within(screen.getAllByRole("row")[2]).getByRole("checkbox"));
  await userEvent.click(screen.getByRole("button", { name: "批量反馈" }));
  const dialog = await screen.findByRole("dialog");
  expect(within(dialog).getAllByRole("listitem").map((item) => item.textContent)).toEqual([
    expect.stringContaining("j1:a2:c0 · 版本 2/3"), expect.stringContaining("j2:a2:c0 · 版本 2/4"),
  ]);
  await userEvent.click(within(dialog).getByRole("button", { name: "返回核对" }));
});
