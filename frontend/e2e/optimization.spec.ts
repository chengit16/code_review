/** @description 验证项目草稿、逐项批量结果、分页和历史收纳；只读隔离服务，写入均使用合成响应。 */
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

async function openRepository(page: Page) {
  await page.goto("/repositories");
  await page.getByRole("button", { name: "编辑 验收任务项目" }).click();
}

async function cancelDiscard(page: Page, action: () => Promise<unknown>) {
  const handled = page.waitForEvent("dialog").then((dialog) => dialog.dismiss());
  await action();
  await handled;
}

test("项目页签保留草稿，关闭及路由离开支持取消", async ({ page }) => {
  await page.goto("/jobs");
  await page.getByRole("link", { name: "项目配置", exact: true }).click();
  await page.getByRole("button", { name: "编辑 验收任务项目" }).click();
  await page.getByRole("tab", { name: "评审参数" }).click();
  await page.getByLabel("超时（秒）").fill("321");
  await page.getByRole("tab", { name: "发布审查" }).click();
  await page.getByRole("textbox", { name: "仓库业务文档路径" }).fill("docs/unsaved.md");
  await page.getByRole("tab", { name: "基础接入" }).click();
  await page.getByLabel("仓库名称").fill("未保存的项目名");
  await page.getByRole("tab", { name: "评审参数" }).click();
  await expect(page.getByLabel("超时（秒）")).toHaveValue("321");
  await page.getByRole("tab", { name: "发布审查" }).click();
  await expect(page.getByRole("textbox", { name: "仓库业务文档路径" })).toHaveValue("docs/unsaved.md");
  await cancelDiscard(page, () => page.getByRole("button", { name: "关闭", exact: true }).click());
  await expect(page.getByRole("dialog")).toBeVisible();
  await cancelDiscard(page, () => page.goBack());
  await expect(page).toHaveURL("/repositories");
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "关闭", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("button", { name: "编辑 验收任务项目" }).click();
  await expect(page.getByLabel("仓库名称")).toHaveValue("验收任务项目");
});

test("保存评审参数不会丢弃其他页签草稿，重新编辑不显示过期成功提示", async ({ page }) => {
  let limits = { model_profile_id: null, timeout_seconds: 120, max_files: null, max_tokens_budget: null };
  await page.route("**/api/repositories/1/limits", async (route) => {
    if (route.request().method() === "PUT") limits = route.request().postDataJSON();
    await route.fulfill({ json: limits });
  });
  await openRepository(page);
  await page.getByLabel("仓库名称").fill("保留的基础草稿");
  await page.getByRole("tab", { name: "评审参数" }).click();
  await page.getByLabel("超时（秒）").fill("456");
  await page.getByRole("button", { name: "保存评审参数" }).click();
  await expect(page.getByText("评审参数已保存", { exact: true })).toBeVisible();
  await page.getByLabel("超时（秒）").fill("457");
  await expect(page.getByText("评审参数已保存", { exact: true })).toHaveCount(0);
  await page.getByRole("tab", { name: "基础接入" }).click();
  await expect(page.getByLabel("仓库名称")).toHaveValue("保留的基础草稿");
  await cancelDiscard(page, () => page.getByRole("button", { name: "关闭", exact: true }).click());
});

