/** @description 验证精简导航、设置标签和概览统计；仅访问隔离验收服务。 */
import { expect, test } from "@playwright/test";

test("精简导航、系统设置标签与旧地址兼容", async ({ page }) => {
  await page.goto("/settings");
  const navigation = page.getByRole("navigation", { name: "主导航" });
  await expect(navigation.getByRole("link")).toHaveText([
    "项目总览", "评审任务", "评审发现", "合并前审查", "合并事件",
    "运行监控", "配置历史", "问题与改进", "首次接入引导", "项目配置", "系统设置", "访问权限",
  ]);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("系统设置");
  const model = page.getByRole("tab", { name: "Agent 模型" });
  await expect(model).toHaveAttribute("aria-selected", "true");
  await model.focus();
  await model.press("ArrowRight");
  await expect(page).toHaveURL("/settings?tab=feishu");
  await expect(page.getByRole("tab", { name: "飞书通知" })).toBeFocused();
  await expect(page.getByRole("heading", { name: "飞书配置", level: 2 })).toBeVisible();
  await page.getByRole("tab", { name: "飞书通知" }).press("End");
  await expect(page.getByRole("tab", { name: "审核规则" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("button", { name: "保存规则", exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("tab", { name: "审核规则" })).toHaveAttribute("aria-selected", "true");
  await page.goBack();
  await expect(page.getByRole("tab", { name: "飞书通知" })).toHaveAttribute("aria-selected", "true");
  await page.goto("/review-rules");
  await expect(page).toHaveURL("/settings?tab=rules");
  await page.goto("/feishu");
  await expect(page).toHaveURL("/settings?tab=feishu");
  await page.goto("/settings?tab=unknown");
  await expect(page.getByRole("tab", { name: "Agent 模型" })).toHaveAttribute("aria-selected", "true");
  await page.screenshot({ path: "test-results/system-settings-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  for (const name of ["飞书通知", "审核规则", "Agent 模型"]) {
    await page.getByRole("tab", { name }).click();
    await expect(page.getByRole("tab", { name })).toHaveAttribute("aria-selected", "true");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }
  await page.screenshot({ path: "test-results/system-settings-mobile.png", fullPage: true });
});

test("旧效果地址兼容并保留项目与时间筛选", async ({ page }) => {
  await page.route("**/api/repositories", (route) => route.fulfill({ json: [{ id: 1, name: "演示项目" }] }));
  await page.route("**/api/review-effectiveness**", (route) => route.fulfill({ json: {
    days: 7, summary: { reviews: 4, failed_reviews: 1, generated: 8, published: 4, new_issues: 3, new_still_open: 2, fixed: 1, ignored: 0, open_now: 2, feedback_marked: 0, false_positive: 0 },
    current_issues: { open_count: 2, severity_counts: { critical: 1, high: 0, medium: 1, low: 0, unclassified: 0 } },
    trend: [{ day: "2026-11-01", new: 1, fixed: 0 }], categories: [],
    projects: [{ id: 1, name: "演示项目", open_issues: 2, new_issues: 3, fixed_issues: 1, generated: 8, published: 4, reviews: 4, critical_issues: 1, high_issues: 0 }],
  } }));
  await page.goto("/effectiveness?days=7&repository_id=1");
  await expect(page).toHaveURL("/?days=7&repository_id=1");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("项目总览");
  await expect(page.getByRole("region", { name: "项目核心指标" })).toContainText("待反馈发现");
  await expect(page.getByText("更多效果分析与统计口径")).toBeVisible();
  await page.screenshot({ path: "test-results/overview-statistics-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/overview-statistics-mobile.png", fullPage: true });
});
