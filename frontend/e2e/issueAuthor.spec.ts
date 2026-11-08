/** @description 验证跟进问题提交人在桌面、窄屏与出现记录中可见；仅使用隔离服务。 */
import { expect, test } from "@playwright/test";

test("问题列表与出现记录展示提交人，窄屏无页面横向溢出", async ({ page }) => {
  await page.goto("/issues");
  await expect(page.getByRole("columnheader", { name: "提交人", exact: true })).toBeVisible();
  const author = page.getByRole("row").filter({ hasText: "测试提交人" });
  await expect(author).toBeVisible();
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 844 });
    await expect(author).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  await page.getByRole("button", { name: "查看问题 1", exact: true }).click();
  const drawer = page.getByRole("dialog", { name: "问题 #1" });
  await expect(drawer.getByText("提交人：测试提交人", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
