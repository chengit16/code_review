/** @description 验证累计时间、失败文案与未知费用；只使用服务端合成事实，不在前端重算历史。 */
import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import type { ReviewJob, ReviewJobDetail } from "../api/types";
import { AttemptTimeline, JobCostFacts, JobExecution, JobTimeFacts, resultText, secondsText } from "../pages/JobExecution";

const job: ReviewJob = {
  id: 1, repository_id: 1, event_id: 1, mr_iid: 7, commit_sha: "a".repeat(40), ordinal: 0,
  status: "failed", error: "[timeout] 超时", attempts: 3,
  created_at: "2026-01-01 00:00:00", finished_at: "2026-01-01 11:00:00",
  reason: { code: "timeout", message: "评审预算耗尽，不自动整批重试" },
  timing: { first_queue_seconds: 21600, latest_execution_seconds: 3600,
    cumulative_execution_seconds: 10800, execution_complete: true, known_attempts: 3,
    total_attempts: 3, total_elapsed_seconds: 39600, retry_backoff_seconds: null,
    retry_ready_wait_seconds: null, schedule_complete: false, calculated_at: "2026-01-01T11:00:00Z" },
};

it("累计三小时与首次排队六小时分开显示", () => {
  render(<JobTimeFacts job={job} />);
  expect(screen.getByText("初审累计执行 3 小时 0 分")).toBeVisible();
  expect(screen.getByText("首次排队 6 小时 0 分")).toBeVisible();
  expect(screen.getByText("总历时 11 小时 0 分 · 初审 3 次 / 补审执行 0 次")).toBeVisible();
});

it("紧凑列表只显示初审执行与独立的初审、补审次数", () => {
  render(<JobTimeFacts job={{ ...job, recovery_execution_count: 2 }} compact />);
  expect(screen.getByText("初审执行 3 小时 0 分")).toBeVisible();
  expect(screen.getByText("初审 3 次 · 补审 2 次")).toBeVisible();
  expect(screen.queryByText(/总历时/)).not.toBeInTheDocument();
});

it("尚未领取的排队任务只显示等待，不把排队误计为执行", () => {
  render(<JobTimeFacts job={{ ...job, status: "queued", attempts: 0 }} compact />);
  expect(screen.getByText("已排队 6 小时 0 分")).toBeVisible();
  expect(screen.getByText("尚未执行")).toBeVisible();
  expect(screen.queryByText(/初审执行/)).not.toBeInTheDocument();
});

it.each(["failed", "skipped", "cancelled", "partial"])("%s 不显示零发现作为成功结论", (status) => {
  expect(resultText({ ...job, reason: undefined, status })).not.toContain("0 条发现");
});

it("旧记录缺失时间显示未知而不是零", () => {
  render(<JobTimeFacts job={{ ...job, timing: undefined }} />);
  expect(screen.getByText("初审累计执行 未知")).toBeVisible();
  expect(secondsText(null)).toBe("未知");
  expect(secondsText(1)).toBe("1 秒");
});

it("累计费用不完整时明确标记只包含已知部分", () => {
  render(<JobCostFacts job={{ ...job, cumulative_usage: {
    known_usage_attempts: 1, total_attempts: 3, usage_complete: false, priced_attempts: 1,
    known_tokens: { input_tokens: 10, output_tokens: 0, total_tokens: 10 },
    known_costs: [{ currency: "CNY", total: "2" }], cost_complete: false,
  } }} />);
  expect(screen.getByText("仅已知部分，费用不完整")).toBeVisible();
});

it("仅换行分析不宣称已排除，逐次成功和取消同时保留", () => {
  const detail: ReviewJobDetail = { ...job, status: "cancelled", result: null, result_path: null,
    feedback: {}, issue_ids: {}, delivery: null, notification_min_severity: "high",
    scope_analysis: { mode: "analyze_only", status: "limited", original_count: 200,
      checked_count: 180, newline_only_count: 170, newline_only_paths: ["main.py"],
      excluded_count: 0, filter_enabled: false, filter_reason: "当前仅分析不排除" },
    attempt_history: [{ id: 1, attempt_number: 1, status: "complete", error: null,
      started_at: "2026-01-01 06:00:00", finished_at: "2026-01-01 07:00:00" },
    { id: 2, attempt_number: 2, status: "cancelled", error: "用户取消",
      started_at: "2026-01-01 08:00:00", finished_at: "2026-01-01 08:00:01" }],
  };
  render(<><JobExecution job={detail} /><AttemptTimeline job={detail} /></>);
  expect(screen.getByText(/确认仅换行 170 个 · 策略排除 0 个/)).toBeVisible();
  expect(screen.getByText(/当前仅分析不排除/)).toBeVisible();
  expect(screen.getByText(/预检受限或不可用/)).toBeVisible();
  expect(screen.getByText("已取消")).toBeInTheDocument();
  expect(screen.getByText("已完成")).toBeInTheDocument();
});

it("中断恢复时间不冒充真实执行结束，阶段耗时保持未知", () => {
  const detail: ReviewJobDetail = { ...job, result: null, result_path: null,
    feedback: {}, issue_ids: {}, delivery: null, notification_min_severity: "high",
    attempt_history: [{ id: 1, attempt_number: 1, status: "failed", error: "Worker 中断",
      reason_code: "interrupted", started_at: "2026-01-01 06:00:00",
      finished_at: "2026-01-02 00:00:00" }],
    stage_timings: [{ attempt_number: 1, stage: "review",
      started_at: "2026-01-01 06:00:00", finished_at: "2026-01-02 00:00:00" }],
  };
  render(<AttemptTimeline job={detail} />);
  expect(screen.getByText(/恢复记录时间/)).toBeInTheDocument();
  expect(screen.getByText(/执行 未知/)).toBeInTheDocument();
  expect(screen.getByText(/实际阶段耗时未知/)).toBeInTheDocument();
  expect(screen.queryByText(/18 小时/)).not.toBeInTheDocument();
});
