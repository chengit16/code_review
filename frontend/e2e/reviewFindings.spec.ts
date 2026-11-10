/** @description 统一发现列表的真实隔离写入、撤销、首页一致性，以及桌面窄屏批量确认；不访问正式实例。 */
import { expect, test } from "@playwright/test";

for (const width of [1440, 390, 320]) {
  test(`统一发现 ${width}px：反馈、撤销与批量写入在首页和任务中一致`, async ({ page, baseURL }, testInfo) => {
    expect(new URL(baseURL ?? "").port).toBe("8791");
    await page.setViewportSize({ width, height: 1000 });
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.request.delete("/api/jobs/1/feedback/0");
    await page.goto("/findings");
    await expect(page.getByRole("heading", { name: "评审发现", exact: true })).toBeVisible();
    await expect(page.getByText("共 1 条发现", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "示例发现", exact: true }).click();
    const drawer = page.getByRole("dialog", { name: "评审发现详情" });
    await expect(drawer).toContainText("j1:a1:c0");
    await drawer.getByRole("button", { name: "有帮助", exact: true }).click();
    await expect(drawer.getByRole("button", { name: "有帮助" })).toHaveAttribute("aria-pressed", "true");
    await expect(drawer).toContainText("已处理");
    await drawer.getByRole("button", { name: "有帮助", exact: true }).click();
    await expect(drawer.getByRole("button", { name: "有帮助" })).toHaveAttribute("aria-pressed", "false");
    await page.keyboard.press("Escape");
    await expect(drawer).not.toBeVisible();
    const row = page.getByRole("row", { name: "查看发现 j1:a1:c0", exact: true });
    await row.getByRole("checkbox").check();
    await page.getByRole("button", { name: "批量反馈", exact: true }).click();
    const confirm = page.getByRole("dialog", { name: "确认将 1 条发现反馈为“有帮助”？" });
    await expect(confirm).toContainText("版本 1/0");
    await expect(confirm).toContainText("j1:a1:c0");
    await confirm.getByRole("button", { name: "确认反馈" }).click();
    await expect(page.getByText("批量反馈成功 1 条，失败 0 条。", { exact: true })).toBeVisible();
    await expect(page.getByText("共 0 条发现", { exact: true })).toBeVisible();
    await page.goto("/?days=7&repository_id=1");
    await page.getByRole("link", { name: "查看有帮助 1 条发现" }).click();
    await expect(page).toHaveURL(/feedback=helpful/);
    await expect(page).toHaveURL(/handling=all/);
    await expect(page.getByText("共 1 条发现", { exact: true })).toBeVisible();
    await expect(page.getByRole("row", { name: "查看发现 j1:a1:c0", exact: true })).toContainText("已处理");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ fullPage: true, animations: "disabled", path: testInfo.outputPath(`review-findings-${width}.png`) });
    await page.goto("/jobs/1");
    const finding = page.getByRole("article", { name: "发现 1", exact: true });
    await expect(finding.getByRole("button", { name: "有帮助" })).toHaveAttribute("aria-pressed", "true");
    await expect(finding.getByLabel("发现 1 的处理状态", { exact: true })).toHaveText("已处理");
    expect(errors).toEqual([]);
    await page.request.delete("/api/jobs/1/feedback/0");
  });
}

for (const width of [1440, 390, 320]) {
  test(`统一发现长摘要 ${width}px：连续字符、长项目与文件路径均不撑开列表`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 1000 });
    const item = { finding_id: "j1:a1:c0", job_id: 1, repository_id: 1, repository_name: "合成超长项目名称".repeat(8), source_attempt: 1, revision: 0, recovery_id: null, comment_index: 0, generated_at: "2026-11-09 00:00:00", category: "security", severity: "high", path: "src/deeplyNestedFolder/".repeat(6) + "candidate.ts", excerpt: "连续描述".repeat(30) + "LongUnbrokenSyntheticIdentifier".repeat(2), issue_id: 1, issue_status: "open", feedback: "unmarked", handling: "pending", commit_author: "合成提交作者".repeat(8) };
    await page.route("**/api/review-findings?**", (route) => route.fulfill({ json: { items: [item], total: 1, page: 1, page_size: 25 } }));
    await page.goto("/findings");
    const summary = page.getByRole("button", { name: item.excerpt, exact: true });
    await expect(summary).toBeVisible();
    expect(await summary.evaluate((element) => getComputedStyle(element).whiteSpace)).toBe("normal");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`review-findings-long-${width}.png`), fullPage: true, animations: "disabled" });
  });
}
