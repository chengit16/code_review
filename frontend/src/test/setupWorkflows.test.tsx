/** @description 独立目标测试确认和元数据旧响应保护；合成网络不访问真实模型、GitLab 或飞书。 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ConfigProvider } from "antd";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";

import { DesignProvider } from "../app/DesignProvider";
import { RepositoryMetadataLookup } from "../pages/RepositoryMetadataLookup";
import { ConnectionChecks } from "../ui/ConnectionChecks";

it("独立模型测试须确认，取消无写入，确认携带目标且不切换默认", async () => {
  const writes: { url: string; body: unknown }[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url, options) => {
    if (options?.method === "POST") writes.push({ url: String(url), body: JSON.parse(String(options.body)) });
    return new Response(JSON.stringify(options?.method === "POST" ? { id: 1, status: "queued" } : []));
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<ConfigProvider theme={{ token: { motion: false } }}><DesignProvider><QueryClientProvider client={client}><ConnectionChecks token="" kinds={["model"]} modelProfileId={7} /></QueryClientProvider></DesignProvider></ConfigProvider>);
  await userEvent.click(screen.getByRole("button", { name: "测试 模型" }));
  expect(await screen.findByText(/可能产生费用/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "取消" }));
  expect(writes).toEqual([]);
  await userEvent.click(screen.getByRole("button", { name: "测试 模型" }));
  await userEvent.click(await screen.findByRole("button", { name: "确认测试" }));
  await waitFor(() => expect(writes).toEqual([{ url: "/api/connection-checks", body: { kind: "model", repository_id: null, model_profile_id: 7 } }]));
});

it("未关联项目的通知可以测试，打开页面无写入并明确真实消息", async () => {
  const writes: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (_url, options) => {
    if (options?.method === "POST") writes.push(String(options.body));
    return new Response("[]");
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<DesignProvider><QueryClientProvider client={client}><ConnectionChecks token="" kinds={["feishu"]} notificationTargetId={8} /></QueryClientProvider></DesignProvider>);
  expect(writes).toEqual([]);
  await userEvent.click(screen.getByRole("button", { name: "测试 飞书" }));
  await waitFor(() => expect(screen.getAllByText("向真实群发送测试消息？").some((element) => element.closest(".ant-modal-confirm-title"))).toBe(true));
  await userEvent.click(screen.getByRole("button", { name: "取消" }));
  expect(writes).toEqual([]);
});

it("元数据等待时编辑任一草稿字段，旧结果不得回填", async () => {
  let complete: (value: Response) => void = () => {};
  const fetch = vi.spyOn(globalThis, "fetch").mockImplementation(async (_url, options) => {
    if (options?.method === "POST") return new Promise<Response>((resolve) => { complete = resolve; });
    return new Response("{}");
  });
  const onResolved = vi.fn();
  const props = { token: "", remoteUrl: "https://gitlab.test/a/b", gitlabToken: "synthetic", onResolved };
  const { rerender } = render(<RepositoryMetadataLookup {...props} draftVersion={0} />);
  await userEvent.click(screen.getByRole("button", { name: "获取项目资料" }));
  expect(fetch).toHaveBeenCalledTimes(1);
  rerender(<RepositoryMetadataLookup {...props} draftVersion={1} />);
  await act(async () => { complete(new Response(JSON.stringify({ id: 1 }))); });
  expect(onResolved).not.toHaveBeenCalled();
  expect(screen.queryByText(/资料已带出/)).toBeNull();
});
