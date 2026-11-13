/** @description 隔离浏览器验证终态任务删除、键盘取消、窄屏确认和统计来源移除。 */
import { expect, test } from "@playwright/test";

test("删除确认支持取消与窄屏，服务端拒绝待投递任务", async ({ page, request }) => {
  await page.goto("/jobs/2");
  await expect(page.getByRole("button", { name: "删除任务", exact: true })).toBeDisabled();
  await page.goto("/jobs/1");
  await expect(page.locator(".page-header").getByRole("button", { name: "删除任务", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "删除任务", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "删除任务 #1" });
  await expect(dialog).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  expect((await request.get("/api/jobs/1")).status()).toBe(200);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "删除任务", exact: true }).click();
  await expect(dialog.getByText("此操作不可撤销")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: "/tmp/ocr-task-delete-confirm-390.png", fullPage: true, animations: "disabled" });
  await dialog.getByRole("button", { name: "确认删除" }).click();
  // 夹具通知仍在 pending，后端必须保护它；错误后不自动重放请求。
  await expect(dialog.getByText(/任务仍有补审、执行或通知待处理/)).toBeVisible();
  await dialog.getByRole("button", { name: "取消" }).click();
  expect((await request.get("/api/jobs/1")).status()).toBe(200);
});

test("列表删除入口可发现、取消不跳转，确认后保留筛选并移除任务", async ({ page, request }) => {
  expect((await request.post("/api/jobs/2/cancel")).status()).toBe(200);
  await page.goto("/jobs?status=cancelled");
  await expect(page.getByRole("columnheader", { name: "操作", exact: true })).toBeVisible();
  const trigger = page.getByRole("button", { name: "删除任务 2", exact: true });
  await expect(trigger).toBeVisible();
  await trigger.click();
  const dialog = page.getByRole("dialog", { name: "删除任务 #2" });
  await dialog.getByText("此操作不可撤销").click();
  await expect(page).toHaveURL(/\/jobs\?status=cancelled$/);
  await dialog.getByRole("button", { name: "取消", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  await expect(trigger).toBeFocused();
  expect((await request.get("/api/jobs/2")).status()).toBe(200);
  await trigger.click();
  await dialog.getByRole("button", { name: "确认删除" }).click();
  await expect(page).toHaveURL(/\/jobs\?status=cancelled$/);
  expect((await request.get("/api/jobs/2")).status()).toBe(404);
  const result = await request.get("/api/task-search?status=cancelled");
  expect((await result.json()).total).toBe(0);
  await expect(page.getByRole("button", { name: "删除任务 2", exact: true })).toHaveCount(0);
});

for (const width of [390, 320]) {
  test(`窄屏任务摘要直接显示删除，活动任务禁用 ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/jobs?status=partial");
    const trigger = page.getByRole("button", { name: "删除任务 1", exact: true });
    await expect(trigger).toBeVisible();
    await trigger.click();
    const dialog = page.getByRole("dialog", { name: "删除任务 #1" });
    await expect(dialog).toBeVisible();
    await dialog.getByText("此操作不可撤销").click();
    await expect(page).toHaveURL(/\/jobs\?status=partial$/);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `/tmp/ocr-delete-entry-${width}.png`, animations: "disabled" });
    await dialog.getByRole("button", { name: "取消", exact: true }).click();
    await page.goto("/jobs?status=queued");
    await expect(page.getByRole("button", { name: "删除任务 3", exact: true })).toBeDisabled();
  });
}
