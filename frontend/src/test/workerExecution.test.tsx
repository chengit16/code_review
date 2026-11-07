/** @description 验证调度槽安全展示；缺失、过期与停止不能伪装为健康或自动恢复。 */
import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import type { SchedulerSnapshot } from "../api/reviewExecution";
import { WorkerExecution } from "../pages/WorkerExecution";

const snapshot: SchedulerSnapshot = { model_task_concurrency: 1, slots: [
  { lane: "model", owner: "synthetic", generation: 3, task_kind: "review", task_id: 7,
    repository_id: 1, state: "running", heartbeat_at: "2026-11-06 00:00:00",
    heartbeat_age_seconds: 1 },
  { lane: "ingress", owner: "synthetic", generation: 2, task_kind: null, task_id: null,
    repository_id: null, state: "idle", heartbeat_at: "2026-11-06 00:00:00",
    heartbeat_age_seconds: 1 },
  { lane: "delivery", owner: "synthetic", generation: 1, task_kind: "notification", task_id: 8,
    repository_id: 1, state: "running", heartbeat_at: "2026-11-06 00:00:00",
    heartbeat_age_seconds: 1 },
] };

it("区分模型、事件和投递执行槽且不提供增加并发按钮", () => {
  render(<WorkerExecution snapshot={snapshot} />);
  expect(screen.getByText(/模型任务并发 1/)).toBeVisible();
  expect(screen.getByText("执行中 · 合并后评审 #7")).toBeVisible();
  expect(screen.getByText("事件与 Git 准备")).toBeVisible();
  expect(screen.getByText("执行中 · 飞书通知 #8")).toBeVisible();
  expect(screen.queryByRole("button")).toBeNull();
});

it("旧 API 和尚无协调器记录时不声称本地调度生效", () => {
  const { rerender } = render(<WorkerExecution />);
  expect(screen.getByText(/模型任务并发 未知/)).toBeVisible();
  expect(screen.getByText(/不能据此确认解耦已在本机生效/)).toBeVisible();
  rerender(<WorkerExecution snapshot={{ model_task_concurrency: 1, slots: [] }} />);
  expect(screen.getByText(/不能据此确认解耦已在本机生效/)).toBeVisible();
});

it("过期心跳提示待核实，已停止槽不提示抢占或当作在运行", () => {
  const slots = snapshot.slots.map((slot, index) => ({ ...slot,
    state: index === 0 ? "stopped" : "idle", heartbeat_age_seconds: index === 1 ? 20 : 1 }));
  render(<WorkerExecution snapshot={{ ...snapshot, slots }} />);
  expect(screen.getByText("已停止")).toBeVisible();
  expect(screen.getAllByText(/协调心跳过期，执行状态待核实/)).toHaveLength(1);
  expect(screen.queryByText("执行中 · 合并后评审 #7")).toBeNull();
});

it("区分已保存与已应用并发，独立标识多个模型槽及降低容量排空", () => {
  render(<WorkerExecution snapshot={{ model_task_concurrency: 1, config_version: 3,
    applied_concurrency: 1, applied_version: 3, running_model_tasks: 2, draining: true,
    slots: [
      { ...snapshot.slots[0], slot_id: "model", slot_index: 1 },
      { ...snapshot.slots[0], slot_id: "model:2", slot_index: 2, task_id: 9 },
    ] }} />);
  expect(screen.getByRole("heading", { name: "模型评审 #1" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "模型评审 #2" })).toBeVisible();
  expect(screen.getByText(/已应用上限 1 · 持久化执行中 2/)).toHaveTextContent("正在排空");
  expect(screen.getByText(/任务 #9|合并后评审 #9/)).toHaveTextContent("超出上限，不再领取");
});
