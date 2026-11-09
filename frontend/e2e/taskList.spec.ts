/** @description 用隔离服务验证列表问题数量、直达及返回；不调用模型、GitLab 或真实业务数据。 */
import { expect, test } from "@playwright/test";

test.beforeEach(async ({ request }) => {
  const job = await (await request.get("/api/jobs/1")).json();
  expect((await request.post(`/api/review-issues/${job.issue_ids["0"]}`, { data: { status: "open" } })).ok()).toBe(true);
});

test("当前任务待处理直达保留列表条件，处置后列表刷新并可重新打开", async ({ page }) => {
  await page.goto("/jobs?page_size=25&target_branch=main");
  await expect(page.getByRole("columnheader", { name: "耗时 / 尝试" })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "创建时间" })).toBeVisible();
  const queued = page.getByRole("row").filter({ has: page.getByText("任务 #6", { exact: false }) });
  await expect(queued).toContainText("待评审");
  await expect(queued).not.toContainText("全部已处置");
  await page.getByRole("link", { name: "任务 1 待处理 1 个问题", exact: true }).click();
  await expect(page).toHaveURL(/finding_state=open#job-result$/);
  await expect(page.getByRole("combobox", { name: "发现的问题处理" })).toBeVisible();
  const finding = page.getByRole("article").filter({ hasText: "示例发现" });
  await expect(finding).toBeVisible();
  await expect(finding.getByRole("button", { name: "已修复", exact: true })).toHaveCount(0);
  await finding.getByRole("link", { name: /跟进问题/ }).click();
  const drawer = page.getByRole("dialog", { name: /问题 #/ });
  await drawer.getByRole("button", { name: "已修复", exact: true }).click();
  const confirmation = page.getByRole("dialog", { name: "将问题改为已修复？", exact: true });
  await confirmation.getByRole("button", { name: "确认修复", exact: true }).click();
  await expect(confirmation).toBeHidden();
  await expect(drawer.getByRole("button", { name: "已修复", exact: true })).toHaveAttribute("aria-pressed", "true");
  await page.goBack();
  await expect(page.getByText("没有符合筛选条件的发现", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "返回任务列表" }).click();
  await expect(page).toHaveURL("/jobs?page_size=25&target_branch=main");
  const row = page.getByRole("row").filter({ hasText: "任务 #1" });
  await expect(row).toContainText("全部已处置");
  await expect(row).toContainText("修复 1");
  await page.getByRole("link", { name: "查看任务 1", exact: true }).click();
  await expect(finding).toBeVisible();
  await finding.getByRole("link", { name: /跟进问题 #\d+/ }).click();
  await drawer.getByRole("button", { name: "待处理", exact: true }).click();
  const reopen = page.getByRole("dialog", { name: "将问题改为待处理？", exact: true });
  await reopen.getByRole("button", { name: "确认恢复", exact: true }).click();
  await expect(reopen).toBeHidden();
  await expect(drawer.getByRole("button", { name: "待处理", exact: true })).toHaveAttribute("aria-pressed", "true");
  await page.goBack();
  await page.getByRole("link", { name: "返回任务列表" }).click();
  await expect(page.getByRole("link", { name: "任务 1 待处理 1 个问题", exact: true })).toBeVisible();
});

test("状态数量来自完整筛选集合，已完成可组合有待处理，失败不伪装成零", async ({ page }) => {
  await page.goto("/jobs?page_size=1");
  await expect(page.getByRole("button", { name: "全部 6", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "排队中 5", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "已完成 0", exact: true }).click();
  await expect(page.getByRole("button", { name: "全部 6", exact: true })).toBeVisible();
  await page.getByRole("combobox", { name: "问题处理", exact: true }).click();
  await page.getByRole("option", { name: "有待处理问题", exact: true }).click();
  await page.getByRole("button", { name: "查询", exact: true }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get("issue_state")).toBe("open");
  expect(new URL(page.url()).searchParams.get("status")).toBe("complete");
  await expect(page.getByRole("button", { name: "全部 1", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "部分完成 1", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "全部 1", exact: true }).click();
  await expect(page.getByRole("link", { name: "任务 1 待处理 1 个问题", exact: true })).toBeVisible();
});
