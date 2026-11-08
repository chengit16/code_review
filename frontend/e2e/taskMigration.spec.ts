/** @description 第二批迁移验收：只使用临时服务与合成读写，核对未知状态、键盘、冻结编号及窄屏。 */
import { expect, test } from "@playwright/test";

for (const width of [1440, 1280, 768, 390, 320]) {
  test(`任务与接入引导可用且无页面横向溢出 ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto("/jobs");
    await expect(page.getByRole("link", { name: "查看任务 1", exact: true })).toBeVisible();
    await expect(page.getByRole("checkbox", { name: "选择任务 1", exact: true })).toBeEnabled();
    await page.getByText("更多筛选（提交、分支、时间）", { exact: true }).click();
    await expect(page.getByLabel("起始时间", { exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `/tmp/ocr-task-migration/jobs-${width}.png`, fullPage: true, animations: "disabled" });
    await page.goto("/onboarding");
    await expect(page.getByRole("link", { name: "前往模型设置" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `/tmp/ocr-task-migration/onboarding-${width}.png`, fullPage: true, animations: "disabled" });
    expect(errors).toEqual([]);
  });
}

test("任务筛选键盘提交和时间 UTC URL 可刷新、回退，勾选不跨条件恢复", async ({ page }) => {
  await page.goto("/jobs?page_size=50");
  const state = page.getByRole("combobox", { name: "问题处理", exact: true });
  await state.focus();
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Enter");
  await page.keyboard.press("Escape");
  await page.getByText("更多筛选（提交、分支、时间）", { exact: true }).click();
  await page.getByLabel("起始时间", { exact: true }).fill("2026-01-01T08:00");
  const expected = await page.evaluate(() => new Date("2026-01-01T08:00").toISOString());
  await page.getByRole("button", { name: "查询", exact: true }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get("since")).toBe(expected);
  expect(new URL(page.url()).searchParams.get("issue_state")).toBe("open");
  await page.reload();
  await expect(page.getByLabel("起始时间", { exact: true })).toHaveValue("2026-01-01T08:00");
  await page.getByRole("button", { name: "清空筛选" }).click();
  await page.getByRole("checkbox", { name: "选择任务 1", exact: true }).check();
  await page.getByRole("button", { name: /^失败(?:\s+\d+)?$/ }).click();
  await expect(page).toHaveURL("/jobs?page_size=50&status=failed");
  await page.goBack();
  await expect(page).toHaveURL("/jobs?page_size=50");
  await expect(page.getByRole("checkbox", { name: "选择任务 1", exact: true })).not.toBeChecked();
});

test("批量确认冻结编号，取消不写入、焦点返回，请求中不可重复提交", async ({ page }) => {
  let currentId = 901;
  await page.route("**/api/task-search*", async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    await route.fulfill({ json: { ...data, items: [{ ...data.items[0], id: currentId, status: "failed", active_recovery_id: null }, { ...data.items[0], id: 999, status: "queued", active_recovery_id: null }], total: 2 } });
  });
  let finish = () => {};
  const held = new Promise<void>((resolve) => { finish = resolve; });
  const submitted: number[][] = [];
  await page.route("**/api/jobs/batch-retry", async (route) => {
    submitted.push(route.request().postDataJSON().ids);
    await held;
    await route.fulfill({ json: [{ id: 901, status: "conflict", error: "合成状态变化" }] });
  });
  await page.goto("/jobs");
  await page.getByRole("checkbox", { name: "选择任务 901", exact: true }).check();
  const trigger = page.getByRole("button", { name: "重审所选任务" });
  await trigger.click();
  await expect(page.getByRole("dialog")).toContainText("#901");
  await expect(page.getByRole("combobox", { name: "问题处理", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "取消", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(trigger).toBeFocused();
  expect(submitted).toEqual([]);
  await trigger.click();
  // 模拟后台轮询改变当前页数据，确认仍只能提交打开时冻结的编号。
  currentId = 902;
  await expect(page.getByRole("checkbox", { name: "选择任务 902", exact: true })).toBeVisible({ timeout: 10000 });
  await expect(page.getByRole("dialog")).toContainText("#901");
  await page.getByRole("button", { name: "确认重审", exact: true }).click();
  await expect.poll(() => submitted.length).toBe(1);
  await expect(page.getByRole("button", { name: "确认重审", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "取消", exact: true })).toBeDisabled();
  finish();
  await expect(page.getByText("#901：合成状态变化")).toBeVisible();
  expect(submitted).toEqual([[901]]);
});

test("任务查询失败不显示无任务或零总量，重试只读", async ({ page }) => {
  let failed = true;
  let writes = 0;
  page.on("request", (request) => { if (request.method() !== "GET") writes += 1; });
  await page.route("**/api/task-search*", async (route) => {
    if (failed) await route.fulfill({ status: 503, json: { detail: "合成任务读取失败" } });
    else await route.continue();
  });
  await page.goto("/jobs");
  await expect(page.getByText("任务读取失败，状态未知")).toBeVisible();
  await expect(page.getByText("总量待确认")).toBeVisible();
  await expect(page.getByText("当前筛选下没有任务，可清空筛选或检查项目接入。")).toHaveCount(0);
  failed = false;
  await page.getByRole("button", { name: "重新读取任务" }).click();
  await expect(page.getByRole("link", { name: "查看任务 1", exact: true })).toBeVisible();
  expect(writes).toBe(0);
});

test("接入失败可单独恢复，认证失败没有默认关闭开关，打开不执行连接测试", async ({ page }) => {
  let failed = true;
  let writes = 0;
  page.on("request", (request) => { if (request.method() !== "GET") writes += 1; });
  await page.route("**/api/model-profiles", async (route) => {
    if (failed) await route.fulfill({ status: 503, json: { detail: "合成模型读取失败" } });
    else await route.continue();
  });
  await page.goto("/onboarding");
  await expect(page.getByText("模型读取失败，状态未知")).toBeVisible();
  await expect(page.getByText(/接入进度待确认/)).toBeVisible();
  failed = false;
  await page.getByRole("button", { name: "重新读取模型" }).click();
  await expect(page.locator(".setup-progress strong")).toBeVisible();
  await expect(page.getByText(/接入清单已完成/)).toHaveCount(0);
  await page.route("**/api/auth/mode", (route) => route.fulfill({ status: 503, json: { detail: "合成认证读取失败" } }));
  await page.goto("/users");
  await expect(page.getByText("认证方式读取失败，状态未知")).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "启用多人账号登录" })).toHaveCount(0);
  expect(writes).toBe(0);
});
