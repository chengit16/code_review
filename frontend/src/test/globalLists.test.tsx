/** @description 保护列表未知计数、URL 范围、历史恢复和手机字段容器；只使用合成接口响应。 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { expect, it, vi } from "vitest";

import { DesignProvider } from "../app/DesignProvider";
import { ConfigHistoryPage } from "../pages/ConfigHistoryPage";
import { ListStatusNav } from "../ui/ListControls";
import { ListTable } from "../ui/ListTable";
import { listReturnSearch, listReturnTarget } from "../ui/listReturn";
import { useLocalList } from "../ui/useLocalList";

it("查询数量未知时显示横线，已确认的零状态不冒充未知", async () => {
  const onChange = vi.fn();
  const props = { value: "all", labels: { all: "全部", open: "待处理" }, onChange };
  const { rerender } = render(<ListStatusNav {...props} />);
  expect(screen.getByRole("button", { name: /待处理\s*—/ })).toBeVisible();
  rerender(<ListStatusNav {...props} counts={{ all: 10 }} />);
  await userEvent.click(screen.getByRole("button", { name: /待处理\s*0/ }));
  expect(onChange).toHaveBeenCalledWith("open");
});

function LocalListFixture() {
  const items = [{ id: 1, title: "甲", enabled: true }, { id: 2, title: "乙", enabled: false }];
  const list = useLocalList(items, (item) => item.title, (item) => item.enabled ? "enabled" : "disabled", "repo_");
  const location = useLocation();
  return <><p>{location.search}</p><p>已确认 {list.counts?.all} 条 / 当前 {list.filtered?.length} 条 / 第 {list.page} 页</p><button onClick={() => list.update("q", "甲")}>限定甲</button></>;
}

it("本地完整数组先搜索再计数，重置本列表页码但保留其他分区参数", async () => {
  render(<MemoryRouter initialEntries={["/?repo_status=disabled&repo_page=99&audit_page=3"]}><LocalListFixture /></MemoryRouter>);
  expect(screen.getByText("已确认 2 条 / 当前 1 条 / 第 1 页")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "限定甲" }));
  expect(screen.getByText("已确认 1 条 / 当前 0 条 / 第 1 页")).toBeVisible();
  expect(screen.getByText(/repo_q=/)).toHaveTextContent("audit_page=3");
  expect(screen.getByText(/repo_q=/)).not.toHaveTextContent("repo_page");
});

it("详情返回只接受列表白名单，不携带任意路径、令牌或过长正文", () => {
  const source = new URLSearchParams({ status: "open", page: "3", q: "合成", token: "synthetic-secret", return: "https://outside.invalid", category: "x".repeat(201) });
  const target = listReturnTarget(listReturnSearch(source));
  expect(target).toBe("/improvements?status=open&page=3&q=%E5%90%88%E6%88%90");
  expect(listReturnTarget("?list=theme_page%3D2", true)).toBe("/improvements?theme_page=2&view=themes");
});

it("表格一个单元格保留多项事实并包为一个窄屏内容区", () => {
  render(<ListTable dataSource={[{ id: 1 }]} rowKey="id" pagination={false} columns={[{ title: "事实", render: () => <><strong>未部署</strong><small>验证通过不等于生效</small></> }]} />);
  const cell = screen.getByRole("cell", { name: /未部署\s*验证通过不等于生效/ });
  expect(cell).toHaveAttribute("data-label", "事实");
  expect(cell.querySelectorAll(":scope > .list-cell-content")).toHaveLength(1);
});

function history(response: object | Error) {
  const request = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const path = String(input);
    if (init?.method === "POST") return new Response("{}");
    if (path.startsWith("/api/config-history-search")) return new Response(JSON.stringify({ total: 126, items: [{ id: 1, object_id: 8, action: "updated", actor: "合成管理员", restorable: true, created_at: "2026-11-08 00:00:00", changes: [{ field: "webhook_secret", secret: true, before: "已配置", after: "已配置" }] }] }));
    return new Response(JSON.stringify(response instanceof Error ? { detail: response.message } : response), { status: response instanceof Error ? 503 : 200 });
  });
  render(<DesignProvider><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={["/config-history?page=2&object_id=8"]}><ConfigHistoryPage token="" /></MemoryRouter></QueryClientProvider></DesignProvider>);
  return request;
}

it("配置对象查询失败保持待确认，不能推断已删除或允许恢复", async () => {
  history(new Error("合成对象读取失败"));
  expect(await screen.findByText("对象 #8 · 名称待确认")).toBeVisible();
  expect(screen.getByRole("button", { name: "恢复版本 1" })).toBeDisabled();
  expect(screen.queryByText("已删除对象 #8")).not.toBeInTheDocument();
  expect(screen.getByText(/共 126 条/)).toBeVisible();
});

it("配置历史差异不回显凭据，确认使用点击时冻结的类型和版本", async () => {
  const request = history([{ id: 8, name: "合成项目" }]);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "1 个字段 · 查看差异" }));
  expect(await screen.findByText("凭据已变更，明文不回显")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "关闭" }));
  await user.click(screen.getByRole("button", { name: "恢复版本 1" }));
  const modal = await screen.findByRole("dialog");
  expect(modal).toHaveTextContent("恢复对象 #8 到版本 #1？");
  await user.click(within(modal).getByRole("button", { name: "确定" }));
  expect(await screen.findByText("配置内容已恢复，请重新核对外部连接")).toBeVisible();
  expect(request.mock.calls.filter(([, init]) => init?.method === "POST").map(([input]) => input)).toEqual(["/api/config-history/repository/8/1/restore"]);
});
