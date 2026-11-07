/** @description 使用临时 API 验证并发设置持久化、冲突草稿及窄屏，不启动 Worker 或真实评审。 */
import { expect, test } from "@playwright/test";

for (const width of [1440, 320]) {
  test(`并发设置允许 1～10，保存不伪造应用状态，视口 ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto("/operations");
    const input = page.getByRole("spinbutton", { name: "模型任务并发上限（1～10）" });
    await expect(input).toBeVisible();
    await input.fill("11");
    await expect(page.getByRole("button", { name: "保存并发上限" })).toBeDisabled();
    await input.fill("10");
    await page.getByRole("button", { name: "保存并发上限" }).click();
    await expect(page.getByText("配置已保存，等待 Worker 确认应用；不代表已开始或完成评审。")).toBeVisible();
    await expect(page.getByText(/模型任务并发 10（已保存上限）/)).toBeVisible();
    await expect(page.getByText(/已应用上限 未知/)).toBeVisible();
    expect((await (await page.request.get("/api/worker-scheduler/config")).json()).model_task_concurrency).toBe(10);
    await page.reload();
    await expect(input).toHaveValue("10");
    await input.scrollIntoViewIfNeeded();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `test-results/worker-concurrency-${width}.png`, fullPage: true });
    await input.fill("1");
    await page.getByRole("button", { name: "保存并发上限" }).click();
    await expect(page.getByText("配置已保存，等待 Worker 确认应用；不代表已开始或完成评审。")).toBeVisible();
    expect(errors).toEqual([]);
  });
}

test("另一个管理员更新后保留草稿且不覆盖，明确放弃后才载入新版本", async ({ page }) => {
  await page.goto("/operations");
  const input = page.getByRole("spinbutton", { name: "模型任务并发上限（1～10）" });
  await expect(input).toHaveValue("1");
  await input.fill("7");
  const config = await (await page.request.get("/api/worker-scheduler/config")).json();
  expect((await page.request.put("/api/worker-scheduler/config", { data: { model_task_concurrency: 3, version: config.version } })).ok()).toBe(true);
  await page.getByRole("button", { name: "保存并发上限" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "并发配置已被修改" })).toBeVisible();
  await expect(input).toHaveValue("7");
  await expect(page.getByRole("button", { name: "保存并发上限" })).toBeDisabled();
  await page.getByRole("button", { name: "放弃草稿并刷新配置" }).click();
  await expect(input).toHaveValue("3");
  await input.fill("1");
  await page.getByRole("button", { name: "保存并发上限" }).click();
  await expect(page.getByText("配置已保存，等待 Worker 确认应用；不代表已开始或完成评审。")).toBeVisible();
});

for (const width of [1440, 320]) {
  test(`十个模型槽排空可见且无横向溢出，视口 ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.route("**/api/operations", async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      body.scheduler = { model_task_concurrency: 1, config_version: 3, applied_concurrency: 1,
        applied_version: 3, running_model_tasks: 10, draining: true,
        slots: Array.from({ length: 10 }, (_, index) => ({ slot_id: index ? `model:${index + 1}` : "model",
          slot_index: index + 1, lane: "model", owner: "synthetic", generation: 1,
          task_kind: "review", task_id: index + 100, repository_id: index + 1, state: "running",
          heartbeat_at: "2026-11-07 12:00:00", heartbeat_age_seconds: 1 })) };
      await route.fulfill({ response, json: body });
    });
    await page.goto("/operations");
    await expect(page.getByText(/已应用上限 1 · 持久化执行中 10/)).toContainText("正在排空");
    await expect(page.getByRole("heading", { name: /^模型评审 #/ })).toHaveCount(10);
    await expect(page.getByText(/超出上限，不再领取/)).toHaveCount(9);
    await page.getByRole("heading", { name: "模型评审 #10", exact: true }).scrollIntoViewIfNeeded();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `test-results/worker-concurrency-slots-${width}.png`, fullPage: true });
  });
}
