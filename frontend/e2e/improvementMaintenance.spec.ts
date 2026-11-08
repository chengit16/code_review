/** @description 仅在 8791 临时服务验收归档策略持久化、版本冲突及桌面与窄屏状态。 */
import { expect, test } from "@playwright/test";

test("管理员保存策略可刷新读取，外部变更不覆盖草稿", async ({ page }) => {
  const original = await (await page.request.get("/api/improvement-maintenance")).json();
  await page.goto("/improvements");
  await page.getByText("维护与聊天收件箱（低频工具）").click();
  await page.locator("summary").filter({ hasText: "自动归档与台账同步" }).click();
  await page.getByLabel("启用自动归档").check();
  await page.getByLabel("连续无更新天数").fill("45");
  await page.getByRole("button", { name: "保存归档策略" }).click();
  await expect(page.getByText(/策略已保存，后台下轮执行/)).toBeVisible();
  await page.reload();
  await page.getByText("维护与聊天收件箱（低频工具）").click();
  await page.locator("summary").filter({ hasText: "自动归档与台账同步" }).click();
  await expect(page.getByLabel("连续无更新天数")).toHaveValue("45");
  await expect(page.getByLabel("启用自动归档")).toBeChecked();
  for (const width of [1280, 320]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `test-results/maintenance-${width}.png`, fullPage: true });
  }
  const current = await (await page.request.get("/api/improvement-maintenance")).json();
  expect((await page.request.put("/api/improvement-maintenance", { data: {
    enabled: original.enabled, archive_after_days: original.archive_after_days,
    expected_version: current.version,
  } })).status()).toBe(200);
  await page.getByLabel("连续无更新天数").fill("60");
  await page.getByRole("button", { name: "保存归档策略" }).click();
  await expect(page.getByRole("alert")).toContainText("策略版本已更新");
  await expect(page.getByLabel("连续无更新天数")).toHaveValue("60");
});