test("保存基础接入不关闭窗口或丢失评审参数草稿", async ({ page }) => {
  const response = await page.request.get("/api/repositories");
  const repositories = await response.json();
  const repository = repositories.find((item: { id: number }) => item.id === 1);
  await page.route("**/api/repositories/preflight?*", (route) => route.fulfill({ json: { status: "ok" } }));
  await page.route("**/api/repositories/1", (route) => route.fulfill({ json: { ...repository, ...route.request().postDataJSON() } }));
  await openRepository(page);
  await page.getByRole("tab", { name: "评审参数" }).click();
  await page.getByLabel("超时（秒）").fill("777");
  await page.getByRole("tab", { name: "基础接入" }).click();
  await page.getByLabel("仓库名称").fill("合成保存名称");
  await page.getByLabel("仓库路径", { exact: true }).fill("team/fixture");
  await page.getByRole("button", { name: "保存设置" }).click();
  await expect(page.getByText("基础接入配置已保存", { exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "评审参数" }).click();
  await expect(page.getByLabel("超时（秒）")).toHaveValue("777");
  await cancelDiscard(page, () => page.getByRole("button", { name: "关闭", exact: true }).click());
});

test("配置读取失败不能保存默认值，重新加载后才恢复操作", async ({ page }) => {
  let failed = true;
  let writes = 0;
  for (const suffix of ["premerge", "gitlab-publication"]) {
    await page.route(`**/api/repositories/1/${suffix}`, async (route) => {
      if (route.request().method() !== "GET") writes += 1;
      await route.fulfill(failed ? { status: 503, json: { detail: "合成配置读取失败" } } : { json: { enabled: true, include_description: true, context_paths: ["docs/saved.md"] } });
    });
  }
  await openRepository(page);
  await page.getByRole("tab", { name: "发布审查" }).click();
  await expect(page.getByRole("alert").first()).toContainText("合成配置读取失败");
  await expect(page.getByRole("button", { name: "保存合并前配置" })).toHaveCount(0);
  await expect(page.getByRole("checkbox", { name: "向 MR 发布可定位的评审发现" })).toBeDisabled();
  failed = false;
  await page.locator("section").filter({ has: page.getByRole("heading", { name: "GitLab 行内评论", exact: true }) }).getByRole("button", { name: "重新加载" }).click();
  await page.locator("section").filter({ has: page.getByRole("heading", { name: "合并前审查", exact: true }) }).getByRole("button", { name: "重新加载" }).click();
  await expect(page.getByRole("textbox", { name: "仓库业务文档路径" })).toHaveValue("docs/saved.md");
  await expect(page.getByRole("button", { name: "保存合并前配置" })).toBeDisabled();
  expect(writes).toBe(0);
});

test("批量重审只取消成功项勾选，请求中锁定选择和筛选", async ({ page }) => {
  await page.route("**/api/task-search*", async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    const job = data.items[0];
    await route.fulfill({ json: { ...data, items: [{ ...job, id: 901, status: "failed" }, { ...job, id: 902, status: "failed" }], total: 2 } });
  });
  let finish = () => {};
  const held = new Promise<void>((resolve) => { finish = resolve; });
  const submitted: number[][] = [];
  await page.route("**/api/jobs/batch-retry", async (route) => {
    submitted.push(route.request().postDataJSON().ids);
    await held;
    await route.fulfill({ json: [{ id: 901, status: "queued", job_id: 903 }, { id: 902, status: "conflict", error: "合成状态冲突" }] });
  });
  await page.goto("/jobs");
  await page.getByRole("checkbox", { name: "全选本页可重审任务" }).check();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "重审所选任务" }).click();
  await expect(page.getByRole("checkbox", { name: "选择任务 902", exact: true })).toBeDisabled();
  await expect(page.getByRole("combobox", { name: "状态", exact: true })).toBeDisabled();
  await expect(page.getByRole("combobox", { name: "每页条数" })).toBeDisabled();
  finish();
  await expect(page.getByText(/已入队 1 条，未接受 1 条/)).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "选择任务 901", exact: true })).not.toBeChecked();
  await expect(page.getByRole("checkbox", { name: "选择任务 902", exact: true })).toBeChecked();
  expect(submitted).toEqual([[901, 902]]);
});

for (const [path, endpoint] of [["/jobs", "task-search"], ["/issues", "review-issues"], ["/premerge", "premerge-search"]]) {
  test(`${path} 支持条数和跳页，地址栏保留筛选`, async ({ page }) => {
    await page.route(`**/api/${endpoint}?*`, async (route) => {
      const params = new URL(route.request().url()).searchParams;
      await route.fulfill({ json: { items: [], total: 220, page: Number(params.get("page") ?? 1), page_size: Number(params.get("page_size") ?? 25) } });
    });
    await page.goto(`${path}?repository_id=1&page=2`);
    await expect(page.getByRole("combobox", { name: "每页条数" })).toBeEnabled();
    await page.getByRole("combobox", { name: "每页条数" }).selectOption("100");
    await expect(page).toHaveURL(`${path}?repository_id=1&page_size=100`);
    await expect(page.getByText("共 220 条 · 第 1 / 3 页", { exact: true })).toBeVisible();
    await page.getByRole("spinbutton", { name: "跳转页码" }).fill("3");
    await page.getByRole("button", { name: "跳转", exact: true }).click();
    await expect(page).toHaveURL(`${path}?repository_id=1&page_size=100&page=3`);
    await expect(page.getByRole("button", { name: "下一页", exact: true })).toBeDisabled();
    await page.reload();
    await expect(page.getByRole("combobox", { name: "每页条数" })).toHaveValue("100");
  });
}

