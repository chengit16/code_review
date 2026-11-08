/** @description 归档仅连接 8791 临时库，验收持久化、恢复、双向关系、复盘与窄屏。 */
import { randomUUID } from "node:crypto";

import { expect, test } from "@playwright/test";

test("问题和主题归档后可查询、追溯、恢复，默认列表不再显示", async ({ page }) => {
  const title = `归档验收-${randomUUID()}`;
  const created = await page.request.post("/api/improvements", { data: {
    client_key: randomUUID(), title, description: "保留未解决事实", category: "integration",
    code_state: "modified", verification_state: "passed", validation_evidence: "仅合成验证",
  } });
  expect(created.status()).toBe(201);
  const issue = await created.json();
  const themeResponse = await page.request.post("/api/improvement-themes", { data: {
    client_key: randomUUID(), title: `${title}-主题`, objective: "保留关系与阶段", category: "integration",
    improvement_ids: [issue.id], phases: [{ title: "未完成阶段", goal: "继续观察" }],
  } });
  expect(themeResponse.status()).toBe(201);
  const theme = await themeResponse.json();
  for (const target of [{ path: `/improvements/${issue.id}`, edit: "编辑并追加进展" },
    { path: `/improvements/themes/${theme.id}`, edit: "编辑主题与阶段" }]) {
    await page.goto(target.path);
    await page.getByRole("button", { name: "归档内容", exact: true }).click();
    await page.getByLabel("归档原因").fill("阶段收纳，不代表解决或部署");
    for (const width of [1280, 320]) {
      await page.setViewportSize({ width, height: 844 });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      await page.screenshot({ path: `test-results/archive-dialog-${width}.png` });
    }
    await page.getByRole("button", { name: "确认归档", exact: true }).click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(page.getByRole("button", { name: target.edit, exact: true })).toHaveCount(0);
    await page.reload();
    await expect(page.getByRole("region", { name: "归档管理" })).toContainText("阶段收纳，不代表解决或部署");
    await expect(page.getByText(/归档 · 版本 2/)).toBeVisible();
  }
  await page.goto(`/improvements?q=${encodeURIComponent(title)}`);
  await expect(page.getByText("当前条件下暂无记录", { exact: false })).toBeVisible();
  await page.getByText("更多筛选", { exact: true }).click();
  await page.getByRole("combobox", { name: "归档范围" }).click();
  await page.getByRole("option", { name: "已归档", exact: true }).click();
  await expect(page).toHaveURL(/archive=archived/);
  await expect(page.getByRole("link", { name: `#${issue.id} · ${title}`, exact: true })).toBeVisible();
  await page.reload();
  await expect(page.locator(".list-conditions")).toContainText("已归档");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/archive-record-list-320.png", fullPage: true });
  await page.getByRole("link", { name: `#${issue.id} · ${title}`, exact: true }).click();
  await expect(page.getByRole("region", { name: "关联优化主题" })).toContainText("已归档");
  await page.getByRole("button", { name: "恢复内容" }).click();
  await page.getByLabel("恢复原因").fill("继续跟进遗留事项");
  await page.getByRole("button", { name: "确认恢复", exact: true }).click();
  await expect(page.getByRole("button", { name: "编辑并追加进展" })).toBeVisible();
  await expect(page.getByText(/恢复 · 版本 3/)).toBeVisible();
  await expect(page.getByRole("region", { name: "当前记录" })).toContainText("本地验证通过");
  await expect(page.getByRole("region", { name: "当前记录" })).toContainText("未部署");
  await page.goto(`/improvements?view=themes&theme_q=${encodeURIComponent(title)}&theme_archive=archived`);
  await expect(page.getByRole("link", { name: `#${theme.id} · ${title}-主题`, exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.getByRole("link", { name: `#${theme.id} · ${title}-主题`, exact: true }).click();
  await expect(page.getByRole("link", { name: `查看问题记录 #${issue.id}`, exact: true })).toBeVisible();
  await page.getByRole("button", { name: "恢复内容" }).click();
  await page.getByLabel("恢复原因").fill("继续实施优化");
  await page.getByRole("button", { name: "确认恢复", exact: true }).click();
  await expect(page.getByRole("button", { name: "编辑主题与阶段" })).toBeVisible();
});

test("过期归档请求保留原因，不伪装成功；复盘继续显示归档中的未解决事项", async ({ page }) => {
  const title = `归档冲突-${randomUUID()}`;
  const created = await page.request.post("/api/improvements", { data: {
    client_key: randomUUID(), title, description: "合成冲突", category: "performance",
  } });
  const issue = await created.json();
  await page.goto(`/improvements/${issue.id}`);
  await page.getByRole("button", { name: "归档内容" }).click();
  await page.getByLabel("归档原因").fill("我的原因草稿");
  const concurrent = await page.request.post(`/api/improvements/${issue.id}/archive`, { data: {
    expected_version: 1, archived: true, reason: "另一管理员已经收纳",
  } });
  expect(concurrent.status()).toBe(200);
  await page.getByRole("button", { name: "确认归档", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("版本已更新");
  await expect(page.getByLabel("归档原因")).toHaveValue("我的原因草稿");
  expect((await (await page.request.get(`/api/improvements/${issue.id}/history`)).json()).total).toBe(2);
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "取消", exact: true }).click();
  await page.goto("/improvements?view=summary&summary_category=performance");
  await expect(page.getByText(/累计与待办包含已归档内容/)).toBeVisible();
  const attention = page.getByRole("region", { name: "未解决记录（含暂缓）", exact: true });
  await expect(attention.getByRole("link", { name: `#${issue.id} · ${title}`, exact: true })).toBeVisible();
  await expect(attention).toContainText("已归档");
});
