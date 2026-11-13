/** @description 保护发布审查的独立保存、失败恢复与接入说明；接口仅使用合成响应。 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";

import { GitLabPublicationSetting } from "../pages/GitLabPublicationSetting";
import { PremergeSetting } from "../pages/PremergeSetting";

it("合并前开关须手动保存，文档去空行且限制三份，保存后再编辑清除成功提示", async () => {
  let saved = { enabled: false, include_description: false, context_paths: [] as string[] };
  const writes: unknown[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (_url, options) => {
    if (options?.method === "PUT") { saved = JSON.parse(String(options.body)); writes.push(saved); }
    return new Response(JSON.stringify(saved));
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><PremergeSetting token="" repositoryId={1} /></QueryClientProvider>);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("switch", { name: "审查未合并 MR 的完整差异" }));
  expect(writes).toEqual([]);
  const paths = screen.getByRole("textbox", { name: "仓库业务文档路径" });
  await user.type(paths, "docs/a.md\ndocs/b.txt\ndocs/c.md\ndocs/d.md");
  expect(screen.getByRole("alert")).toHaveTextContent("最多填写 3 份");
  expect(screen.getByRole("button", { name: "保存合并前配置" })).toBeDisabled();
  await user.clear(paths);
  await user.type(paths, "docs/a.md\ndocs/a.md");
  expect(screen.getByRole("alert")).toHaveTextContent("路径不能重复");
  await user.clear(paths);
  await user.type(paths, " docs/a.md \n\ndocs/b.txt\n");
  await user.click(screen.getByRole("button", { name: "保存合并前配置" }));
  expect(await screen.findByText("合并前配置已保存")).toBeVisible();
  expect(writes).toEqual([{ enabled: true, include_description: false, context_paths: ["docs/a.md", "docs/b.txt"] }]);
  expect(paths).toHaveValue("docs/a.md\ndocs/b.txt");
  await user.click(screen.getByRole("checkbox", { name: "包含 GitLab MR 描述" }));
  expect(screen.queryByText("合并前配置已保存")).not.toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("有未保存的更改，保存后生效");
});

it("合并前说明展示已保存目标分支，切到诊断不提交草稿", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ enabled: true, include_description: true, context_paths: [] })));
  const client = new QueryClient();
  const onOpenDiagnosis = vi.fn();
  render(<QueryClientProvider client={client}><PremergeSetting token="" repositoryId={1} targetBranch="test" onOpenDiagnosis={onOpenDiagnosis} /></QueryClientProvider>);
  const user = userEvent.setup();
  await screen.findByRole("switch");
  expect(screen.getByRole("note")).toHaveTextContent("不自动发送飞书、发布 GitLab 评论或阻止合并");
  await user.click(screen.getByRole("button", { name: "自动触发需要哪些配置？" }));
  await waitFor(() => expect(screen.getByText("Merge request events")).toBeVisible());
  expect(screen.getByText("test", { exact: true })).toBeVisible();
  expect(screen.getByText(/未收到过事件的已有 MR 不会自动补扫/)).toBeVisible();
  await user.click(screen.getByRole("button", { name: "查看接入诊断" }));
  expect(onOpenDiagnosis).toHaveBeenCalledOnce();
  expect(globalThis.fetch).toHaveBeenCalledOnce();
});

it("行内发布失败保留服务端开关，保存期间冻结且不重复提交，确认后更新缓存", async () => {
  let enabled = false;
  let fail = true;
  let writes = 0;
  let finish: (() => void) | undefined;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (_url, options) => {
    if (options?.method === "PUT") {
      writes += 1;
      if (fail) return new Response(JSON.stringify({ detail: "合成保存冲突" }), { status: 409 });
      await new Promise<void>((resolve) => { finish = resolve; });
      enabled = JSON.parse(String(options.body)).enabled;
    }
    return new Response(JSON.stringify({ enabled }));
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const onStatusChange = vi.fn();
  render(<QueryClientProvider client={client}><GitLabPublicationSetting token="" repositoryId={1} onStatusChange={onStatusChange} /></QueryClientProvider>);
  const user = userEvent.setup();
  const toggle = screen.getByRole("switch", { name: "向 MR 发布可定位的评审发现" });
  await waitFor(() => expect(toggle).toBeEnabled());
  await user.click(toggle);
  expect(await screen.findByRole("alert")).toHaveTextContent("合成保存冲突");
  expect(toggle).not.toBeChecked();
  fail = false;
  await user.click(toggle);
  await waitFor(() => expect(finish).toBeTypeOf("function"));
  expect(toggle).toBeDisabled();
  expect(onStatusChange).toHaveBeenLastCalledWith({ dirty: false, pending: true });
  await user.click(toggle);
  expect(writes).toBe(2);
  await act(async () => { finish?.(); });
  expect(await screen.findByText("行内评论配置已保存")).toBeVisible();
  expect(toggle).toBeChecked();
  expect(client.getQueryData(["gitlab-publication", 1])).toEqual({ enabled: true });
  expect(onStatusChange).toHaveBeenLastCalledWith({ dirty: false, pending: false });
});
