/** @description 保护配置读取失败、后台刷新与保存冲突时的草稿；所有接口使用合成响应。 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, renderHook, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";

import { PremergeSetting } from "../pages/PremergeSetting";
import { useConfigurationDraft } from "../ui/useConfigurationDraft";

it("后台刷新不覆盖草稿，保存后使用新读取基线", () => {
  const { result, rerender } = renderHook(({ value }) => useConfigurationDraft(value), { initialProps: { value: { timeout: 60 } } });
  act(() => result.current.setValue({ timeout: 120 }));
  rerender({ value: { timeout: 180 } });
  expect(result.current.value).toEqual({ timeout: 120 });
  expect(result.current.dirty).toBe(true);
  act(() => result.current.saved());
  expect(result.current.value).toEqual({ timeout: 180 });
  expect(result.current.dirty).toBe(false);
});

it("无读取基线不能建立可保存的默认草稿", () => {
  const { result } = renderHook(() => useConfigurationDraft<{ enabled: boolean }>(undefined));
  act(() => result.current.setValue({ enabled: false }));
  expect(result.current.value).toBeUndefined();
  expect(result.current.dirty).toBe(false);
});

it("撤销全部编辑后跟随后台最新配置，不保留无变化的旧草稿", () => {
  const { result, rerender } = renderHook(({ value }) => useConfigurationDraft(value), { initialProps: { value: { timeout: 60 } } });
  act(() => result.current.setValue({ timeout: 120 }));
  act(() => result.current.setValue({ timeout: 60 }));
  rerender({ value: { timeout: 180 } });
  expect(result.current.value).toEqual({ timeout: 180 });
  expect(result.current.dirty).toBe(false);
});

it("合并前配置读取失败只提供重新加载，恢复后才允许编辑", async () => {
  let failed = true;
  vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response(JSON.stringify(failed ? { detail: "合成读取失败" } : { enabled: true, include_description: true, context_paths: ["docs/context.md"] }), { status: failed ? 503 : 200 }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><PremergeSetting token="" repositoryId={1} /></QueryClientProvider>);
  expect(await screen.findByRole("alert")).toHaveTextContent("合成读取失败");
  expect(screen.queryByRole("button", { name: "保存合并前配置" })).not.toBeInTheDocument();
  failed = false;
  await userEvent.click(screen.getByRole("button", { name: "重新加载" }));
  expect(await screen.findByRole("checkbox", { name: "包含 GitLab MR 描述" })).toBeChecked();
  expect(screen.getByRole("button", { name: "保存合并前配置" })).toBeDisabled();
});

it("保存错误与查询错误分离，失败保留草稿，成功清除脏状态", async () => {
  let failSave = true;
  let saved = { enabled: false, include_description: false, context_paths: [] as string[] };
  vi.spyOn(globalThis, "fetch").mockImplementation(async (_url, options) => {
    if (options?.method === "PUT") {
      if (failSave) return new Response(JSON.stringify({ detail: "合成保存冲突" }), { status: 409 });
      saved = JSON.parse(String(options.body));
    }
    return new Response(JSON.stringify(saved));
  });
  const onStatusChange = vi.fn();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><PremergeSetting token="" repositoryId={1} onStatusChange={onStatusChange} /></QueryClientProvider>);
  const user = userEvent.setup();
  await user.type(await screen.findByRole("textbox", { name: "仓库业务文档路径" }), "docs/draft.md");
  await user.click(screen.getByRole("button", { name: "保存合并前配置" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("保存失败：合成保存冲突");
  expect(screen.queryByText(/查询失败不代表没有数据/)).not.toBeInTheDocument();
  expect(screen.getByRole("textbox")).toHaveValue("docs/draft.md");
  failSave = false;
  await user.click(screen.getByRole("button", { name: "保存合并前配置" }));
  expect(await screen.findByText("合并前配置已保存")).toBeVisible();
  expect(onStatusChange).toHaveBeenLastCalledWith({ dirty: false, pending: false });
  expect(screen.getByRole("button", { name: "保存合并前配置" })).toBeDisabled();
});
