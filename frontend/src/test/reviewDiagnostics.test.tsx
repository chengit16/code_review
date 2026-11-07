/** @description 合成故障证据的展示测试；不请求工件、不将超时推断为已确认根因。 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { FailureAnalysis } from "../api/reviewDiagnostics";
import { ReviewFailureAnalysis } from "../pages/ReviewFailureAnalysis";
import { resultText } from "../pages/JobExecution";
import type { ReviewJob } from "../api/types";

const analysis: FailureAnalysis = {
  schema_version: "platform.failure-analysis/v1", summary: "完成 1/2 个文件；模型请求存在 HTTP 504",
  selected_count: 2, completed_count: 1, failed_count: 1, failed_group_count: null,
  report_state: "limited", groups: [],
  requests: [{ group_id: null, task_type: "plan_task", request_no: 1, attempts: 2,
    http_statuses: [504], error_classes: ["timeout"], failure_phases: ["http", "context"],
    duration_to_headers_ms: [60001, 20], observed_backoff_ms: [400] }],
  signals: [{ code: "http_504", message: "上游请求返回 HTTP 504，具体网关层级未知", count: 1 }],
  notes: ["不能计算全部成功请求的耗时分布。"],
};

describe("分层失败诊断", () => {
  it("旧结果不猜测原因，也不出现恢复按钮", () => {
    render(<ReviewFailureAnalysis analysis={null} />);
    expect(screen.getByText(/历史结果未保存分层诊断/)).toBeVisible();
    expect(screen.getByText(/需要受控历史诊断导入/)).toBeVisible();
    expect(screen.getByText(/无需再次调用模型/)).toHaveTextContent(/管理员可预览后执行批量导入/);
    expect(screen.queryByText(/HTTP 504/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("披露报告截断、关联未知及不同层级超时，不输出原始响应", () => {
    render(<ReviewFailureAnalysis analysis={analysis} />);
    expect(screen.getByText(analysis.summary)).toBeVisible();
    expect(screen.getByText(/超限或截断/)).toBeVisible();
    expect(screen.getByText(/分组关联未知 · 计划阶段/)).toBeInTheDocument();
    expect(screen.getByText(/响应头计时（毫秒）：60001 \/ 20/)).toBeInTheDocument();
    expect(screen.getByText(/不能计算全部成功请求/)).toBeVisible();
  });

  it("历史导入的诊断明确标记证据来源，不冒充重新评审", () => {
    render(<ReviewFailureAnalysis analysis={analysis} importedAt="2026-11-07 02:00:00" />);
    expect(screen.getByText(/历史诊断导入于/)).toHaveTextContent(/没有重跑模型或修改初审结果/);
    expect(screen.getByText(analysis.summary)).toBeVisible();
  });

  it("失败列表优先使用持久化摘要，成功不沿用故障提示", () => {
    const job: ReviewJob = { id: 1, repository_id: 1, event_id: 1, mr_iid: 1,
      commit_sha: "a".repeat(40), ordinal: 1, status: "partial", error: null,
      attempts: 1, created_at: "2026-01-01", finished_at: null,
      failure_summary: analysis.summary, reason: { code: "partial", message: "部分完成" } };
    expect(resultText(job)).toBe(analysis.summary);
    expect(resultText({ ...job, status: "complete", finding_count: 1 })).not.toContain("504");
  });
});