test("高级筛选按需展开，条件标签可移除并保留每页条数", async ({ page }) => {
  await page.goto("/jobs?page_size=50");
  await expect(page.getByLabel("提交 SHA", { exact: true })).toBeHidden();
  await page.getByText("更多筛选（提交、分支、时间）", { exact: true }).click();
  await page.getByLabel("提交 SHA", { exact: true }).fill("abcd");
  await page.getByLabel("分支", { exact: true }).fill("main");
  await page.getByRole("button", { name: "查询", exact: true }).click();
  await expect(page).toHaveURL(/page_size=50&sha=abcd&target_branch=main/);
  await expect(page.getByLabel("提交 SHA", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "移除提交筛选" }).click();
  await expect(page).toHaveURL("/jobs?page_size=50&target_branch=main");
  await page.getByRole("button", { name: "清空筛选" }).click();
  await expect(page).toHaveURL("/jobs?page_size=50");
});

test("问题历史默认最近十条，按需追加且不丢失旧记录", async ({ page }) => {
  await page.route("**/api/review-issues/1", async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    await route.fulfill({ json: { ...data,
      occurrences: Array.from({ length: 23 }, (_, index) => ({ ...data.occurrences[0], id: 23 - index })),
      events: Array.from({ length: 23 }, (_, index) => ({ id: 23 - index, new_status: "open", actor: "合成用户", note: `合成记录 ${23 - index}`, created_at: "2026-10-22 01:00:00" })),
    } });
  });
  await page.goto("/issues?issue=1");
  await expect(page.locator(".issue-occurrences > div")).toHaveCount(10);
  await expect(page.locator(".issue-history > li")).toHaveCount(10);
  await page.getByRole("button", { name: /再显示 10 条出现记录/ }).click();
  await expect(page.locator(".issue-occurrences > div")).toHaveCount(20);
  await page.getByRole("button", { name: /再显示 10 条出现记录/ }).click();
  await expect(page.locator(".issue-occurrences > div")).toHaveCount(23);
  await page.getByRole("button", { name: /再显示 10 条处理记录/ }).click();
  await expect(page.locator(".issue-history > li")).toHaveCount(20);
});

test("重复问题搜索合并连续输入，避免逐字请求", async ({ page }) => {
  const keywords: string[] = [];
  await page.route("**/api/review-issues?*", async (route) => {
    const keyword = new URL(route.request().url()).searchParams.get("q");
    if (!keyword) { await route.continue(); return; }
    keywords.push(keyword);
    await route.fulfill({ json: { items: [], total: 0, page: 1, page_size: 10 } });
  });
  await page.goto("/issues?issue=1");
  await page.getByText("合并重复问题", { exact: true }).click();
  await page.getByLabel("搜索重复问题").fill("a");
  await page.getByLabel("搜索重复问题").fill("app.py");
  await expect.poll(() => keywords).toEqual(["app.py"]);
  await expect(page.getByText("未找到同项目的其他待处理问题，请更换关键词。", { exact: true })).toBeVisible();
});

for (const width of [1280, 390, 320]) {
  test(`新增分页与配置布局无横向溢出 ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/jobs");
    await expect(page.getByRole("combobox", { name: "每页条数" })).toBeVisible();
    await page.getByText("更多筛选（提交、分支、时间）", { exact: true }).click();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `test-results/optimized-jobs-${width}.png`, fullPage: true });
    await openRepository(page);
    await page.getByRole("tab", { name: "评审参数" }).click();
    await expect(page.getByLabel("超时（秒）")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `test-results/optimized-config-${width}.png`, fullPage: true });
  });
}
