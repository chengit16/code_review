/** @description 全站筛选前置、无重复标签、按日查询和配置卡片验收；仅访问隔离后端与合成数据。 */
import { expect, test } from "@playwright/test";

for (const width of [1440, 768, 390, 320]) {
  test(`筛选与配置卡片统一，桌面窄屏无溢出 ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 1000 });
    const errors: string[] = [], writes: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("request", (request) => { if (!["GET", "HEAD"].includes(request.method())) writes.push(request.url()); });
    await page.route("**/api/model-profiles", (route) => route.fulfill({ json: [
      { id: 91, name: "主评审模型", model: "code-review-primary", provider: "openai", enabled: 1, has_api_key: true, base_url: "https://models.example.test/v1", price_currency: "CNY", input_price_per_million: "2", output_price_per_million: "8" },
      { id: 92, name: "备用评审模型", model: "qwen-code-review-alternative-with-long-name", provider: "dashscope", enabled: 0, has_api_key: true, base_url: "", price_currency: "CNY" },
    ] }));
    await page.route("**/api/notification-targets", (route) => route.fulfill({ json: [
      { id: 81, name: "Web 端评审通知", repository_count: 1, has_signing_secret: true },
      { id: 82, name: "移动端评审通知", repository_count: 0, has_signing_secret: false },
    ] }));
    const views = [
      ["/jobs", ".jobs-filter-form"], ["/improvements", ".list-toolbar"], ["/improvements?view=themes", ".list-toolbar"],
      ["/repositories", ".list-toolbar"], ["/config-history", ".list-toolbar"], ["/events", "form.list-toolbar"],
      ["/issues", ".issue-filter-grid"], ["/findings", ".finding-list-filters"], ["/users", ".list-toolbar"],
    ];
    for (const [path, selector] of views) {
      await page.goto(path, { waitUntil: "domcontentloaded" });
      const toolbar = page.locator(selector).first();
      await expect(toolbar).toBeVisible();
      await expect(page.getByText(/更多筛选/)).toHaveCount(0);
      await expect(toolbar.locator("label")).toHaveCount(0);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), path).toBe(true);
      if (path === "/jobs") {
        await expect(page.getByLabel("MR IID", { exact: true })).toHaveCount(0);
        await expect(page.getByLabel("提交 SHA", { exact: true })).toHaveCount(0);
        await expect(page.getByLabel("飞书通知筛选", { exact: true })).toHaveCount(0);
        await expect(page.getByLabel("创建日期", { exact: true })).toHaveAttribute("placeholder", "创建日期");
        await expect(toolbar.locator(".ant-picker")).toHaveCount(1);
        await expect(toolbar.locator('input[type="datetime-local"]')).toHaveCount(0);
        if (width >= 1280) {
          const tops = await toolbar.locator(".jobs-filter-main > *").evaluateAll((elements) => elements.map((element) => element.getBoundingClientRect().top));
          expect(Math.max(...tops) - Math.min(...tops)).toBeLessThanOrEqual(1);
        }
      }
      if ([1440, 320].includes(width) && ["/jobs", "/improvements", "/events"].includes(path)) await page.screenshot({ path: testInfo.outputPath(`${path.slice(1)}-${width}.png`), fullPage: true, animations: "disabled" });
    }
    await page.goto("/settings?tab=model");
    const models = page.getByRole("region", { name: "模型配置列表", exact: true });
    await expect(models.getByRole("article")).toHaveCount(2);
    const main = page.getByRole("article", { name: "模型 主评审模型" });
    await expect(main.getByRole("button", { name: "删除 主评审模型" })).toBeDisabled();
    expect((await main.boundingBox())?.height).toBeLessThan(width >= 768 ? 280 : 360);
    await main.getByText("端点与计价", { exact: true }).click();
    await expect(main).toContainText("输入 2 / 输出 8");
    await expect(page.getByRole("table")).toHaveCount(0);
    await expect(page.locator(".list-toolbar label")).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`model-cards-${width}.png`), fullPage: true, animations: "disabled" });
    await page.getByRole("textbox", { name: "搜索配置" }).fill("备用");
    await page.getByRole("button", { name: "搜索", exact: true }).click();
    await expect(models.getByRole("article")).toHaveCount(1);
    await expect(page.getByRole("article", { name: "模型 备用评审模型" })).toBeVisible();
    await page.getByRole("article").getByRole("button", { name: "测试 模型", exact: true }).click();
    await expect(page.getByRole("dialog")).toContainText("可能产生费用");
    await page.getByRole("dialog").getByRole("button", { name: "取消", exact: true }).click();
    await page.goto("/settings?tab=feishu");
    const channels = page.getByRole("region", { name: "飞书通道列表", exact: true });
    await expect(channels.getByRole("article")).toHaveCount(2);
    for (const card of await channels.getByRole("article").all()) expect((await card.boundingBox())?.height).toBeLessThan(width >= 768 ? 230 : 280);
    await expect(page.getByRole("table")).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`feishu-cards-${width}.png`), fullPage: true, animations: "disabled" });
    await page.getByRole("article", { name: "飞书通道 Web 端评审通知" }).getByRole("button", { name: "测试 飞书", exact: true }).click();
    await expect(page.getByRole("dialog")).toContainText("真实测试消息");
    await page.getByRole("dialog").getByRole("button", { name: "取消", exact: true }).click();
    expect(writes).toEqual([]); expect(errors).toEqual([]);
  });
}

test("单个创建日期查询整天、刷新回显并支持清空", async ({ page }) => {
  await page.goto("/jobs?page_size=50");
  const date = page.getByLabel("创建日期", { exact: true });
  await date.fill("2026-11-13"); await date.press("Tab");
  await page.getByRole("button", { name: "查询", exact: true }).click();
  const expected = await page.evaluate(() => ({ since: new Date(2026, 10, 13).toISOString(), until: new Date(2026, 10, 13, 23, 59, 59, 999).toISOString() }));
  await expect.poll(() => new URL(page.url()).searchParams.get("until")).toBe(expected.until);
  expect(new URL(page.url()).searchParams.get("since")).toBe(expected.since);
  await page.reload(); await expect(date).toHaveValue("2026-11-13");
  await expect(page.getByRole("button", { name: "移除创建日期筛选", exact: true })).toHaveCount(1);
  await date.fill(""); await date.press("Tab");
  await page.getByRole("button", { name: "查询", exact: true }).click();
  await expect(page).toHaveURL("/jobs?page_size=50");
  await expect(date).toHaveValue("");
});
