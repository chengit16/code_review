/** @description 验证 HTTP 复制降级、拒绝与临时内容清理；所有令牌及浏览器能力均为合成替身。 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import * as api from "../api/client";
import { WebhookTokenCell } from "../pages/WebhookTokenCell";
import * as clipboard from "../ui/clipboard";

const originalCopy = Object.getOwnPropertyDescriptor(document, "execCommand");
afterEach(() => {
  vi.unstubAllGlobals();
  if (originalCopy) Object.defineProperty(document, "execCommand", originalCopy);
  else Reflect.deleteProperty(document, "execCommand");
});

function copyCommand(result: boolean | Error) {
  const copy = vi.fn(() => { if (result instanceof Error) throw result; return result; });
  Object.defineProperty(document, "execCommand", { configurable: true, value: copy });
  return copy;
}

it("优先原生剪贴板，不创建残留的临时节点", async () => {
  const write = vi.fn().mockResolvedValue(undefined);
  vi.stubGlobal("navigator", { clipboard: { writeText: write } });
  await clipboard.copyText("synthetic-secret");
  expect(write).toHaveBeenCalledWith("synthetic-secret");
  expect(document.querySelector('textarea[aria-label="临时复制内容"]')).toBeNull();
});

it("HTTP 无 clipboard 时降级复制，清除临时令牌并恢复焦点", async () => {
  vi.stubGlobal("navigator", {});
  const button = document.createElement("button"); document.body.append(button); button.focus();
  const copy = copyCommand(true);
  copy.mockImplementation(() => {
    expect(document.querySelector<HTMLTextAreaElement>("textarea")?.value).toBe("synthetic-secret");
    return true;
  });
  await clipboard.copyText("synthetic-secret");
  expect(copy).toHaveBeenCalledWith("copy");
  expect(document.querySelector("textarea")).toBeNull();
  expect(document.activeElement).toBe(button); button.remove();
});

it("原生权限被拒绝后可以降级，不误报未定义方法", async () => {
  vi.stubGlobal("navigator", { clipboard: { writeText: vi.fn().mockRejectedValue(new Error("合成拒绝")) } });
  const copy = copyCommand(true);
  await expect(clipboard.copyText("synthetic-secret")).resolves.toBeUndefined();
  expect(copy).toHaveBeenCalledOnce();
});

it.each([false, new Error("合成命令拒绝")])("兼容复制失败仍清理临时内容，不伪装成功", async (result) => {
  vi.stubGlobal("navigator", {}); copyCommand(result);
  await expect(clipboard.copyText("synthetic-secret")).rejects.toBeInstanceOf(Error);
  expect(document.querySelector("textarea")).toBeNull();
});

it("两种能力均缺失时提供手动选择提示", async () => {
  vi.stubGlobal("navigator", {}); Reflect.deleteProperty(document, "execCommand");
  await expect(clipboard.copyText("synthetic-secret")).rejects.toThrow("手动选择内容复制");
});

it("隐藏令牌复制失败不暴露明文，提供先查看再手动复制指引", async () => {
  vi.spyOn(api, "apiRequest").mockResolvedValue({ webhook_token: "synthetic-secret" });
  vi.spyOn(clipboard, "copyText").mockRejectedValue(new Error("合成拒绝"));
  render(<WebhookTokenCell token="" repositoryId={1} repositoryName="合成仓库" />);
  await userEvent.click(screen.getByRole("button", { name: "复制 合成仓库 的 Webhook Token" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("点击查看令牌后手动选择复制");
  expect(screen.queryByDisplayValue("synthetic-secret")).not.toBeInTheDocument();
  expect(screen.queryByText("已复制")).not.toBeInTheDocument();
});

it("主动查看后复制也经过统一兼容层，页面退出不残留令牌", async () => {
  vi.spyOn(api, "apiRequest").mockResolvedValue({ webhook_token: "synthetic-secret" });
  const copy = vi.spyOn(clipboard, "copyText").mockResolvedValue(undefined);
  const { unmount } = render(<WebhookTokenCell token="" repositoryId={1} repositoryName="合成仓库" />);
  await userEvent.click(screen.getByRole("button", { name: "查看 合成仓库 的 Webhook Token" }));
  expect(await screen.findByDisplayValue("synthetic-secret")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "复制 合成仓库 的 Webhook Token" }));
  expect(await screen.findByText("已复制")).toBeVisible();
  expect(copy).toHaveBeenCalledWith("synthetic-secret");
  unmount(); expect(screen.queryByDisplayValue("synthetic-secret")).not.toBeInTheDocument();
});
