/** @description 验证项目换行开关的旧接口默认、保存冲突及排除范围披露；仅使用合成响应。 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";

import { parsePremergeResult } from "../api/premerge";
import type { ReviewJob } from "../api/types";
import { resultText } from "../pages/JobExecution";
import { ProjectReviewLimits } from "../pages/ProjectReviewLimits";

it("旧接口默认关闭，冲突保留开关草稿，重试成功后显示持久化值", async () => {
  let failSave = true;
  let value = { model_profile_id: null, timeout_seconds: null, max_files: null, max_tokens_budget: null };
  const bodies: unknown[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url, options) => {
    if (String(url).endsWith("/api/model-profiles")) return new Response("[]");
    if (options?.method === "PUT") {
      bodies.push(JSON.parse(String(options.body)));
      if (failSave) return new Response('{"detail":"合成项目仍有在途任务"}', { status: 409 });
      value = JSON.parse(String(options.body));
    }
    return new Response(JSON.stringify(value));
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><ProjectReviewLimits token="" repositoryId={1} /></QueryClientProvider>);
  const checkbox = await screen.findByRole("checkbox", { name: "自动过滤纯换行文件" });
  expect(checkbox).not.toBeChecked();
  const user = userEvent.setup();
  await user.click(checkbox);
  await user.click(screen.getByRole("button", { name: "保存评审参数" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("草稿已保留");
  expect(checkbox).toBeChecked();
  expect(bodies[0]).toMatchObject({ newline_filter_enabled: true });
  failSave = false;
  await user.click(screen.getByRole("button", { name: "保存评审参数" }));
  expect(await screen.findByText("评审参数已保存")).toBeVisible();
  expect(checkbox).toBeChecked();
  expect(screen.getByRole("button", { name: "保存评审参数" })).toBeDisabled();
});

it("成功结果仍披露策略排除，不把选中覆盖包装成原始全范围覆盖", () => {
  const job: ReviewJob = { id: 1, repository_id: 1, event_id: 1, mr_iid: 7,
    commit_sha: "a".repeat(40), ordinal: 0, status: "complete", error: null,
    attempts: 1, created_at: "2026-01-01 00:00:00", finished_at: "2026-01-01 00:01:00",
    finding_count: 0,
    scope_analysis: { mode: "exclude_verified_paths", status: "complete", original_count: 10,
      checked_count: 10, newline_only_count: 9, excluded_count: 9, filter_enabled: true,
      filter_reason: "已通过双预览校验" } };
  expect(resultText(job)).toContain("纯换行策略排除 9 个文件，非原始全范围模型覆盖");
  expect(parsePremergeResult(JSON.stringify({ comments: [], input_filter: { excluded_count: 9 } })))
    .toMatchObject({ valid: true, completeCoverage: false, excludedCount: 9 });
});
