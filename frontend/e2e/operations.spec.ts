/** @description 隔离服务验证 Ant Design 分区、草稿和查询生命周期；清理仅使用合成响应，不执行真实删除。 */
import { expect, test } from "@playwright/test";

for (const width of [1440, 1024, 768, 375, 320]) {
  test(`四分区与十槽在桌面窄屏可用 ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.route("**/api/operations", async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      body.execution_jobs = { queued: 2, running: 3 };
      body.jobs = { queued: 90, running: 99, failed: 4, partial: 1 };
      body.scheduler = { model_task_concurrency: 2, config_version: 2, applied_concurrency: 2, applied_version: 2, running_model_tasks: 10, draining: true,
        slots: Array.from({ length: 10 }, (_, index) => ({ slot_id: `model:${index + 1}`, slot_index: index + 1,
          lane: "model", owner: "synthetic", generation: 1, task_kind: "review", task_id: index + 100,
          repository_id: index + 1, state: "running", heartbeat_at: "2026-11-07 12:00:00", heartbeat_age_seconds: index === 9 ? 20 : 1 })) };
      body.performance_7d = [{ repository_id: 1, status: "complete", size_bucket: "1-10", count: 2, execution_samples: 0,
        execution_p50_seconds: null, execution_p95_seconds: null, queue_samples: 1, queue_p50_seconds: 3,
        queue_p95_seconds: 3, timeout_count: 1, timeout_rate: .5, retry_count: 1, unknown_usage_count: 1, known_tokens: 15 }];
      await route.fulfill({ response, json: body });
    });
    const reads: string[] = [];
    page.on("request", (request) => { if (request.method() === "GET") reads.push(new URL(request.url()).pathname); });
    await page.goto("/operations");
    await expect(page.getByRole("spinbutton", { name: "模型任务并发上限（1～10）" })).toBeVisible();
    await expect(page.getByRole("spinbutton", { name: "模型任务并发上限（1～10）" })).toHaveCSS("height", "40px");
    expect(reads.some((path) => /maintenance|alerts|reconciliation|audit-logs/.test(path))).toBe(false);
    await expect(page.locator(".operations-number").first()).toHaveText("2");
    await expect(page.locator(".operations-number").nth(1)).toHaveText("3");
    await expect(page.getByText(/已应用上限 2 · 持久化执行中 10/)).toContainText("排空");
    await expect(page.getByRole("heading", { name: /^模型评审 #/ })).toHaveCount(10);
    await page.screenshot({ path: `test-results/operations-runtime-${width}.png`, fullPage: true });
    for (const name of ["性能分析", "告警与通知", "维护与审计", "运行与并发"]) {
      await page.getByRole("tab", { name }).click();
      await expect(page.getByRole("tab", { name })).toHaveAttribute("aria-selected", "true");
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      if (name === "性能分析") {
        await expect(page.getByText("无有效样本")).toBeVisible();
        const projectFilter = page.getByRole("combobox", { name: "性能项目筛选" });
        await projectFilter.focus();
        await page.keyboard.press("ArrowDown");
        await page.keyboard.press("Enter");
        await expect(page).toHaveURL(/performance_repository=1/);
        await page.keyboard.press("Escape");
        await expect(page.getByRole("listbox")).toBeHidden();
        await page.getByRole("button", { name: "展开行" }).click();
        await expect(page.getByText("已知 Token 下限 15")).toBeVisible();
      }
      await page.screenshot({ path: `test-results/operations-${name}-${width}.png`, fullPage: true });
    }
    await expect(page).toHaveURL(/tab=runtime/);
    await page.goBack();
    await expect(page.getByRole("tab", { name: "维护与审计" })).toHaveAttribute("aria-selected", "true");
    await page.reload();
    await expect(page.getByRole("tab", { name: "维护与审计" })).toHaveAttribute("aria-selected", "true");
    expect(errors).toEqual([]);
  });
}

test("草稿跨分区、后台刷新保留，隐藏分区停止轮询", async ({ page }) => {
  await page.clock.install();
  const reads: string[] = [];
  page.on("request", (request) => { if (request.method() === "GET") reads.push(new URL(request.url()).pathname); });
  await page.goto("/operations");
  const input = page.getByRole("spinbutton", { name: "模型任务并发上限（1～10）" });
  await input.fill("7");
  await page.getByRole("tab", { name: "告警与通知" }).click();
  const threshold = page.getByRole("spinbutton", { name: "队列等待阈值（分钟）" });
  await threshold.fill("71");
  await page.getByRole("button", { name: "刷新当前视图" }).click();
  await expect(threshold).toHaveValue("71");
  const before = reads.filter((path) => path === "/api/worker-scheduler/config").length;
  await page.clock.fastForward(31000);
  expect(reads.filter((path) => path === "/api/worker-scheduler/config")).toHaveLength(before);
  await page.getByRole("tab", { name: "运行与并发" }).click();
  await expect(input).toHaveValue("7");
  await expect(page.getByRole("button", { name: "保存并发上限" })).toBeEnabled();
  await page.getByRole("tab", { name: "告警与通知" }).click();
  await expect(threshold).toHaveValue("71");
});

test("清理必须二次确认，取消不写入，确认使用冻结保留天数并恢复焦点", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 850 });
  const writes: string[] = [];
  await page.route("**/api/maintenance/preview?*", (route) => route.fulfill({ json: { count: 2, bytes: 1024 } }));
  await page.route("**/api/maintenance/prune?*", (route) => { writes.push(route.request().url()); return route.fulfill({ json: { count: 2 } }); });
  await page.goto("/operations?tab=maintenance");
  const trigger = page.getByRole("button", { name: "清理工件", exact: true });
  await expect(trigger).toBeEnabled();
  await trigger.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("超过 90 天");
  await expect(dialog.getByRole("button", { name: "取消" })).toBeVisible();
  await dialog.getByRole("button", { name: "取消" }).click();
  await expect(dialog).toBeHidden();
  expect(writes).toEqual([]);
  await expect(trigger).toBeFocused();
  await trigger.click();
  await dialog.getByRole("button", { name: "确认清理", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "已清理 2 个旧工件目录" })).toBeVisible();
  expect(writes).toHaveLength(1);
  expect(writes[0]).toContain("days=90");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
