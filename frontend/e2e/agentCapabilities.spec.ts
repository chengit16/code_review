/** @description 在真实管理台完成 Skill、方案、项目启用、试跑和运行记录核对。 */

import { expect, test } from "@playwright/test";

test("从系统方案管理走到项目试点与双评审证据", async ({ page, request }) => {
  test.skip(process.env.OCR_BROWSER_AGENT_CAPABILITIES !== "1", "需要 Agent 能力隔离夹具");
  await page.goto("/settings?tab=agent");
  await page.getByRole("tab", { name: "Skill", exact: true }).click();
  await page.getByRole("button", { name: "创建 Skill" }).click();
  await page.getByLabel("Skill 名称").fill("订单重试检查");
  await page.getByLabel("适用文件匹配式").fill("*.py");
  await page.getByLabel("检查步骤").fill("核对重复调用是否造成重复写入。");
  await page.getByRole("button", { name: "发布 Skill 版本" }).click();
  await expect(page.getByText("#1 · 订单重试检查", { exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "评审方案" }).click();
  await page.getByRole("button", { name: "复制为草稿" }).click();
  await page.getByLabel("方案名称").fill("订单方案");
  await page.getByLabel("可选流程步骤").click();
  await page.locator(".ant-select-item-option-content:visible").filter({ hasText: "加载 Skill" }).click();
  await page.keyboard.press("Escape");
  await page.getByLabel("Skill 版本").click();
  await page.locator(".ant-select-item-option-content:visible").filter({ hasText: "订单重试检查" }).click();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "保存新草稿" }).click();
  await expect(page.getByText("#2 · 订单方案", { exact: true }).last()).toBeVisible();

  await page.goto("/repositories?repository=1&section=agent");
  await page.getByRole("switch", { name: "启用仓库试点" }).click();
  await page.getByRole("button", { name: "保存 Agent 设置" }).click();
  await expect(page.getByText("Agent 设置已保存")).toBeVisible();

  await page.goto("/settings?tab=agent");
  await page.getByRole("combobox", { name: "方案版本" }).click();
  await page.locator(".ant-select-item-option-content:visible").filter({ hasText: "订单方案" }).click();
  await page.getByRole("spinbutton", { name: "评审任务编号" }).fill("1");
  await page.getByRole("button", { name: "预览命中范围" }).click();
  await expect(page.getByRole("row", { name: /orders.py.*订单重试检查/ })).toBeVisible();
  await page.getByRole("button", { name: "试跑此方案" }).click();
  await page.getByRole("button", { name: "确认试跑" }).click();
  await expect(page).toHaveURL(/\/jobs\/1\?agent_comparison=1/);
  await page.getByText("查看本次 Agent 配置与执行").click();
  await expect(page.getByRole("row", { name: /订单重试检查.*orders.py.*命中/ })).toBeVisible();
  await expect.poll(async () => (await (await request.get("/api/jobs/1/agent-comparisons/1")).json()).status)
    .toBe("complete");

  await page.setViewportSize({ width: 390, height: 820 });
  await page.goto("/settings?tab=agent");
  await page.getByRole("combobox", { name: "方案版本" }).click();
  await page.locator(".ant-select-item-option-content:visible").filter({ hasText: "订单方案" }).click();
  await page.getByRole("button", { name: "发布方案", exact: true }).click();
  await page.getByRole("button", { name: "确认", exact: true }).click();
  await expect(page.getByText("已发布", { exact: true })).toBeVisible();
  await page.goto("/repositories?repository=1&section=agent");
  await page.getByLabel("评审方案").click();
  await page.locator(".ant-select-item-option-content:visible").filter({ hasText: "订单方案" }).click();
  await page.getByRole("button", { name: "保存 Agent 设置" }).click();
  await expect(page.getByText("当前使用 #2 · 订单方案")).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});
