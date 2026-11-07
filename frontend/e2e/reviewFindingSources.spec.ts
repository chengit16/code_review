/** @description 隔离服务验证补审出现记录的来源标签，不能被初审任务链接误导；不调用模型。 */
import { expect, test } from "@playwright/test";

for (const width of [1280, 390, 320]) {
  test(`补审出现记录明确标识候选来源 ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.route("**/api/review-issues/1", async (route) => {
      const response = await route.fetch();
      const data = await response.json();
      await route.fulfill({ response, json: {
        ...data,
        occurrences: data.occurrences.map((item: Record<string, unknown>, index: number) => ({
          ...item, recovery_id: index === 0 ? 7 : null,
        })),
      } });
    });
    await page.goto("/issues");
    await page.getByRole("button", { name: "查看问题 1", exact: true }).click();
    const drawer = page.getByRole("dialog", { name: "问题 #1" });
    const source = drawer.getByRole("link", { name: /补审 #7（候选来源）/ });
    await expect(source).toBeVisible();
    await expect(source).toHaveAttribute("href", "/jobs/1");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    if (width === 320) {
      await page.screenshot({ path: "test-results/review-finding-source-320.png", fullPage: true });
    }
  });
}
