/** @description 复盘汇总只对隔离临时库验收，覆盖口径、筛选、明细、失败与窄屏。 */
import { randomUUID } from "node:crypto";

import { expect, test } from "@playwright/test";

test("复盘累计与活动分开，明细可定位且条件刷新保留", async ({ page }) => {
  const record = await page.request.post("/api/improvements", { data: {
    client_key: randomUUID(), title: "复盘验收：本地通过未部署", description: "合成场景",
    category: "security", status: "resolved", code_state: "modified", solution: "补充边界保护",
    verification_state: "passed", validation_evidence: "仅合成验证，不代表已部署",
  } });
  expect(record.status()).toBe(201);
  const recordId: number = (await record.json()).id;
  const blocked = await page.request.post("/api/improvements", { data: {
    client_key: randomUUID(), title: "复盘验收：验证受阻", description: "合成阻塞", category: "security",
    status: "deferred", verification_state: "blocked", validation_evidence: "等待合成隔离环境",
  } });
  expect(blocked.status()).toBe(201);
  const theme = await page.request.post("/api/improvement-themes", { data: {
    client_key: randomUUID(), title: "复盘验收：安全优化", objective: "复盘关联和阶段分母", category: "security",
    improvement_ids: [recordId], phases: [{ title: "保护阶段", goal: "确认本地证据", status: "completed",
      solution: "完成合成保护", verification_state: "passed", validation_evidence: "合成检查" }],
  } });
  expect(theme.status()).toBe(201);

  await page.goto("/improvements?view=summary&summary_category=security&summary_start_date=2026-11-01&summary_end_date=2026-11-03");
  await expect(page.getByRole("heading", { name: "复盘汇总", exact: true })).toBeVisible();
  await expect(page.getByRole("article", { name: "当前台账记录" }).locator("strong")).toHaveText("2");
  await expect(page.getByRole("article", { name: "已解决占比" }).locator("strong")).toHaveText("50.0%");
  await expect(page.getByRole("heading", { name: "部署待确认（1）" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "验证待跟进（1）" })).toBeVisible();
  await expect(page.getByRole("region", { name: "窗口内活动", exact: true })).toContainText("新增记录 0 条");
  await page.screenshot({ path: "test-results/improvement-summary-full-desktop.png", fullPage: true });
  await page.reload();
  await expect(page.getByLabel("活动开始日期")).toHaveValue("2026-11-01");
  await page.getByLabel("活动开始日期").fill("");
  await page.getByLabel("活动结束日期").fill("");
  await page.getByRole("button", { name: "应用复盘条件" }).click();
  await expect(page.getByRole("region", { name: "窗口内活动", exact: true })).toContainText("新增记录 2 条");
  await page.goBack();
  await expect(page.getByLabel("活动结束日期")).toHaveValue("2026-11-03");
  await page.getByRole("region", { name: "部署待确认", exact: true }).getByRole("link", { name: /本地通过未部署/ }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("复盘验收：本地通过未部署");
  await page.goBack();
  await expect(page.getByLabel("活动结束日期")).toHaveValue("2026-11-03");
  await page.getByRole("region", { name: "处理进展", exact: true }).getByRole("link", { name: "已解决", exact: true }).click();
  await expect(page).toHaveURL(/category=security&status=resolved/);
  await expect(page.getByRole("link", { name: /复盘验收：本地通过未部署/ })).toBeVisible();
});

test("复盘表格与长窗口图表在桌面和窄屏局部滚动，异常不显示空结果", async ({ page }) => {
  await page.goto("/improvements?view=summary&summary_start_date=2026-01-01&summary_end_date=2026-11-03");
  await expect(page.getByRole("article", { name: "当前台账记录" })).toBeVisible();
  await page.getByText("逐日活动明细", { exact: true }).click();
  for (const width of [1280, 390, 320]) {
    await page.setViewportSize({ width, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: `test-results/improvement-summary-${width}.png` });
  }
  await page.route("**/api/improvement-summary?**", (route) => route.fulfill({ status: 503, json: { detail: "合成统计查询失败" } }));
  await page.getByRole("button", { name: "刷新统计" }).click();
  await expect(page.getByRole("alert")).toContainText("合成统计查询失败");
  await expect(page.getByRole("article", { name: "当前台账记录" })).toHaveCount(0);
  await expect(page.getByText(/当前分类暂无台账/)).toHaveCount(0);
  await page.unroute("**/api/improvement-summary?**");
  await page.getByRole("button", { name: "重新加载" }).click();
  await expect(page.getByRole("article", { name: "当前台账记录" })).toBeVisible();
  await page.getByLabel("活动开始日期").fill("2026-11-04");
  await page.getByLabel("活动结束日期").fill("2026-11-01");
  await page.getByRole("button", { name: "应用复盘条件" }).click();
  await expect(page.getByRole("alert")).toContainText("活动日期范围");
  await page.getByRole("button", { name: "重置条件" }).click();
  await expect(page.getByRole("article", { name: "当前台账记录" })).toBeVisible();
});
