/** @description 验证改版的草稿保护、侧栏、批量范围和失败恢复；只使用隔离数据库与合成响应。 */
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

async function confirmAction(page: Page, action: () => Promise<unknown>, accept: boolean) {
  const handled = page.waitForEvent("dialog").then((dialog) => accept ? dialog.accept() : dialog.dismiss());
  await action();
  await handled;
}

test("规则草稿支持取消离开，确认放弃后才能切换", async ({ page }) => {
  await page.goto("/settings?tab=model");
  await page.getByRole("tab", { name: "审核规则" }).click();
  const include = page.getByLabel("额外纳入的路径");
  await include.fill("**/ux-draft.ts");
  await confirmAction(page, () => page.getByRole("tab", { name: "Agent 模型" }).click(), false);
  await expect(include).toHaveValue("**/ux-draft.ts");
  await expect(page).toHaveURL("/settings?tab=rules");
  await confirmAction(page, () => page.goBack(), false);
  await expect(page).toHaveURL("/settings?tab=rules");
  await confirmAction(page, () => page.getByRole("link", { name: "评审任务", exact: true }).click(), false);
  await expect(include).toHaveValue("**/ux-draft.ts");
  await confirmAction(page, () => page.getByRole("tab", { name: "Agent 模型" }).click(), true);
  await expect(page).toHaveURL("/settings?tab=model");
  await page.getByRole("button", { name: "新增模型" }).click();
  await page.getByLabel("配置名称").fill("不会保存的草稿");
  await confirmAction(page, () => page.getByRole("button", { name: "取消", exact: true }).click(), false);
  await expect(page.getByLabel("配置名称")).toHaveValue("不会保存的草稿");
  await confirmAction(page, () => page.getByRole("button", { name: "取消", exact: true }).click(), true);
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("规则保存后清除离开提醒且不保存浏览器草稿", async ({ page }) => {
  let saved = false;
  await page.route("**/api/review-rules", (route) => route.fulfill({ json: saved ? [{ repository_id: null, content: { include: ["**/*.ux.ts"], exclude: [], rules: [] }, updated_at: "2026-10-22 00:00:00" }] : [] }));
  await page.route("**/api/review-rules/global", async (route) => { saved = true; await route.fulfill({ json: { status: "saved" } }); });
  await page.goto("/settings?tab=rules");
  await page.getByLabel("额外纳入的路径").fill("**/*.ux.ts");
  await page.getByRole("button", { name: "保存规则", exact: true }).click();
  await expect(page.getByText("审核规则已保存", { exact: true })).toBeVisible();
  await expect(page.getByText("有未保存的更改，离开前请先保存。")).toHaveCount(0);
  let dialogs = 0;
  page.on("dialog", async (dialog) => { dialogs += 1; await dialog.dismiss(); });
  await page.getByRole("tab", { name: "Agent 模型" }).click();
  await expect(page).toHaveURL("/settings?tab=model");
  expect(dialogs).toBe(0);
  expect(await page.evaluate(() => Object.values(localStorage).some((value) => value.includes("**/*.ux.ts")))).toBe(false);
});

test("显式状态不会叠加冲突快捷视图", async ({ page }) => {
  await page.goto("/jobs?view=attention");
  await page.getByRole("combobox", { name: "状态", exact: true }).click();
  await page.getByRole("option", { name: "已完成", exact: true }).click();
  await page.getByRole("button", { name: "查询", exact: true }).click();
  await expect(page).toHaveURL("/jobs?status=complete");
  await expect(page.getByRole("button", { name: "待关注", exact: true })).toHaveAttribute("aria-pressed", "false");
});

test("问题摘要搜索与侧栏保留筛选，窄屏无横向溢出", async ({ page }) => {
  await page.goto("/issues?status=all");
  await expect(page.getByRole("combobox", { name: "项目", exact: true })).toContainText("全部项目");
  await expect(page.getByRole("combobox", { name: "级别", exact: true })).toContainText("全部级别");
  await page.getByLabel("搜索问题", { exact: true }).fill("app.py");
  await page.getByRole("button", { name: "搜索", exact: true }).click();
  await expect(page).toHaveURL(/q=app.py/);
  await page.getByRole("button", { name: "查看问题 1", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "问题 #1" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "出现记录" })).toBeVisible();
  await page.screenshot({ path: "test-results/issue-drawer-desktop.png" });
  await page.setViewportSize({ width: 390, height: 844 });
  const drawer = await page.getByRole("dialog", { name: "问题 #1" }).boundingBox();
  expect(drawer?.x).toBe(0);
  expect(drawer?.width).toBe(390);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/issue-drawer-mobile.png" });
  await page.getByRole("button", { name: "关闭", exact: true }).click();
  await expect(page).toHaveURL("/issues?status=all&q=app.py");
  await expect(page.getByLabel("搜索问题", { exact: true })).toHaveValue("app.py");
});

test("接入诊断基于已保存事实，打开不触发连接测试", async ({ page }) => {
  let writes = 0;
  page.on("request", (request) => { if (request.method() === "POST") writes += 1; });
  await page.goto("/repositories");
  await page.getByRole("button", { name: "编辑 验收任务项目" }).click();
  await page.getByRole("tab", { name: "接入诊断" }).click();
  await expect(page.getByRole("heading", { name: "最近接收事件" })).toBeVisible();
  await expect(page.getByText("已配置不等于调用成功", { exact: false })).toBeVisible();
  await expect(page.getByText("已生成 1 个任务，查看最新任务 →").first()).toBeVisible();
  expect(writes).toBe(0);
  await page.screenshot({ path: "test-results/repository-diagnosis-desktop.png" });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/repository-diagnosis-mobile.png" });
});

test("任务勾选重审必须确认且只提交当前页显式编号", async ({ page }) => {
  const submitted: number[][] = [];
  await page.route("**/api/jobs/batch-retry", async (route) => {
    submitted.push(route.request().postDataJSON().ids);
    await route.fulfill({ json: [{ id: 1, status: "conflict", error: "合成冲突：任务已在执行" }] });
  });
  await page.goto("/jobs?status=partial");
  await page.getByRole("checkbox", { name: "全选本页可重审任务" }).check();
  page.once("dialog", (dialog) => dialog.dismiss());
  await page.getByRole("button", { name: "重审所选任务" }).click();
  expect(submitted).toHaveLength(0);
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "重审所选任务" }).click();
  await expect(page.getByText("#1：合成冲突：任务已在执行")).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "选择任务 1", exact: true })).toBeChecked();
  expect(submitted).toEqual([[1]]);
});

