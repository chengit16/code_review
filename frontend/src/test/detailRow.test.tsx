/** @description 保护整行详情入口的表格语义、键盘和控件隔离；仅使用合成行。 */
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";

import { DesignProvider } from "../app/DesignProvider";
import { ListTable } from "../ui/ListTable";

it("整行鼠标及 Enter 打开详情，选择框、按钮、链接、文本选择及修饰键不误导航", async () => {
  const open = vi.fn();
  render(<DesignProvider><ListTable dataSource={[{ id: 1 }]} rowKey="id" pagination={false}
    onOpenRow={open} rowLabel={() => "查看合成记录"} columns={[
      { title: "摘要", render: () => <span>合成摘要</span> },
      { title: "控件", render: () => <><label><input type="checkbox" />选择记录</label><button>独立动作</button><a href="#other">其他入口</a><details><summary>展开文本</summary>完整文本</details></> },
    ]} /></DesignProvider>);
  const row = screen.getByRole("row", { name: "查看合成记录" });
  await userEvent.click(screen.getByText("合成摘要"));
  expect(open).toHaveBeenCalledTimes(1);
  row.focus();
  await userEvent.keyboard("{Enter}");
  expect(open).toHaveBeenCalledTimes(2);
  await userEvent.click(screen.getByLabelText("选择记录"));
  await userEvent.keyboard("{Enter}");
  await userEvent.click(screen.getByRole("button", { name: "独立动作" }));
  await userEvent.click(screen.getByRole("link", { name: "其他入口" }));
  await userEvent.click(screen.getByText("展开文本"));
  fireEvent.click(row, { ctrlKey: true });
  fireEvent.keyDown(row, { key: "Enter", metaKey: true });
  const selection = vi.spyOn(window, "getSelection").mockReturnValue({ toString: () => "合成摘要" } as Selection);
  fireEvent.click(row);
  selection.mockRestore();
  expect(open).toHaveBeenCalledTimes(2);
});
