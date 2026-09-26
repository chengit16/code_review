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
  // 对象名称与版本分别加载，按对象单元格和新增版本定位，避免提前选中最新修改。
  await page.getByRole("row").filter({ has: page.getByRole("cell", { name: "修改后仓库", exact: true }) }).filter({ hasText: "新增" }).getByRole("button", { name: /恢复版本/ }).click();
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

test("百练模型单价配置与评审详情用量", async ({ page }) => {
  await page.goto("/settings");
  await page.getByRole("button", { name: "新增模型" }).click();
  await page.getByLabel("配置名称").fill("百练验收模型");
  await page.getByLabel("模型标识").fill("qwen-test");
  await page.getByLabel("API Key").fill("synthetic-key");
  await page.getByLabel("输入单价（每百万 Token）").fill("2");
  await page.getByLabel("输出单价（每百万 Token）").fill("8");
  await page.getByRole("button", { name: "保存模型" }).click();
  const row = page.getByRole("row").filter({ hasText: "百练验收模型" });
  await expect(row).toContainText("百练 / DashScope");
  await expect(row).toContainText("¥2 输入 / 8 输出");
  await page.goto("/jobs/1");
  await expect(page.getByRole("heading", { name: "模型用量" })).toBeVisible();
  await expect(page.getByText("500,000")).toBeVisible();
  await expect(page.getByText("250,000")).toBeVisible();
  await expect(page.getByText("¥3.0000")).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  const reportControls = await page.locator(".attempt-filters").evaluate((section) =>
    Array.from(section.querySelectorAll("button, input")).map((element) => {
      const box = element.getBoundingClientRect();
      return { left: box.left, right: box.right, top: box.top, bottom: box.bottom };
    }),
  );
  for (const [index, first] of reportControls.entries()) {
    for (const second of reportControls.slice(index + 1)) {
      expect(first.right <= second.left || second.right <= first.left ||
        first.bottom <= second.top || second.bottom <= first.top).toBe(true);
    }
  }
  await page.screenshot({ path: "test-results/model-usage-mobile.png", fullPage: true });
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

test("详情连续导航跨页保留筛选、刷新与首尾边界", async ({ page }) => {
  const search = "?page=2&page_size=2&mr_iid=8&target_branch=main";
  await page.goto(`/jobs${search}`);
  await page.getByRole("link", { name: "查看任务 2", exact: true }).click();
  await expect(page.getByRole("heading", { name: "任务 #2", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "下一条", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "上一条", exact: true }).click();
  await expect(page.getByRole("heading", { name: "任务 #4", exact: true })).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "上一条", exact: true }).click();
  await expect(page.getByRole("heading", { name: "任务 #6", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "上一条", exact: true })).toBeDisabled();
  await page.screenshot({ path: "test-results/job-navigation-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("button", { name: "下一条", exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/job-navigation-mobile.png", fullPage: true });
  await page.getByRole("button", { name: "下一条", exact: true }).click();
  await expect(page.getByRole("heading", { name: "任务 #4", exact: true })).toBeVisible();
  await page.getByRole("link", { name: "返回任务列表" }).click();
  await expect(page).toHaveURL(`/jobs${search}`);
  await expect(page.getByRole("link", { name: "查看任务 2", exact: true })).toBeVisible();
});

test("账号模式登录与只读界面", async ({ page }) => {
  page.on("dialog", (dialog) => dialog.accept());
  await page.goto("/users");
  await page.getByRole("button", { name: "添加账号" }).click();
  await page.getByLabel("用户名").fill("browser-admin");
  await page.getByLabel("密码", { exact: true }).fill("browser-password-123");
  await page.getByRole("combobox", { name: "角色", exact: true }).click();
  await page.getByRole("option", { name: "管理员" }).click();
  await page.getByRole("button", { name: "保存账号" }).click();
  await expect(page.getByText("browser-admin", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "添加账号" }).click();
  await page.getByLabel("用户名").fill("browser-reader");
  await page.getByLabel("密码", { exact: true }).fill("browser-password-123");
  await page.getByRole("button", { name: "保存账号" }).click();
  await expect(page.getByText("browser-reader", { exact: true })).toBeVisible();
  await page.screenshot({ path: "test-results/users-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/users-mobile.png", fullPage: true });
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.getByLabel("启用多人账号登录").click();
  await expect(page.getByLabel("用户名")).toBeVisible();
  await page.getByLabel("用户名").fill("browser-reader");
  await page.getByLabel("密码", { exact: true }).fill("browser-password-123");
  await page.getByRole("button", { name: "进入管理台" }).click();
  await expect(page.getByText("browser-reader · 只读")).toBeVisible();
  await expect(page.getByRole("link", { name: "项目配置" })).toHaveCount(0);
  await page.getByRole("link", { name: "评审任务" }).click();
  await page.getByRole("link", { name: "查看任务 1" }).click();
  await expect(page.getByText("部分完成").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "重新评审" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "误报" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "上一条", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "上一条", exact: true }).click();
  await expect(page.getByRole("heading", { name: "任务 #2", exact: true })).toBeVisible();
});
