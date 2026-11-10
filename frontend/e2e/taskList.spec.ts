/** @description 用隔离服务验证列表问题数量、直达及返回；不调用模型、GitLab 或真实业务数据。 */
import { expect, test } from "@playwright/test";

test.beforeEach(async ({ request }) => {
  await request.delete("/api/jobs/1/feedback/0");
  const job = await (await request.get("/api/jobs/1")).json();
  expect((await request.post(`/api/review-issues/${job.issue_ids["0"]}`, { data: { status: "open" } })).ok()).toBe(true);
});

for (const width of [1440, 768, 390, 320]) {
  test(`反馈数量与详情一致且整行可打开，选择不误跳转 ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 950 });
    await page.request.put("/api/jobs/1/feedback/0", { data: { verdict: "helpful" } });
    await page.goto("/jobs?page_size=25&target_branch=main");
    const row = page.getByRole("row", { name: "查看任务 1", exact: true });
    await expect(row).toContainText("有帮助 1 · 误报 0 · 忽略 0");
    await expect(row.getByLabel("反馈进度：反馈完成 1/1", { exact: true })).toBeVisible();
    await expect(row.getByLabel(/^问题处置/)).toHaveCount(0);
    await expect(row).not.toContainText("待处理");
    await expect(row).toContainText("仅当前已发现范围");
    await expect(page.getByRole("columnheader", { name: "操作", exact: true })).toHaveCount(0);
    const checkbox = row.getByRole("checkbox");
    await checkbox.check();
    await expect(page).toHaveURL("/jobs?page_size=25&target_branch=main");
    await checkbox.uncheck();
    await row.getByText("有帮助 1 · 误报 0 · 忽略 0", { exact: true }).click();
    await expect(page).toHaveURL(/\/jobs\/1\?/);
    await expect(page).not.toHaveURL(/finding_state/);
    const finding = page.getByRole("article", { name: "发现 1", exact: true });
    await expect(finding.getByRole("button", { name: "有帮助", exact: true })).toHaveAttribute("aria-pressed", "true");
    await expect(finding.getByLabel("发现 1 的处理状态", { exact: true })).toHaveText("已处理");
    await expect(finding).not.toContainText("待处理");
    await finding.getByRole("button", { name: "误报", exact: true }).click();
    await expect(finding.getByRole("button", { name: "误报", exact: true })).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("link", { name: "返回任务列表", exact: true }).click();
    await expect(page).toHaveURL("/jobs?page_size=25&target_branch=main");
    await expect(row).toContainText("有帮助 0 · 误报 1 · 忽略 0");
    await row.focus();
    await page.keyboard.press("Enter");
    await finding.getByRole("button", { name: "忽略", exact: true }).click();
    await expect(finding.getByRole("button", { name: "忽略", exact: true })).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("link", { name: "返回任务列表", exact: true }).click();
    await page.reload();
    await expect(row).toContainText("有帮助 0 · 误报 0 · 忽略 1");
    await expect(row).toContainText("反馈完成 1/1");
    await expect(row).not.toContainText("待处理");
    await page.screenshot({ path: testInfo.outputPath(`completion-open-${width}.png`), fullPage: true });
    const job = await (await page.request.get("/api/jobs/1")).json();
    expect((await page.request.post(`/api/review-issues/${job.issue_ids["0"]}`, { data: { status: "fixed" } })).ok()).toBe(true);
    await page.reload();
    await expect(row.getByLabel(/^问题处置/)).toHaveCount(0);
    await expect(row).toContainText("反馈完成 1/1");
    expect((await page.request.delete("/api/jobs/1/feedback/0")).ok()).toBe(true);
    await page.reload();
    await expect(row).toContainText("待反馈 · 剩 1 条");
    await expect(row.getByLabel(/^问题处置/)).toHaveCount(0);
    await row.getByText("待反馈 · 剩 1 条", { exact: true }).click();
    await expect(finding.getByLabel("发现 1 的处理状态", { exact: true })).toHaveText("待处理");
    await finding.getByRole("button", { name: "有帮助", exact: true }).click();
    await expect(finding.getByLabel("发现 1 的处理状态", { exact: true })).toHaveText("已处理");
    await page.reload();
    await expect(finding.getByLabel("发现 1 的处理状态", { exact: true })).toHaveText("已处理");
    await page.screenshot({ path: testInfo.outputPath(`finding-handled-${width}.png`), fullPage: true });
    await page.getByRole("link", { name: "返回任务列表", exact: true }).click();
    await expect(row).toContainText("反馈完成 1/1");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`feedback-rows-${width}.png`), fullPage: true });
  });
}

test("状态数量来自完整筛选集合，已完成可组合有待处理，失败不伪装成零", async ({ page }) => {
  await page.goto("/jobs?page_size=1");
  await expect(page.getByRole("button", { name: "全部 6", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "排队中 5", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "已完成 0", exact: true }).click();
  await expect(page.getByRole("button", { name: "全部 6", exact: true })).toBeVisible();
  await page.getByRole("combobox", { name: "发现反馈", exact: true }).click();
  await page.getByRole("option", { name: "有待反馈发现", exact: true }).click();
  await page.getByRole("button", { name: "查询", exact: true }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get("feedback_state")).toBe("pending");
  expect(new URL(page.url()).searchParams.get("status")).toBe("complete");
  await expect(page.getByRole("button", { name: "全部 1", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "部分完成 1", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "全部 1", exact: true }).click();
  await expect(page.getByRole("row", { name: "查看任务 1", exact: true })).toBeVisible();
});

for (const width of [1440, 390, 320]) {
  test(`反馈快捷筛选直接生效、可取消且保留其他条件 ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 950 });
    await page.goto("/jobs?page=2&page_size=1&target_branch=main");
    const filters = page.getByRole("group", { name: "反馈状态快捷筛选" });
    const pending = filters.getByRole("button", { name: "待反馈 1", exact: true });
    await pending.click();
    await expect(pending).toHaveAttribute("aria-pressed", "true");
    expect(new URL(page.url()).searchParams.has("page")).toBe(false);
    expect(new URL(page.url()).searchParams.get("target_branch")).toBe("main");
    expect(new URL(page.url()).searchParams.get("page_size")).toBe("1");
    await expect(page.getByRole("row", { name: "查看任务 1", exact: true })).toBeVisible();
    await page.reload();
    await expect(pending).toHaveAttribute("aria-pressed", "true");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`feedback-shortcuts-${width}.png`), fullPage: true });
    await pending.click();
    await expect(pending).toHaveAttribute("aria-pressed", "false");
    expect(new URL(page.url()).searchParams.has("feedback_state")).toBe(false);
    await page.goBack();
    await expect(pending).toHaveAttribute("aria-pressed", "true");
    await page.request.put("/api/jobs/1/feedback/0", { data: { verdict: "helpful" } });
    await page.getByRole("button", { name: "刷新任务", exact: true }).click();
    const handled = filters.getByRole("button", { name: "已反馈 1", exact: true });
    await expect(handled).toBeVisible();
    await handled.click();
    await expect(handled).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByRole("row", { name: "查看任务 1", exact: true })).toContainText("反馈完成 1/1");
    await page.getByRole("button", { name: "清空筛选", exact: true }).click();
    await expect(handled).toHaveAttribute("aria-pressed", "false");
  });
}
