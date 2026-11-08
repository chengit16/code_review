/** @description 概览五档布局、可信缓存、精确导航及趋势键盘验收；仅使用隔离服务与合成响应。 */
import { expect, test } from "@playwright/test";

const snapshot = {
  summary: { repositories: 2, queued: 0, running: 0, complete: 20, attention: 3, historical_failed: 9, notification_failed: 2, total: 32 },
  todo: { events_attention: 1, premerge_failed: 2, premerge_partial: 1 },
  issue_todo: { open_count: 18, severity_counts: { critical: 1, high: 3, medium: 8, low: 4, unclassified: 2 } },
  activity: { queued: 1, running: 1, total: 2 },
  recent: [{ id: 999, repository_name: "合成项目与长名称".repeat(6), repository_id: 1, mr_iid: 7, commit_sha: "a".repeat(40), status: "partial", attempts: 2, recovery_execution_count: 1, created_at: "2026-11-07 12:00:00", timing: { cumulative_execution_seconds: 125, execution_complete: true } }],
};

for (const width of [1440, 1280, 768, 390, 320]) {
  test(`概览 ${width}px 分离工作区并保留时间尝试及所有入口`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 1000 });
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.route("**/api/overview", (route) => route.fulfill({ json: snapshot }));
    await page.goto("/?days=90&repository_id=1");
    const work = page.getByRole("region", { name: "当前工作", exact: true });
    await expect(work.getByRole("heading", { name: "运行异常" })).toBeVisible();
    await expect(work.getByText("待处置", { exact: false }).first()).toBeVisible();
    await expect(work.getByRole("link", { name: "查看合并事件需要恢复" })).toHaveAttribute("href", "/events?status=needs_attention&actionable_only=true");
    await expect(work.getByRole("link", { name: "查看合并前审查失败" })).toHaveAttribute("href", "/premerge?status=failed&latest_only=true&actionable_only=true");
    await expect(work.getByRole("link", { name: "严重 1" })).toHaveAttribute("href", "/issues?status=open&severity=critical");
    const recent = page.getByRole("region", { name: "最近评审" });
    await expect(recent.getByText("初审执行 2 分 5 秒")).toBeVisible();
    await expect(recent.getByText("初审 2 次 · 补审 1 次")).toBeVisible();
    await expect(recent.getByRole("button", { name: /2026.*Asia/ })).toBeVisible();
    const expand = page.getByRole("button", { name: "查看趋势数据" });
    await expand.focus();
    await page.keyboard.press("Enter");
    const dataTable = page.getByRole("table", { name: "问题变化数据（UTC）" });
    await expect(dataTable).toBeVisible();
    await expect(dataTable.getByRole("columnheader", { name: "起止日期（UTC）" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    const targets = await page.locator(".overview-exceptions a, .overview-work-link, .overview-header-actions .ant-btn").evaluateAll((items) => items.map((item) => item.getBoundingClientRect().height));
    expect(targets.every((height) => height >= 44)).toBe(true);
    await page.screenshot({ animations: "disabled", fullPage: true, path: testInfo.outputPath(`overview-${width}.png`) });
    expect(errors).toEqual([]);
  });
}

test("手动刷新部分失败不把缓存停止说成当前状态，延迟请求期间禁止重复", async ({ page }) => {
  let fail = false;
  await page.route("**/api/health", async (route) => {
    if (fail) await new Promise((resolve) => setTimeout(resolve, 650));
    await route.fulfill({ status: fail ? 503 : 200, json: fail ? { detail: "合成健康失败" } : { status: "ok", worker: "stopped", auth_mode: "dev" } });
  });
  await page.goto("/");
  await expect(page.getByText(/Worker 未运行，队列可能等待处理/)).toBeVisible();
  fail = true;
  const refresh = page.getByRole("button", { name: "刷新概览" });
  await refresh.click();
  await expect(refresh).toBeDisabled();
  await expect(page.getByText(/暂时无法确认 Worker 当前状态/)).toBeVisible();
  await expect(page.getByText(/Worker 未运行，队列可能等待处理/)).toHaveCount(0);
  await expect(page.getByText(/部分读取失败/)).toBeVisible();
  await expect(refresh).toBeEnabled();
  await expect(page.getByRole("heading", { name: "最近评审" })).toBeVisible();
  await expect(page.getByText(/运行数据 · 成功读取于/)).toBeVisible();
});

test("旧服务缺摘要只降级本区，读者没有管理恢复入口", async ({ page }) => {
  await page.route("**/api/auth/me", (route) => route.fulfill({ json: { id: 1, username: "合成读者", role: "reader" } }));
  await page.route("**/api/overview", (route) => route.fulfill({ json: { summary: snapshot.summary, todo: snapshot.todo, recent: [] } }));
  await page.goto("/");
  await expect(page.getByText("当前服务暂不提供汇总")).toBeVisible();
  await expect(page.getByText(/请联系管理员核对启动指引/)).toBeVisible();
  await expect(page.getByRole("link", { name: "查看运行监控" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: /已配置项目/ })).toHaveCount(0);
});

test("启用范围条件能保持筛选、清除及前进后退", async ({ page }) => {
  await page.goto("/events?status=needs_attention&actionable_only=true");
  await expect(page.getByText("当前启用范围", { exact: false }).first()).toBeVisible();
  await page.getByRole("button", { name: "查询", exact: true }).click();
  await expect(page).toHaveURL(/actionable_only=true/);
  await page.getByRole("button", { name: "清除范围筛选" }).click();
  await expect(page).not.toHaveURL(/actionable_only/);
  await page.goBack();
  await expect(page).toHaveURL(/actionable_only=true/);
  await page.goto("/premerge?status=failed&latest_only=true&actionable_only=true");
  await expect(page.getByText("当前启用范围", { exact: false }).first()).toBeVisible();
  await page.getByRole("button", { name: "重置", exact: true }).click();
  await expect(page).not.toHaveURL(/actionable_only/);
});
