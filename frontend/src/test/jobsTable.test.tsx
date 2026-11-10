/** @description 列表反馈按发现计数，不由问题处置推断；保留覆盖和加载边界。 */
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it } from "vitest";

import type { ReviewJob } from "../api/types";
import { DesignProvider } from "../app/DesignProvider";
import { JobsTable } from "../pages/jobs/JobsTable";

const summary: NonNullable<ReviewJob["issue_summary"]> = {
  available: true, finding_count: 1, highest_severity: "high",
  open_count: 0, fixed_count: 0, ignored_count: 1, false_positive_count: 0, unknown_count: 0,
  complete: true, no_findings: false, coverage_complete: true, coverage_limited: false,
};

const job: ReviewJob = {
  id: 1, repository_id: 1, event_id: 1, repository_name: "合成项目", mr_iid: 7,
  commit_sha: "a".repeat(40), ordinal: 0, status: "complete", error: null, attempts: 1,
  created_at: "2026-01-01 00:00:00", finished_at: "2026-01-01 00:00:01",
  issue_summary: summary,
  feedback_summary: { available: true, total: 1, helpful: 1, false_positive: 0, ignored: 0, unmarked: 0 },
};

function show(item: ReviewJob) {
  render(<DesignProvider><MemoryRouter><JobsTable items={[item]} canEdit={false}
    selectable={[]} targets={[]} disabled={false} onSelect={() => {}}
    detailPath={(id) => `/jobs/${id}?status=complete`} loading={false} failed={false} />
  </MemoryRouter></DesignProvider>);
}

it("问题被忽略仍按独立价值反馈展示，只保留反馈完成状态", () => {
  show(job);
  expect(screen.getByText("有帮助 1 · 误报 0 · 忽略 0")).toBeVisible();
  expect(screen.getByLabelText("反馈进度：反馈完成 1/1")).toBeVisible();
  expect(screen.queryByLabelText(/^问题处置/)).not.toBeInTheDocument();
  expect(screen.queryByRole("columnheader", { name: "操作" })).not.toBeInTheDocument();
  expect(screen.queryByText(/修复 1/)).not.toBeInTheDocument();
});

it("缺失反馈投影显示待核实，不将问题忽略数当作反馈", () => {
  show({ ...job, feedback_summary: undefined, issue_summary: { ...summary, complete: false, unknown_count: 1 } });
  expect(screen.getByText("反馈待核实")).toBeVisible();
  expect(screen.queryByLabelText(/^问题处置/)).not.toBeInTheDocument();
  expect(screen.queryByText(/已处理/)).not.toBeInTheDocument();
});

it("部分覆盖零发现不显示本次未发现问题", () => {
  show({ ...job, status: "partial", issue_summary: { ...summary, finding_count: 0,
    ignored_count: 0, coverage_complete: false } });
  expect(screen.getByText("暂无发现 · 覆盖不完整")).toBeVisible();
  expect(screen.queryByText("本次未发现问题")).not.toBeInTheDocument();
});

it.each([
  ["queued", "待评审"], ["running", "评审中"], ["complete", "状态待核实"],
  ["failed", "未形成有效结论"], ["cancelled", "未形成有效结论"],
])("%s 没有当前结论时保留真实边界", (status, expected) => {
  show({ ...job, status, issue_summary: { ...summary, available: false,
    finding_count: null, complete: false } });
  expect(screen.getByText(expected)).toBeVisible();
  expect(screen.queryByText(/全部已处置/)).not.toBeInTheDocument();
  expect(screen.queryByText("本次未发现问题")).not.toBeInTheDocument();
});
