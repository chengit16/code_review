/** @description 以隔离任务验证页面授权、独立入队确认和关闭试点。 */

import { expect, test } from "@playwright/test";

test("在任务详情启用和关闭仓库试点，启用时不产生评审", async ({ page, request }, info) => {
  test.skip(process.env.OCR_BROWSER_AGENT_PILOT !== "1", "需要页面试点隔离夹具");
  await page.setViewportSize({ width: 390, height: 820 });
  await page.goto("/jobs/1#job-agent-comparison");
  const panel = page.getByRole("region", { name: "双评审对比" });
  await expect(panel.getByRole("button", { name: "运行 Agent" })).toHaveCount(0);
  const enable = panel.getByRole("button", { name: "启用仓库试点" });
  await enable.focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", { name: "启用仓库 Agent 试点" });
  await expect(dialog.getByText("双评审合成示例", { exact: true })).toBeVisible();
  await dialog.screenshot({ path: info.outputPath("pilot-confirm-mobile.png") });
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await enable.click();
  await dialog.getByRole("button", { name: "确认启用" }).click();
  const run = panel.getByRole("button", { name: "运行 Agent" });
  await expect(run).toBeEnabled();
  const path = "/api/jobs/1/agent-comparisons";
  const enabled = await (await request.get(path)).json();
  expect(enabled.items).toEqual([]);
  expect(enabled.pilot.enabled).toBe(true);
  await run.click();
  const enqueue = page.getByRole("dialog", { name: "运行自建 Agent" });
  await expect(enqueue.getByRole("button", { name: "确认入队" })).toBeVisible();
  await page.keyboard.press("Escape");
  await page.reload();
  await expect(run).toBeEnabled();
  await panel.getByRole("button", { name: "关闭仓库试点" }).click();
  await page.getByRole("dialog", { name: "关闭仓库 Agent 试点" })
    .getByRole("button", { name: "确认关闭" }).click();
  await expect(enable).toBeVisible();
  const disabled = await (await request.get(path)).json();
  expect(disabled.pilot.enabled).toBe(false);
  expect(disabled.items).toEqual([]);
});
