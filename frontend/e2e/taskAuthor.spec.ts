/** @description 验证提交人在任务列表、详情及窄屏可见，旧任务明确显示缺失；仅访问隔离服务。 */
import { expect, test } from "@playwright/test";

test("列表和详情展示提交人，兼容旧任务与窄屏", async ({ page }) => {
  await page.goto("/jobs");
  await expect(page.getByRole("columnheader", { name: "提交人", exact: true })).toBeVisible();
  await expect(page.locator('td[data-label="提交人"]').filter({ hasText: "测试提交人" })).toBeVisible();
  await expect(page.locator('td[data-label="提交人"]').filter({ hasText: "未记录" }).first()).toBeVisible();
  await page.getByRole("link", { name: "查看任务 1", exact: true }).click();
  const author = page.locator(".job-summary-card > div").filter({ hasText: "提交人" });
  await expect(author).toHaveText("提交人测试提交人");
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(author).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.goto("/jobs");
  await expect(page.getByText("提交人：测试提交人", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.setViewportSize({ width: 320, height: 844 });
  await expect(page.getByText("提交人：测试提交人", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.goto("/jobs/2");
  await expect(page.locator(".job-summary-card > div").filter({ hasText: "提交人" })).toHaveText("提交人未记录");
});
