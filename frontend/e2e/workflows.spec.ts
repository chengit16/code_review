/** @description 验证关键配置与评审流程；仅使用隔离数据库和合成凭据。 */
import { expect, test } from "@playwright/test";

test("项目新增、编辑、恢复和删除", async ({ page }) => {
  page.on("dialog", (dialog) => dialog.accept());
  await page.goto("/repositories");
  await page.getByRole("button", { name: "添加仓库" }).click();
  await page.getByLabel("仓库名称").fill("验收仓库");
  await page.getByLabel("项目数字 ID").fill("42");
  await page.getByLabel("仓库路径").fill("team/demo");
  await page.getByLabel("Clone URL").fill("https://gitlab.example.test/team/demo.git");
  await page.getByLabel("GitLab Token", { exact: true }).fill("synthetic-gitlab-token");
  await page.getByRole("button", { name: "保存仓库" }).click();
  await expect(page.getByRole("button", { name: "编辑 验收仓库" })).toBeVisible();
  await page.getByRole("button", { name: "编辑 验收仓库" }).click();
  await expect(page.getByLabel("仓库路径")).toHaveValue("team/demo");
  await page.getByLabel("仓库名称").fill("修改后仓库");
  await page.getByRole("button", { name: "保存设置" }).click();
  await expect(page.getByRole("button", { name: "编辑 修改后仓库" })).toBeVisible();
  await page.goto("/config-history");
  await page.getByRole("row").filter({ hasText: "修改后仓库" }).getByRole("button", { name: /恢复版本/ }).last().click();
  await expect(page.getByRole("status")).toContainText("配置内容已恢复");
  await page.goto("/repositories");
  await page.getByRole("button", { name: "删除 验收仓库" }).click();
  await expect(page.getByRole("button", { name: "编辑 验收仓库" })).toHaveCount(0);
});

test("飞书删除立即更新列表", async ({ page }) => {
  page.on("dialog", (dialog) => dialog.accept());
  await page.goto("/feishu");
  await page.getByRole("button", { name: "新增飞书配置" }).click();
  await page.getByLabel("配置名称").fill("验收飞书");
  await page.getByLabel("Webhook URL").fill("https://open.feishu.cn/open-apis/bot/v2/hook/synthetic");
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await page.getByRole("button", { name: "删除 验收飞书" }).click();
  await expect(page.getByRole("status")).toContainText("飞书配置已删除");
  await expect(page.getByRole("button", { name: "编辑 验收飞书" })).toHaveCount(0);
});

test("部分结果、反馈与重审", async ({ page }) => {
  await page.goto("/jobs/1");
  await expect(page.getByText("部分完成").first()).toBeVisible();
  const feedback = page.getByRole("button", { name: "误报", exact: true });
  await feedback.click();
  await expect(feedback).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "重新评审" }).click();
  await expect(page.getByText("排队中").first()).toBeVisible();
});

test("窄屏导航与布局", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/repositories");
  await expect(page.getByRole("heading", { name: "项目配置" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.getByRole("button", { name: "打开导航" }).click();
  await page.getByRole("link", { name: "飞书配置" }).click();
  await expect(page.getByRole("heading", { name: "飞书配置" })).toBeVisible();
  await page.screenshot({ path: "test-results/mobile.png", fullPage: true });
});