test("合并前失败不冒充无发现，工件损坏不影响列表", async ({ page }) => {
  const review = { id: 900, repository_id: 1, repository_name: "合成项目", mr_iid: 3, head_sha: "a".repeat(40), status: "failed", result_json: "{broken", changed_files: "invalid", context_json: "invalid", error: "合成超时，请检查接入", created_at: "2026-10-22 01:00:00" };
  await page.route("**/api/premerge-search*", (route) => route.fulfill({ json: { items: [review], total: 1, page: 1, page_size: 25 } }));
  await page.route("**/api/premerge-reviews/900", (route) => route.fulfill({ json: review }));
  await page.goto("/premerge");
  await page.getByRole("button", { name: "详情 #900", exact: true }).click();
  await expect(page).toHaveURL("/premerge?review=900");
  await expect(page.getByText(/审查失败，无法形成完整结论/)).toBeVisible();
  await expect(page.getByText("完整审查已完成，未发现问题。")).toHaveCount(0);
  await page.getByText("变更文件与业务上下文来源", { exact: true }).click();
  await expect(page.getByText("上下文来源记录格式不可用")).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/premerge-failure-mobile.png", fullPage: true });
});

test("查询失败显示恢复入口，不伪装为空列表且重试不写数据", async ({ page }) => {
  let recovered = false;
  let writes = 0;
  page.on("request", (request) => { if (request.method() === "POST") writes += 1; });
  await page.route("**/api/premerge-search*", (route) => route.fulfill(recovered ? { json: { items: [], total: 0, page: 1, page_size: 25 } } : { status: 503, json: { detail: "合成读取失败" } }));
  await page.goto("/premerge");
  await expect(page.getByRole("alert")).toContainText("合成读取失败");
  await expect(page.getByText(/当前条件下没有审查记录/)).toHaveCount(0);
  recovered = true;
  await page.getByRole("button", { name: "重新加载" }).click();
  await expect(page.getByText(/当前条件下没有审查记录/)).toBeVisible();
  expect(writes).toBe(0);
});
