/** @description 补审确认范围冻结、未知响应幂等重放和只读权限；只使用合成服务替身。 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";

import * as recovery from "../api/reviewRecovery";
import * as commandId from "../api/commandId";
import * as conclusions from "../api/reviewConclusions";
import { ApiError } from "../api/client";
import type { ReviewJobDetail } from "../api/types";
import { EffectiveReview } from "../pages/EffectiveReview";
import { ReviewRecoveryPanel } from "../pages/ReviewRecoveryPanel";

const job: ReviewJobDetail = { id: 1, repository_id: 1, event_id: 1, mr_iid: 7,
  commit_sha: "a".repeat(40), ordinal: 1, status: "partial", error: null, attempts: 1,
  created_at: "2026-01-01", finished_at: null, result: null, result_path: null,
  feedback: {}, issue_ids: {}, delivery: null, notification_min_severity: "high", attempt_history: [] };
const eligibility: recovery.RecoveryEligibility = { eligible: true, reason_code: null,
  source_attempt: 1, source_revision: 0, remaining_count: 2, remaining_paths: ["comma,name.ts", "space name.py"],
  max_token_budget: 2000, max_timeout_seconds: 30, remaining_batches: 3, active_recovery_id: null,
  budget: { max_batches: 3, used_batches: 0, max_total_tokens: 6000, committed_tokens: 0, minimum_start_tokens: 1000, authorization_version: 0, previous_gate: null },
  snapshot: { head_sha: job.commit_sha, base_sha: null, provider: "synthetic", model: "fixture", model_version: 1, ocr_version: "1.12.9", rule_digest: "safe-digest" } };

function panel(canEdit = true, state: recovery.RecoveryEligibility | Error = eligibility, history: recovery.RecoveryRecord[] = []) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const readEligibility = vi.spyOn(recovery, "getRecoveryEligibility");
  if (state instanceof Error) readEligibility.mockRejectedValue(state);
  else readEligibility.mockResolvedValue(state);
  vi.spyOn(recovery, "getRecoveries").mockResolvedValue(history);
  vi.spyOn(recovery, "getRecoveryDeliveries").mockResolvedValue([]);
  render(<QueryClientProvider client={client}><ReviewRecoveryPanel token="" job={job} canEdit={canEdit} /></QueryClientProvider>);
  return client;
}

it("配置不可用时明确展示原因码和修复步骤，不要求开启功能", async () => {
  const create = vi.spyOn(recovery, "createRecovery");
  panel(true, { ...eligibility, eligible: false, reason_code: "configuration_unavailable" });
  const reason = await screen.findByText("当前无法补审：无法读取当前模型配置，请先核对配置");
  expect(reason).toBeVisible();
  expect(screen.getByText(/补审无需配置开关或项目白名单/)).toBeVisible();
  expect(screen.getByText(/资格原因码/)).toHaveTextContent("configuration_unavailable");
  const button = screen.getByRole("button", { name: "继续审核剩余部分" });
  expect(button).toBeDisabled();
  expect(button).toHaveAccessibleDescription(/无法读取当前模型配置/);
  await userEvent.click(button);
  expect(create).not.toHaveBeenCalled();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it.each([
  ["configuration_changed", /不能放宽来源校验强行补审/],
  ["source_evidence_invalid", /仅重启服务不能恢复缺失证据/],
])("资格受 %s 阻塞时显示对应处理指引", async (reason, guidance) => {
  panel(true, { ...eligibility, eligible: false, reason_code: reason });
  expect(await screen.findByText(guidance)).toBeVisible();
  expect(screen.getByRole("button", { name: "继续审核剩余部分" })).toBeDisabled();
});

it("资格查询失败不伪装成未开启，也不允许排队", async () => {
  panel(true, new Error("合成资格查询失败"));
  expect(await screen.findByText(/补审资格查询失败，请重新加载/)).toBeVisible();
  expect(screen.queryByText(/OCR_APP_REVIEW_RECOVERY_ENABLED=1/)).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "继续审核剩余部分" })).toBeDisabled();
});

it("确认快照不被后台刷新覆盖，费用未知明确展示，预算非法时不提交", async () => {
  const create = vi.spyOn(recovery, "createRecovery");
  const client = panel();
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "继续审核剩余部分" }));
  const dialog = screen.getByRole("dialog", { name: "确认补审范围与预算" });
  await act(async () => { client.setQueryData(["recovery-eligibility", 1], { ...eligibility, source_revision: 5, remaining_count: 1, remaining_paths: ["changed.py"] }); });
  expect(within(dialog).getByText(/源版本 0/)).toBeVisible();
  expect(within(dialog).getByText(/失败子集 2 个文件/)).toBeVisible();
  expect(within(dialog).getByText(/预估费用未知/)).toBeVisible();
  await user.clear(within(dialog).getByLabelText("本批 Token 上限"));
  await user.type(within(dialog).getByLabelText("本批 Token 上限"), "2001");
  expect(within(dialog).getByRole("button", { name: "确认并排队" })).toBeDisabled();
  expect(create).not.toHaveBeenCalled();
});

it("不确定响应后保留同一源版本、预算和幂等键，不自动调用第二次", async () => {
  const create = vi.spyOn(recovery, "createRecovery").mockRejectedValue(new Error("合成网络中断"));
  panel();
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "继续审核剩余部分" }));
  const dialog = screen.getByRole("dialog");
  await user.type(within(dialog).getByLabelText("本批 Token 上限"), "1000");
  await user.click(within(dialog).getByRole("button", { name: "确认并排队" }));
  await within(dialog).findByRole("alert");
  expect(create).toHaveBeenCalledTimes(1);
  expect(within(dialog).getByLabelText("本批 Token 上限")).toBeDisabled();
  await user.click(within(dialog).getByRole("button", { name: "重试同一补审请求" }));
  await waitFor(() => expect(create).toHaveBeenCalledTimes(2));
  expect(create.mock.calls[0][2]).toEqual(create.mock.calls[1][2]);
  expect(create.mock.calls[0][2].client_key).not.toBe("");
});

it("随机标识不可生成时在确认框解释且不提交，恢复后可以继续", async () => {
  const generate = vi.spyOn(commandId, "createCommandId").mockImplementationOnce(() => { throw new Error("合成随机源不可用"); });
  const create = vi.spyOn(recovery, "createRecovery").mockRejectedValue(new Error("合成网络中断"));
  panel();
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "继续审核剩余部分" }));
  const dialog = within(screen.getByRole("dialog"));
  await user.type(dialog.getByLabelText("本批 Token 上限"), "1000");
  await user.click(dialog.getByRole("button", { name: "确认并排队" }));
  expect(dialog.getByRole("alert")).toHaveTextContent("无法生成安全的请求标识");
  expect(create).not.toHaveBeenCalled();
  generate.mockReturnValue("12345678-1234-4234-8234-123456789abc");
  await user.click(dialog.getByRole("button", { name: "确认并排队" }));
  await waitFor(() => expect(create).toHaveBeenCalledOnce());
  expect(create.mock.calls[0][2].client_key).toBe("12345678-1234-4234-8234-123456789abc");
});

it("旧失效批次明确显示预算原因、实际覆盖和固定原因码", async () => {
  panel(true, eligibility, [{ id: 2, requested_by: "合成操作者", source_attempt: 1, source_revision: 0,
    status: "stale", token_budget: 1000, timeout_seconds: 30, cancel_requested: false,
    error_code: "child_not_usable", failure_summary: "本批完成 0/5 个文件；触发 Token 预算限制。未自动重试或增加额度。",
    created_at: "2026-11-07", started_at: null, finished_at: null, usage: { total_tokens: 584 }, estimated_cost: null }]);
  await screen.findByText(/本批完成 0\/5 个文件；触发 Token 预算限制/);
  expect(screen.getByText("child_not_usable")).toBeVisible();
  expect(screen.getByText("已失效", { exact: true })).toBeVisible();
  expect(screen.getByText(/旧版本将本批执行失败记为已失效/)).toBeVisible();
  expect(screen.getByText(/本批未形成可合并的评审结果/)).toBeVisible();
});

it("只读角色保留资格与历史说明，不出现补审写操作", async () => {
  panel(false);
  await screen.findByText(/剩余 2 个文件/);
  expect(screen.queryByRole("button", { name: "继续审核剩余部分" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "调整本任务补审额度" })).not.toBeInTheDocument();
});

it("预算未知时不填低默认值，超时沿用源快照而非固定30秒", async () => {
  const create = vi.spyOn(recovery, "createRecovery");
  panel(true, { ...eligibility, budget: null, max_timeout_seconds: 3600 });
  await userEvent.click(await screen.findByRole("button", { name: "继续审核剩余部分" }));
  const dialog = within(screen.getByRole("dialog"));
  expect(dialog.getByLabelText("本批 Token 上限")).toHaveValue(null);
  expect(dialog.getByLabelText("本批超时秒数")).toHaveValue(3600);
  expect(dialog.getByRole("button", { name: "确认并排队" })).toBeDisabled();
  expect(create).not.toHaveBeenCalled();
});

it("最低启动参考拦截过小预算，历史解释具体算式不误作已扣费用", async () => {
  const gate = { used_tokens: 573, group_estimate_tokens: 127524, projected_tokens: 128097, budget_tokens: 1000 };
  panel(true, { ...eligibility, max_token_budget: 200000,
    budget: { ...eligibility.budget!, minimum_start_tokens: 128097, previous_gate: gate } });
  expect(await screen.findByText(/已用 573 \+ 下一组预估 127524 = 128097/)).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "继续审核剩余部分" }));
  const dialog = within(screen.getByRole("dialog"));
  expect(dialog.getByLabelText("本批 Token 上限")).toHaveValue(null);
  await userEvent.clear(dialog.getByLabelText("本批 Token 上限"));
  await userEvent.type(dialog.getByLabelText("本批 Token 上限"), "1000");
  expect(dialog.getByRole("button", { name: "确认并排队" })).toBeDisabled();
});

it("额度保存需要原因且不排队，409保留草稿并阻止盲目重试", async () => {
  const write = vi.spyOn(recovery, "setRecoveryBudget").mockRejectedValue(new ApiError(409, "冲突", "budget_authorization_changed"));
  const create = vi.spyOn(recovery, "createRecovery");
  panel(true, { ...eligibility, eligible: false, reason_code: "recovery_limit" });
  await userEvent.click(await screen.findByRole("button", { name: "调整本任务补审额度" }));
  const dialog = within(screen.getByRole("dialog", { name: "确认调整任务额度" }));
  const save = dialog.getByRole("button", { name: "确认保存额度（不排队）" });
  expect(save).toBeDisabled();
  expect(dialog.getByLabelText("累计批准 Token 上限")).toHaveValue(6000);
  await userEvent.type(dialog.getByLabelText("调整原因"), "合成授权原因");
  await userEvent.click(save);
  expect(await dialog.findByRole("alert")).toHaveTextContent("额度版本已变化");
  expect(dialog.getByLabelText("调整原因")).toHaveValue("合成授权原因");
  expect(save).toBeDisabled();
  expect(write).toHaveBeenCalledOnce();
  expect(create).not.toHaveBeenCalled();
});

it("保存额度成功后仍需单独确认补审", async () => {
  vi.spyOn(recovery, "setRecoveryBudget").mockResolvedValue({ status: "saved", version: 1 });
  const create = vi.spyOn(recovery, "createRecovery");
  panel();
  await userEvent.click(await screen.findByRole("button", { name: "调整本任务补审额度" }));
  await userEvent.type(screen.getByLabelText("调整原因"), "合成授权");
  await userEvent.click(screen.getByRole("button", { name: "确认保存额度（不排队）" }));
  expect(await screen.findByText(/额度已保存，未排队或调用模型/)).toBeVisible();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(create).not.toHaveBeenCalled();
});

it("有效发现反馈使用稳定来源 ID 和固定版本，绝不提交聚合下标", async () => {
  const write = vi.spyOn(conclusions, "setFindingFeedback").mockResolvedValue({ verdict: "helpful" });
  const version = { source_attempt: 1, revision: 2, recovery_id: 7, terminal_state: "complete", finding_count: 1,
    coverage: { selected: 2, completed: 2, reused: 0, failed: 0, waived: 0 } };
  const current: ReviewJobDetail = { ...job, effective_document: {
    schema_version: "platform.review-conclusion/v1", consumer_integration_ready: true, job_id: 1,
    version, role: "effective", is_current_source: true, input_filter_excluded_count: 0,
    usage_through_recovery_id: 7, execution_usage: { known_usage_attempts: 0, total_attempts: 1,
      usage_complete: false, priced_attempts: 0, known_tokens: null, known_costs: [], cost_complete: false },
    findings: [{ finding_id: "j1:a1:r7:c0", origin: { kind: "recovery", source_attempt: 1, recovery_id: 7, comment_index: 0 },
      also_seen_in: [], path: "file.py", content: "合成补审发现", start_line: null, end_line: null, severity: "high", category: null }],
  } };
  const client = new QueryClient();
  render(<MemoryRouter><QueryClientProvider client={client}><EffectiveReview token="" job={current} canEdit /></QueryClientProvider></MemoryRouter>);
  await userEvent.click(screen.getByRole("button", { name: "有帮助" }));
  await waitFor(() => expect(write).toHaveBeenCalledWith("", 1, "j1:a1:r7:c0", { source_attempt: 1, revision: 2 }, "helpful"));
  expect(screen.getByText(/补审 #7 · 原始发现 1/)).toBeVisible();
});
