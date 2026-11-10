/** @description 保护发现反馈处理进度、版本变化及未知和覆盖边界，不显示跨任务处置标签。 */
import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import type { ReviewJob } from "../api/types";
import { IssueSummary } from "../pages/jobs/TaskIssueSummary";

const issues: NonNullable<ReviewJob["issue_summary"]> = {
  available: true, finding_count: 8, highest_severity: "high",
  open_count: 8, fixed_count: 0, ignored_count: 0, false_positive_count: 0, unknown_count: 0,
  complete: true, no_findings: false, coverage_complete: true, coverage_limited: false,
};
const feedback: NonNullable<ReviewJob["feedback_summary"]> = {
  available: true, total: 8, helpful: 0, false_positive: 0, ignored: 0, unmarked: 8,
};
const job: ReviewJob = {
  id: 403, repository_id: 1, event_id: 1, mr_iid: 1, commit_sha: "a".repeat(40), ordinal: 0,
  status: "complete", error: null, attempts: 1, created_at: "2026-11-09 00:00:00",
  finished_at: "2026-11-09 00:01:00", issue_summary: issues, feedback_summary: feedback,
};

it("列表只展示反馈进度，忽略跨任务问题状态，撤销后退回待反馈", () => {
  const view = render(<IssueSummary job={job} />);
  expect(screen.getByText("待反馈 · 剩 8 条")).toBeVisible();
  expect(screen.queryByLabelText(/^问题处置/)).not.toBeInTheDocument();
  expect(screen.queryByText(/待处理|已处理.*个问题/)).not.toBeInTheDocument();
  view.rerender(<IssueSummary job={{ ...job, feedback_summary: { ...feedback, helpful: 1, unmarked: 7 } }} />);
  expect(screen.getByText("反馈中 1/8 · 剩 7 条")).toBeVisible();
  const evaluated = { ...feedback, helpful: 5, false_positive: 1, ignored: 2, unmarked: 0 };
  view.rerender(<IssueSummary job={{ ...job, feedback_summary: evaluated }} />);
  expect(screen.getByText("反馈完成 8/8")).toBeVisible();
  view.rerender(<IssueSummary job={{ ...job, feedback_summary: evaluated,
    issue_summary: { ...issues, open_count: 0, fixed_count: 2 } }} />);
  expect(screen.getByText("反馈完成 8/8")).toBeVisible();
  expect(screen.queryByLabelText(/^问题处置/)).not.toBeInTheDocument();
  view.rerender(<IssueSummary job={job} />);
  expect(screen.getByText("待反馈 · 剩 8 条")).toBeVisible();
});

it("补审新增发现时按新有效集合重新展示剩余反馈", () => {
  const view = render(<IssueSummary job={{ ...job, feedback_summary: { ...feedback, helpful: 8, unmarked: 0 } }} />);
  expect(screen.getByText("反馈完成 8/8")).toBeVisible();
  view.rerender(<IssueSummary job={{ ...job, issue_summary: { ...issues, finding_count: 9, open_count: 9 },
    feedback_summary: { ...feedback, total: 9, helpful: 8, unmarked: 1 } }} />);
  expect(screen.getByText("反馈中 8/9 · 剩 1 条")).toBeVisible();
});

it.each([
  undefined, { ...feedback, available: false }, { ...feedback, total: null },
  { ...feedback, total: 7 }, { ...feedback, unmarked: -1 }, { ...feedback, helpful: 0.5 },
  { ...feedback, helpful: 1 }, { ...feedback, ignored: Number.NaN },
])("反馈数据缺失或不一致时不补零或显示完成：%j", (value) => {
  render(<IssueSummary job={{ ...job, feedback_summary: value }} />);
  expect(screen.getByText("反馈待核实")).toBeVisible();
  expect(screen.queryByText(/反馈完成|有帮助/)).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/^问题处置/)).not.toBeInTheDocument();
});

it("问题关联未知不影响独立反馈进度，部分覆盖仍保留范围提示", () => {
  const view = render(<IssueSummary job={{ ...job, issue_summary: { ...issues, complete: false, open_count: 3, unknown_count: 5 } }} />);
  expect(screen.getByText("待反馈 · 剩 8 条")).toBeVisible();
  expect(screen.queryByLabelText(/^问题处置/)).not.toBeInTheDocument();
  view.rerender(<IssueSummary job={{ ...job, status: "partial",
    issue_summary: { ...issues, coverage_complete: false },
    feedback_summary: { ...feedback, helpful: 8, unmarked: 0 } }} />);
  expect(screen.getByText("仅当前已发现范围")).toBeVisible();
  expect(screen.getByText("反馈完成 8/8")).toBeVisible();
});

it.each(["coverage_limited", "coverage_complete"] as const)("%s 范围受限时继续提示", (field) => {
  render(<IssueSummary job={{ ...job, issue_summary: { ...issues, [field]: field === "coverage_limited" } }} />);
  expect(screen.getByText("仅当前已发现范围")).toBeVisible();
});

it("完整无发现不绘制人工完成标识，范围受限或计数缺失不能暗示无问题", () => {
  const empty = { ...issues, finding_count: 0, open_count: 0, no_findings: true };
  const view = render(<IssueSummary job={{ ...job, issue_summary: empty }} />);
  expect(screen.getByText("本次未发现问题")).toBeVisible();
  expect(screen.queryByLabelText(/^反馈进度|^问题处置/)).not.toBeInTheDocument();
  view.rerender(<IssueSummary job={{ ...job, issue_summary: { ...empty, coverage_limited: true } }} />);
  expect(screen.getByText("选中范围内暂无发现")).toBeVisible();
  view.rerender(<IssueSummary job={{ ...job, issue_summary: { ...issues, finding_count: null } }} />);
  expect(screen.getByText("状态待核实")).toBeVisible();
});
