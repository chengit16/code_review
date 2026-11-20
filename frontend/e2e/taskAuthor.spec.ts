/** @description 验证提交人在任务列表、详情及窄屏可见，旧任务明确显示缺失；仅访问隔离服务。 */
import { expect, test } from "@playwright/test";

test("列表和详情展示提交人，兼容旧任务与窄屏", async ({ page }) => {
  await page.goto("/jobs");
  await expect(page.getByRole("columnheader", { name: "提交人", exact: true })).toBeVisible();
  await expect(page.locator('td[data-label="提交人"]').filter({ hasText: /^测试提交人$/ })).toBeVisible();
  await expect(page.locator('td[data-label="提交人"]').filter({ hasText: "未记录" }).first()).toBeVisible();
  await page.getByRole("link", { name: "查看任务 1", exact: true }).click();
  const author = page.locator(".job-summary-card > div").filter({ hasText: "提交人" });
  await expect(author).toHaveText("提交人测试提交人");
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(author).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.goto("/jobs");
  await page.getByRole("row", { name: "查看任务 1", exact: true }).getByText("提交、耗时与通知", { exact: true }).click();
  await expect(page.getByText("提交人：测试提交人", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.setViewportSize({ width: 320, height: 844 });
  await expect(page.getByText("提交人：测试提交人", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.goto("/jobs/2");
  await expect(page.locator(".job-summary-card > div").filter({ hasText: "提交人" })).toHaveText("提交人未记录");
});

for (const [path, row] of [["/jobs", "查看任务 1"], ["/findings", "查看发现 j1:a1:c0"]]) {
  test(`${path} 下拉按提交人精确筛选、刷新回显并清除`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 320, height: 844 });
    await page.goto(`${path}?page=2&commit_author=${encodeURIComponent("测试提交")}`);
    const select = page.getByRole("combobox", { name: "筛选提交人" });
    const field = page.locator(".commit-author-select");
    await expect(field).toContainText("姓名片段：测试提交");
    await select.click();
    await expect(page.getByRole("option", { name: "测试提交人", exact: true })).toBeVisible();
    await expect(page.getByRole("option", { name: "测试提交人乙", exact: true })).toHaveCount(path === "/jobs" ? 1 : 0);
    await page.screenshot({ path: testInfo.outputPath("author-dropdown-320.png"), animations: "disabled" });
    await page.getByRole("option", { name: "测试提交人", exact: true }).click();
    if (path === "/jobs") await page.getByRole("button", { name: "查询", exact: true }).click();
    await expect.poll(() => new URL(page.url()).searchParams.get("author")).toBe("测试提交人");
    expect(new URL(page.url()).searchParams.has("page")).toBe(false);
    expect(new URL(page.url()).searchParams.has("commit_author")).toBe(false);
    await expect(page.getByRole("row", { name: row, exact: true })).toBeVisible();
    if (path === "/jobs") await expect(page.getByRole("row", { name: "查看任务 3", exact: true })).toHaveCount(0);
    await page.reload();
    await expect(field).toContainText("测试提交人");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await select.click();
    await page.getByRole("option", { name: "全部提交人", exact: true }).click();
    if (path === "/jobs") await page.getByRole("button", { name: "查询", exact: true }).click();
    await expect(field).toContainText("全部提交人");
    expect(new URL(page.url()).searchParams.has("author")).toBe(false);
  });
}
