/** @description 全站说明精简回归；仅访问隔离服务，核对标题、核心控件与三档视口，不调用真实外部服务。 */
import { expect, test } from "@playwright/test";

for (const width of [1440, 390, 320]) {
  test(`全站 ${width}px 用标题与控件表达常用操作`, async ({ page }, testInfo) => {
    test.setTimeout(90000);
    await page.setViewportSize({ width, height: 1000 });
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    const routes = [
      ["/", "项目总览", "刷新概览"],
      ["/jobs", "评审任务", "刷新任务"],
      ["/findings", "评审发现", "刷新发现"],
      ["/issues", "历史问题与修复记录", "刷新问题"],
      ["/events", "合并事件", "刷新事件"],
      ["/repositories", "项目配置", "添加仓库"],
      ["/settings", "系统设置", "新增模型"],
      ["/settings?tab=feishu", "系统设置", "新增飞书配置"],
      ["/settings?tab=rules", "系统设置", "保存规则"],
      ["/users", "访问权限", "添加账号"],
      ["/operations", "运行监控", "刷新当前视图"],
      ["/operations?tab=performance", "运行监控", "刷新当前视图"],
      ["/operations?tab=alerts", "运行监控", "刷新当前视图"],
      ["/operations?tab=maintenance", "运行监控", "刷新当前视图"],
      ["/improvements", "问题与改进", "新增记录"],
      ["/improvements?view=themes", "问题与改进", "新增优化主题"],
      ["/improvements?view=summary", "问题与改进", "刷新统计"],
      ["/onboarding", "项目接入清单", "返回项目配置"],
    ];
    for (const [index, [route, heading, action]] of routes.entries()) {
      await page.goto(route);
      await expect(page.getByRole("heading", { name: heading, level: 1, exact: true })).toBeVisible();
      await expect(page.getByRole(route === "/onboarding" ? "link" : "button", { name: action, exact: true })).toBeVisible();
      await expect(page.locator(".page-header > div > p")).toHaveCount(0);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), route).toBe(true);
      await page.screenshot({ path: testInfo.outputPath(`page-${index}-${width}.png`), animations: "disabled" });
    }
    await page.goto("/");
    await expect(page.getByRole("region", { name: "评审反馈" })).toBeVisible();
    await expect(page.getByText(/成功读取于|评审价值、反馈质量|悬停、聚焦或点击/)).toHaveCount(0);
    await expect(page.locator(".overview-kpis small, .quality-legend, .quality-share-caption")).toHaveCount(0);
    await page.screenshot({ path: testInfo.outputPath(`overview-clean-${width}.png`), animations: "disabled", fullPage: true });
    expect(errors).toEqual([]);
  });
}
