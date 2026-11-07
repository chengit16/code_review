/** @description 合成配置服务验证 1～10 边界、冻结草稿、保存反馈与冲突不自动重放。 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";

import { ApiError } from "../api/client";
import * as scheduler from "../api/workerScheduler";
import { WorkerConcurrency } from "../pages/WorkerConcurrency";

function panel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const read = vi.spyOn(scheduler, "getWorkerSchedulerConfig").mockResolvedValue({ model_task_concurrency: 1, version: 1 });
  const save = vi.spyOn(scheduler, "saveWorkerSchedulerConfig").mockResolvedValue({ model_task_concurrency: 10, version: 2 });
  render(<QueryClientProvider client={client}><WorkerConcurrency token="synthetic-token" /></QueryClientProvider>);
  return { client, read, save };
}

it("支持自由设置 10，保存携带读取版本并明确不代表已应用", async () => {
  const { save } = panel();
  const input = await screen.findByRole("spinbutton", { name: "模型任务并发上限（1～10）" });
  const button = screen.getByRole("button", { name: "保存并发上限" });
  expect(button).toBeDisabled();
  await userEvent.clear(input);
  await userEvent.type(input, "10");
  await userEvent.click(button);
  await waitFor(() => expect(save).toHaveBeenCalledWith("synthetic-token", { model_task_concurrency: 10, version: 1 }));
  expect(await screen.findByRole("status")).toHaveTextContent("等待 Worker 确认应用");
  expect(screen.getByText(/调高后可自动领取更多已排队任务并产生模型费用/)).toBeVisible();
});

it.each(["", "0", "11", "1.5"])("非法容量 %s 不发送保存请求", async (value) => {
  const { save } = panel();
  const input = await screen.findByRole("spinbutton");
  await userEvent.clear(input);
  if (value) await userEvent.type(input, value);
  expect(screen.getByRole("button", { name: "保存并发上限" })).toBeDisabled();
  expect(save).not.toHaveBeenCalled();
});

it("后台刷新不覆盖草稿及旧版本，409 保留输入且禁止自动重试", async () => {
  const { client, save } = panel();
  save.mockRejectedValue(new ApiError(409, "配置版本冲突", "scheduler_config_conflict"));
  const input = await screen.findByRole("spinbutton");
  await userEvent.clear(input);
  await userEvent.type(input, "7");
  act(() => client.setQueryData(["worker-scheduler-config"], { model_task_concurrency: 2, version: 2 }));
  expect(input).toHaveValue(7);
  await userEvent.click(screen.getByRole("button", { name: "保存并发上限" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("草稿保留");
  expect(save).toHaveBeenCalledWith("synthetic-token", { model_task_concurrency: 7, version: 1 });
  await userEvent.clear(input);
  await userEvent.type(input, "8");
  expect(screen.getByRole("button", { name: "保存并发上限" })).toBeDisabled();
  expect(save).toHaveBeenCalledTimes(1);
  await userEvent.click(screen.getByRole("button", { name: "放弃草稿并刷新配置" }));
  await waitFor(() => expect(input).toHaveValue(1));
});

it("读取失败不伪造默认值或允许提交", async () => {
  vi.spyOn(scheduler, "getWorkerSchedulerConfig").mockRejectedValue(new Error("合成读取失败"));
  const save = vi.spyOn(scheduler, "saveWorkerSchedulerConfig");
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><WorkerConcurrency token="" /></QueryClientProvider>);
  expect(await screen.findByRole("alert")).toHaveTextContent("合成读取失败");
  expect(screen.queryByRole("spinbutton")).toBeNull();
  expect(save).not.toHaveBeenCalled();
});
