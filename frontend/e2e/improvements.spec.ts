/** @description 用隔离 SQLite 验收记录闭环、历史、草稿保护和窄屏，不操作 8781 业务服务。 */
import { expect, test } from "@playwright/test";

test("新增、编辑、历史与刷新后持久化", async ({ page }) => {
  await page.goto("/improvements");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("问题与改进");
  await page.getByRole("button", { name: "新增记录" }).click();
  await page.getByLabel("标题", { exact: true }).fill("隔离验收：通知排队");
  await page.getByLabel("现象或目标").fill("合成场景中长评审阻塞通知");
  await page.getByRole("button", { name: "保存记录", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("link", { name: /隔离验收：通知排队/ }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("隔离验收：通知排队");
  await page.getByRole("button", { name: "编辑并追加进展" }).click();
  await page.getByLabel("标题", { exact: true }).fill("隔离验收：通知解耦");
  await page.getByLabel("原因与排查").fill("合成确认：共用执行路径");
  await page.getByLabel("解决办法与改进").fill("拆分独立执行槽，尚未部署");
  await page.getByRole("combobox", { name: "代码修改", exact: true }).click();
  await page.getByRole("option", { name: "代码已修改", exact: true }).click();
  await page.getByRole("combobox", { name: "本地验证", exact: true }).click();
  await page.getByRole("option", { name: "本地验证通过", exact: true }).click();
  await page.getByLabel("验证命令、结果与范围").fill("合成检查通过，不代表生产效果");
  await page.getByLabel("本次进展说明").fill("本地修改完成，待部署");
  await page.getByRole("button", { name: "保存记录", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("隔离验收：通知解耦");
  const current = page.getByRole("region", { name: "当前记录", exact: true });
  await expect(current.getByText("代码已修改", { exact: true })).toBeVisible();
  await expect(current.getByText("本地验证通过", { exact: true })).toBeVisible();
  await expect(current.getByText("未部署", { exact: true })).toBeVisible();
  await page.getByText(/^建立 · 版本 1 · 建立记录/).click();
  await expect(page.getByRole("heading", { name: "隔离验收：通知排队", exact: true })).toBeVisible();
  await page.screenshot({ path: "test-results/improvements-detail-desktop.png", fullPage: true });
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: `test-results/improvements-detail-${width}.png`, fullPage: true });
  }
});

test("新建草稿关闭与路由离开可取消，窄屏表单不溢出", async ({ page }) => {
  await page.goto("/jobs");
  await page.getByRole("link", { name: "问题与改进", exact: true }).click();
  await page.getByRole("button", { name: "新增记录" }).click();
  await page.getByLabel("标题", { exact: true }).fill("尚未保存的排查");
  page.once("dialog", (dialog) => dialog.dismiss());
  await page.getByRole("button", { name: "关闭", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  page.once("dialog", (dialog) => dialog.dismiss());
  await page.goBack();
  await expect(page).toHaveURL("/improvements");
  await expect(page.getByLabel("标题", { exact: true })).toHaveValue("尚未保存的排查");
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    const dialog = page.getByRole("dialog");
    expect(await dialog.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
    await page.screenshot({ path: `test-results/improvements-editor-${width}.png`, fullPage: true });
  }
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "关闭", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("搜索条件与分页保留，空结果和加载失败明确区分", async ({ page }) => {
  await page.goto("/improvements?q=不存在的合成标题&page_size=50");
  await expect(page.getByLabel("搜索记录")).toHaveValue("不存在的合成标题");
  await expect(page.getByText(/当前条件下暂无记录/)).toBeVisible();
  await expect(page.getByRole("combobox", { name: "每页条数" })).toHaveValue("50");
  await page.route("**/api/improvements?**", (route) => route.fulfill({ status: 503, json: { detail: "合成查询失败" } }));
  await page.reload();
  await expect(page.getByRole("alert")).toContainText("合成查询失败");
  await expect(page.getByText(/当前条件下暂无记录/)).toHaveCount(0);
});

test("主题阶段、问题关联和历史快照在隔离服务持久化", async ({ page }) => {
  await page.goto("/improvements");
  await page.getByRole("button", { name: "新增记录" }).click();
  await page.getByLabel("标题", { exact: true }).fill("主题关联用合成问题");
  await page.getByLabel("现象或目标").fill("供优化历程验收关联");
  await page.getByRole("button", { name: "保存记录", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);

  await page.getByRole("button", { name: "优化历程" }).click();
  await page.getByRole("button", { name: "新增优化主题" }).click();
  await page.getByLabel("主题名称").fill("隔离验收主题");
  await page.getByLabel("总体目标").fill("记录阶段与关联问题");
  await page.getByRole("button", { name: "添加阶段" }).click();
  await page.getByLabel("阶段名称").fill("第一阶段");
  await page.getByLabel("阶段目标").fill("验证关联闭环");
  await page.getByLabel("搜索可关联记录").fill("主题关联用合成问题");
  await page.getByRole("button", { name: "搜索问题" }).click();
  await page.getByRole("checkbox", { name: /主题关联用合成问题/ }).check();
  await page.getByRole("button", { name: "保存主题" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("link", { name: /隔离验收主题/ }).click();
  await expect(page.getByRole("heading", { name: /第一阶段/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /查看问题记录 #/ })).toBeVisible();
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: `test-results/themes-detail-${width}.png`, fullPage: true });
  }

  await page.getByRole("button", { name: "编辑主题与阶段" }).click();
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 844 });
    const dialog = page.getByRole("dialog");
    expect(await dialog.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: `test-results/themes-editor-${width}.png`, fullPage: true });
  }
  await page.getByLabel("本次进展说明").fill("追加隔离验收进展");
  await page.getByRole("button", { name: "保存主题" }).click();
  await expect(page.getByText(/版本 2 · 追加隔离验收进展/)).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: /隔离验收主题/ })).toBeVisible();
  await page.getByRole("link", { name: /查看问题记录 #/ }).click();
  await expect(page.getByRole("heading", { name: "主题关联用合成问题" })).toBeVisible();
  await expect(page.getByRole("link", { name: /隔离验收主题/ })).toBeVisible();
});
