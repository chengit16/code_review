/** @description 验证精简导航、设置标签和概览统计；仅访问隔离验收服务。 */
import { expect, test } from "@playwright/test";

test("精简导航、系统设置标签与旧地址兼容", async ({ page }) => {
  await page.goto("/settings");
  const navigation = page.getByRole("navigation", { name: "主导航" });
  await expect(navigation.getByRole("link")).toHaveText([
    "运行概览", "评审任务", "待跟进问题", "合并前审查", "项目配置", "系统设置", "访问权限",
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

test("运行概览整合效果统计并保留筛选与低频报表", async ({ page }) => {
  await page.goto("/effectiveness?days=7&repository_id=1");
  await expect(page).toHaveURL("/?days=7&repository_id=1");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("运行概览");
  const statistics = page.getByRole("region", { name: "评审效果", exact: true });
  await expect(statistics.getByRole("region", { name: "评审效果摘要" })).toBeVisible();
  await expect(statistics.getByText("人工标记已修复", { exact: true })).toBeVisible();
  await expect(statistics.getByText(/不代表系统已验证代码修复/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "项目对比" })).not.toBeVisible();
  await statistics.getByText("展开类别与项目统计", { exact: true }).click();
  await expect(page.getByRole("heading", { name: "项目对比" })).toBeVisible();
  await statistics.getByRole("combobox", { name: "项目", exact: true }).click();
  await page.getByRole("option", { name: "全部项目" }).click();
  await expect(page).toHaveURL("/?days=7");
  await statistics.getByRole("combobox", { name: "时间", exact: true }).click();
  await page.getByRole("option", { name: "近 90 天" }).click();
  await expect(page).toHaveURL("/?days=90");
  await page.reload();
  await expect(statistics.getByRole("combobox", { name: "时间", exact: true })).toContainText("近 90 天");
  await page.screenshot({ path: "test-results/overview-statistics-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/overview-statistics-mobile.png", fullPage: true });
});
