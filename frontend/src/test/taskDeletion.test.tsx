/** @description 验证删除确认、冻结版本、无自动重试、错误可见和成功返回；仅使用合成接口。 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConfigProvider } from "antd";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { expect, it, vi } from "vitest";

import type { TaskDeletionTarget } from "../api/tasks";
import { DesignProvider } from "../app/DesignProvider";
import { TaskDelete } from "../pages/TaskDelete";
import { JobsTable } from "../pages/jobs/JobsTable";
import type { ReviewJob } from "../api/types";

const target: TaskDeletionTarget = { id: 487, status: "partial", attempts: 1, finished_at: "2026-11-13 03:53:25" };

function renderDelete(initial = target) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: 3 } } });
  function node(value: TaskDeletionTarget) {
    // JSDOM 无布局动画，组件测试关闭动效；真实焦点和窄屏另由浏览器检查。
    return <ConfigProvider theme={{ token: { motion: false } }}><DesignProvider><QueryClientProvider client={client}><MemoryRouter initialEntries={["/jobs/487"]}>
      <Routes><Route path="/jobs/:id" element={<TaskDelete token="" target={value} back="/jobs?status=partial" />} />
        <Route path="/jobs" element={<p>已回到任务列表</p>} /></Routes>
    </MemoryRouter></QueryClientProvider></DesignProvider></ConfigProvider>;
  }
  return { ...render(node(initial)), node, client };
}

it("取消不写入", async () => {
  const fetch = vi.spyOn(globalThis, "fetch");
  const user = userEvent.setup();
  renderDelete();
  await user.click(screen.getByRole("button", { name: "删除任务" }));
  await user.click(screen.getByRole("button", { name: "取消" }));
  expect(fetch).not.toHaveBeenCalled();
});

it("确认冻结原任务版本；失败不自动重试且可关闭", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ detail: "任务版本已变化" }), { status: 409 }));
  const user = userEvent.setup();
  const view = renderDelete();
  await user.click(screen.getByRole("button", { name: "删除任务" }));
  await waitFor(() => expect(screen.getByRole("dialog", { name: "删除任务 #487" })).toBeVisible());
  view.rerender(view.node({ ...target, attempts: 2 }));
  await user.click(screen.getByRole("button", { name: "确认删除" }));
  expect(await screen.findByText(/任务版本已变化.*请关闭弹窗/)).toBeVisible();
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(JSON.parse(fetch.mock.calls[0][1]?.body as string)).toEqual({ expected_status: "partial", expected_attempts: 1, expected_finished_at: target.finished_at });
  expect(screen.getByRole("button", { name: "确认删除" })).toBeDisabled();
});

it("删除成功后使统计缓存失效并返回任务列表", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ status: "deleted", job_id: 487, deleted_findings: 2, deleted_issues: 2 })));
  const user = userEvent.setup();
  const view = renderDelete();
  view.client.setQueryData(["review-effectiveness"], { total: 2 });
  await user.click(screen.getByRole("button", { name: "删除任务" }));
  await user.click(await screen.findByRole("button", { name: "确认删除" }));
  expect(await screen.findByText("已回到任务列表")).toBeVisible();
  expect(fetch.mock.calls[0][0]).toBe("/api/jobs/487");
  expect(fetch.mock.calls[0][1]?.method).toBe("DELETE");
  expect(view.client.getQueryState(["review-effectiveness"])?.isInvalidated).toBe(true);
});

it.each(["queued", "running"])("活动状态 %s 禁止开始删除", (status) => {
  renderDelete({ ...target, status });
  expect(screen.getByRole("button", { name: "删除任务" })).toBeDisabled();
});

it.each([true, false])("列表按编辑权限展示删除入口：%s", (canEdit) => {
  const client = new QueryClient();
  const item: ReviewJob = { ...target, repository_id: 1, event_id: 1, mr_iid: 7,
    commit_sha: "a".repeat(40), ordinal: 0, error: null, created_at: "2026-11-13 00:00:00" };
  render(<DesignProvider><QueryClientProvider client={client}><MemoryRouter><JobsTable token="" items={[item]} canEdit={canEdit}
    selectable={[487]} targets={[]} disabled={false} onSelect={() => {}} detailPath={(id) => `/jobs/${id}`}
    loading={false} failed={false} /></MemoryRouter></QueryClientProvider></DesignProvider>);
  if (canEdit) expect(screen.getByRole("button", { name: "删除任务 487" })).toBeEnabled();
  else expect(screen.queryByRole("button", { name: "删除任务 487" })).not.toBeInTheDocument();
});
