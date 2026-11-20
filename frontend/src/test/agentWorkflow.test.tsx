/** @description 验证定位下一页失败时，已核对页面仍保留完成状态。 */

import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { AgentWorkflow } from "../pages/agentComparison/AgentWorkflow";

test("下一页定位失败独立展示，不更改已核对页的状态", () => {
  render(<AgentWorkflow status="failed" steps={[
    "request · 模型请求块 1，起始 0",
    "read · orders.py 块 1 [0,8)/8，续读位置 无",
    "verified · 本页已核对，保留 0 条发现",
    "failed · 差异页请求超出当前计划",
    "finish · invalid_read_request",
  ]} />);

  expect(screen.getByRole("button", { name: /orders.py.*已核对/ })).toBeVisible();
  expect(screen.getByText("差异页请求超出当前计划")).toBeVisible();
});
