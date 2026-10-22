/** @description 验证单页渲染故障可恢复，且不把原始异常或密钥展示给用户。 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";

import { PageErrorBoundary } from "../ui/PageErrorBoundary";

it("渲染失败保留外层导航并允许重新挂载页面", async () => {
  vi.spyOn(console, "error").mockImplementation(() => undefined);
  let fail = true;
  function Content() { if (fail) throw new Error("不能回显的内部错误"); return <p>已恢复内容</p>; }
  render(<><nav>仍可进入其他页面</nav><PageErrorBoundary><Content /></PageErrorBoundary></>);
  expect(screen.getByRole("alert")).toHaveTextContent("后台任务不受影响");
  expect(screen.queryByText("不能回显的内部错误")).not.toBeInTheDocument();
  expect(screen.getByRole("navigation")).toBeVisible();
  fail = false;
  await userEvent.setup().click(screen.getByRole("button", { name: "重试页面" }));
  expect(screen.getByText("已恢复内容")).toBeVisible();
});
