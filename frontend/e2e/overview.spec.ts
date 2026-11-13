/** @description 项目首页数据优先层级、筛选、响应式与运行隔离；仅使用隔离服务和合成数据。 */
import { expect, test } from "@playwright/test";

const snapshot = {
  summary: { reviews: 20, failed_reviews: 2, generated: 46, published: 32, new_issues: 18, new_still_open: 12, fixed: 5, ignored: 2, open_now: 18, feedback_marked: 8, false_positive: 1 },
  quality: {
    pending_severity: { critical: 1, high: 3, medium: 20, low: 4, unclassified: 2 },
    summary: { total: 210, helpful: 90, false_positive: 30, ignored: 60, unmarked: 30 },
    since: "2026-10-01 00:00:00", until: "2026-10-31 00:00:00", unavailable_sources: 0,
    trend: Array.from({ length: 30 }, (_, index) => ({ day: `2026-10-${String(index + 1).padStart(2, "0")}`, total: 7, helpful: 3, false_positive: 1, ignored: 2, unmarked: 1 })),
    categories: [{ name: "security", total: 210, helpful: 90, false_positive: 30, ignored: 60, unmarked: 30 }],
    projects: [{ id: 1, name: "合成项目与长名称".repeat(3), total: 210, helpful: 90, false_positive: 30, ignored: 60, unmarked: 30 }],
  },
  current_status_counts: { open: 18, fixed: 5, ignored: 7, merged: 1 },
  current_issues: { open_count: 18, severity_counts: { critical: 1, high: 3, medium: 8, low: 4, unclassified: 2 } },
  trend: Array.from({ length: 30 }, (_, index) => ({ day: `2026-10-${String(index + 1).padStart(2, "0")}`, new: index % 8, fixed: index % 4 })),
  categories: [{ category: "security", generated: 14, issues: 8, open_issues: 5 }, { category: "style", generated: 7, issues: 6, open_issues: 3 }],
  projects: [{ id: 1, name: "合成项目与长名称".repeat(3), open_issues: 8, new_issues: 10, fixed_issues: 2, generated: 22, published: 15, reviews: 12, critical_issues: 1, high_issues: 2 }, { id: 2, name: "次要项目", open_issues: 3, new_issues: 8, fixed_issues: 3, generated: 11, published: 8, reviews: 8, critical_issues: 0, high_issues: 1 }],
};
const runtime = { summary: { repositories: 2, queued: 1, running: 1, complete: 20, attention: 3, historical_failed: 9, notification_failed: 2, total: 32 }, todo: { events_attention: 1, premerge_failed: 2, premerge_partial: 1 }, issue_todo: { open_count: 18, severity_counts: snapshot.current_issues.severity_counts }, activity: { queued: 1, running: 1, total: 2 }, recent: [] };

for (const width of [1440, 390, 320]) {
  test(`反馈趋势直接展示且没有折叠开关 ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.route("**/api/overview", (route) => route.fulfill({ json: runtime }));
    await page.route("**/api/review-effectiveness**", (route) => route.fulfill({ json: snapshot }));
    await page.goto("/?days=30");
    const quality = page.getByRole("region", { name: "评审反馈", exact: true });
    const chart = quality.getByRole("region", { name: "反馈趋势图，可横向滚动" });
    await expect(chart).toBeVisible();
    await expect(quality.getByRole("button", { name: /展开反馈趋势|收起反馈趋势/ })).toHaveCount(0);
    await expect(quality.getByRole("group", { name: /四类反馈按日期并排/ })).toBeVisible();
    await quality.getByRole("button", { name: "查看反馈数据" }).click();
    await expect(quality.getByRole("table", { name: "反馈价值数据（UTC）" })).toBeVisible();
    await quality.getByRole("button", { name: "收起反馈数据" }).click();
    await expect(chart).toBeVisible();
    await page.reload();
    await expect(chart).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`trend-visible-${width}.png`), fullPage: true, animations: "disabled" });
  });
}

for (const width of [1440, 1280, 768, 390, 320]) {
  test(`项目总览 ${width}px 优先展示项目数据并保持窄屏可读`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 1000 });
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.route("**/api/overview", (route) => route.fulfill({ json: runtime }));
    await page.route("**/api/repositories", (route) => route.fulfill({ json: [{ id: 1, name: "合成项目与长名称".repeat(3) }, { id: 2, name: "次要项目" }] }));
    await page.route("**/api/review-effectiveness**", (route) => route.fulfill({ json: snapshot }));
    await page.goto("/?days=30&repository_id=1");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("项目总览");
    const filters = page.getByRole("region", { name: "总览筛选" });
    await expect(filters.getByRole("combobox", { name: "项目" })).toBeVisible();
    await expect(page.getByRole("radio", { name: "近 30 天" })).toBeChecked();
    await expect(page.getByRole("region", { name: "项目核心指标" })).toContainText("本期评审数");
    await expect(page.getByRole("region", { name: "项目核心指标" })).toContainText("待反馈发现");
    const quality = page.getByRole("region", { name: "评审反馈" });
    await expect(quality).toBeVisible();
    await expect(quality.getByRole("radio", { name: "问题状态" })).toHaveCount(0);
    await expect(quality.getByRole("link", { name: "查看有帮助 90 条发现" })).toBeVisible();
    for (const share of ["占 42.9%", "占 28.6%"]) {
      await expect(quality.getByText(share, { exact: true })).toBeVisible();
    }
    await expect(quality.getByText("占 14.3%", { exact: true })).toHaveCount(2);
    await expect(quality.getByText(/全部 210 条有效发现为分母（含未评价）/)).toBeVisible();
    expect(await quality.locator(".quality-facts > div").evaluateAll((facts) => facts.every((fact) => {
      const bounds = fact.getBoundingClientRect();
      const share = fact.querySelector(".quality-fact-share")?.getBoundingClientRect();
      return share && share.left >= bounds.left && share.right <= bounds.right + 1;
    }))).toBe(true);
    await expect(quality.getByRole("link", { name: "已处理 180 条" })).toBeVisible();
    const bars = await quality.locator(".quality-bar-group").first().locator("span").evaluateAll((elements) => elements.map((element) => {
      const rect = element.getBoundingClientRect();
      return { left: rect.left, right: rect.right, bottom: rect.bottom, height: rect.height };
    }));
    expect(bars).toHaveLength(4);
    for (let index = 1; index < bars.length; index += 1) {
      expect(bars[index].left).toBeGreaterThan(bars[index - 1].right);
      expect(bars[index].bottom).toBeCloseTo(bars[0].bottom, 1);
    }
    expect(bars[0].height / bars[1].height).toBeCloseTo(3, 1);
    expect(bars[2].height / bars[1].height).toBeCloseTo(2, 1);
    const chartViewport = quality.getByRole("region", { name: "反馈趋势图，可横向滚动" });
    if (width <= 768) {
      const axisLeft = await quality.locator(".overview-chart-axis").evaluate((element) => element.getBoundingClientRect().left);
      await chartViewport.focus();
      await page.keyboard.press("ArrowRight");
      await expect.poll(() => chartViewport.evaluate((element) => element.scrollLeft)).toBeGreaterThan(0);
      expect(await quality.locator(".overview-chart-axis").evaluate((element) => element.getBoundingClientRect().left)).toBeCloseTo(axisLeft, 1);
      await chartViewport.evaluate((element) => { element.scrollLeft = 0; });
    }
    await page.getByRole("button", { name: "展开问题诊断" }).click();
    await expect(page.getByRole("region", { name: "待反馈严重级别" })).toContainText("严重");
    await expect(page.getByRole("region", { name: "项目概况" })).toContainText("待反馈发现");
    await expect(page.getByRole("region", { name: "优化方向" })).toContainText("安全");
    await expect(page.getByRole("region", { name: "全平台运行摘要" })).toContainText("全平台");
    await expect(page.getByRole("region", { name: "最近评审" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "查看评审任务" })).toHaveAttribute("href", "/jobs?repository_id=1");
    const expand = page.getByRole("button", { name: "查看反馈数据" });
    await expand.focus();
    await page.keyboard.press("Enter");
    const dataTable = page.getByRole("table", { name: "反馈价值数据（UTC）" });
    await expect(dataTable).toBeVisible();
    await expect(dataTable.getByRole("columnheader", { name: "日期（UTC）" })).toBeVisible();
    await expect(dataTable.getByRole("columnheader", { name: /修复/ })).toHaveCount(0);
    await expect(quality.getByRole("link", { name: "查看忽略 60 条发现" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ animations: "disabled", fullPage: true, path: testInfo.outputPath(`project-overview-${width}-data.png`) });
    await page.getByRole("button", { name: "收起反馈数据" }).click();
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ animations: "disabled", fullPage: true, path: testInfo.outputPath(`project-overview-${width}.png`) });
    expect(errors).toEqual([]);
  });
}

for (const days of [7, 90]) {
  test(`反馈并排柱 ${days} 天：小数量不被未标记覆盖，零值不绘制假柱`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 390, height: 1000 });
    const counts = { total: 43, helpful: 1, false_positive: 0, ignored: 2, unmarked: 40 };
    const trend = Array.from({ length: days }, (_, index) => ({
      day: new Date(Date.UTC(2026, 7, 1 + index)).toISOString().slice(0, 10),
      ...(index === 0 ? counts : { total: 0, helpful: 0, false_positive: 0, ignored: 0, unmarked: 0 }),
    }));
    await page.route("**/api/overview", (route) => route.fulfill({ json: runtime }));
    await page.route("**/api/review-effectiveness**", (route) => route.fulfill({ json: { ...snapshot, quality: { ...snapshot.quality, summary: counts, trend } } }));
    await page.goto(`/?days=${days}`);
    const chart = page.getByRole("group", { name: /四类反馈按日期并排/ });
    await expect(chart).toBeVisible();
    await expect(chart).toHaveAccessibleName(/纵轴 0 至 40 条/);
    const heights = await chart.locator(".quality-bar-group").first().locator("span").evaluateAll((elements) => elements.map((element) => element.getBoundingClientRect().height));
    expect(heights[0]).toBeGreaterThan(4);
    expect(heights[1]).toBe(0);
    expect(heights[2] / heights[0]).toBeCloseTo(2, 1);
    expect(heights[3] / heights[0]).toBeCloseTo(40, 0);
    expect(await chart.locator(".quality-bar-group").nth(1).locator("span").evaluateAll((elements) => elements.every((element) => element.getBoundingClientRect().height === 0))).toBe(true);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await chart.screenshot({ path: testInfo.outputPath(`grouped-feedback-${days}.png`) });
  });
}

test("项目切换统一影响所有业务图表，运行摘要仍为全平台", async ({ page }) => {
  const requests: string[] = [];
  await page.route("**/api/overview", (route) => route.fulfill({ json: runtime }));
  await page.route("**/api/repositories", (route) => route.fulfill({ json: [{ id: 1, name: "项目一" }, { id: 2, name: "项目二" }] }));
  await page.route("**/api/review-effectiveness**", async (route) => { requests.push(route.request().url()); await route.fulfill({ json: snapshot }); });
  await page.goto("/?days=7&repository_id=1");
  await expect(page.getByRole("region", { name: "项目概况" })).toBeVisible();
  const filters = page.getByRole("region", { name: "总览筛选" });
  await filters.getByRole("combobox", { name: "项目" }).click();
  await page.getByRole("option", { name: "项目二" }).click();
  await expect(page).toHaveURL(/days=7.*repository_id=2|repository_id=2.*days=7/);
  await expect.poll(() => requests.some((url) => url.includes("repository_id=2"))).toBe(true);
  await expect(page.getByRole("region", { name: "全平台运行摘要" })).toContainText("活动任务 2");
  await page.getByRole("radiogroup", { name: "统计时间" }).getByText("近 90 天", { exact: true }).click();
  await expect(page).toHaveURL(/days=90/);
  await expect.poll(() => requests.some((url) => url.includes("days=90") && url.includes("repository_id=2"))).toBe(true);
});

test("手动刷新部分失败不把缓存停止说成当前状态，读者没有管理恢复入口", async ({ page }) => {
  let fail = false;
  await page.route("**/api/health", async (route) => route.fulfill({ status: fail ? 503 : 200, json: fail ? { detail: "合成健康失败" } : { status: "ok", worker: "stopped", auth_mode: "dev" } }));
  await page.route("**/api/overview", (route) => route.fulfill({ json: runtime }));
  await page.route("**/api/review-effectiveness**", (route) => route.fulfill({ json: snapshot }));
  await page.goto("/");
  await expect(page.getByText(/Worker 未运行，队列可能等待处理/)).toBeVisible();
  fail = true;
  const refresh = page.getByRole("button", { name: "刷新概览" });
  await refresh.click();
  await expect(page.getByText(/暂时无法确认 Worker 当前状态/)).toBeVisible();
  await expect(page.getByText(/Worker 未运行，队列可能等待处理/)).toHaveCount(0);
  await expect(page.getByText(/部分读取失败/)).toBeVisible();
  await expect(page.getByRole("region", { name: "全平台运行摘要" })).toBeVisible();
});

for (const width of [1440, 390, 320]) {
  test(`质量样本 ${width}px 保留范围与分页，失败可重试且不丢筛选`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 1000 });
    const requests: string[] = [];
    let fail = false;
    await page.route("**/api/review-effectiveness**", (route) => route.fulfill({ json: snapshot }));
    await page.route("**/api/review-effectiveness/findings**", async (route) => {
      requests.push(route.request().url());
      const query = new URL(route.request().url()).searchParams;
      const current = Number(query.get("page") ?? 1);
      await route.fulfill({ status: fail ? 503 : 200, json: fail ? { detail: "合成样本读取失败" } : {
        total: 90, page: current, page_size: 10,
        items: Array.from({ length: 10 }, (_, index) => ({ finding_id: `j${current * 10 + index}:a1:c0`, job_id: 1, repository_id: 1, repository_name: "合成项目", source_attempt: 1, revision: 0, recovery_id: null, comment_index: 0, generated_at: "2026-10-05 00:00:00", category: "security", severity: "high", path: "src/long-file-name.ts", excerpt: `合成发现 ${current}-${index}：检查边界处理及人工反馈`, issue_id: 1, issue_status: "ignored", feedback: "helpful" })),
      } });
    });
    await page.goto("/?days=30&repository_id=1&sample_open=1&sample_feedback=helpful&sample_since=2026-10-01+00%3A00%3A00&sample_until=2026-10-31+00%3A00%3A00");
    const drawer = page.getByRole("dialog", { name: "评审质量样本" });
    await expect(drawer).toBeVisible();
    await expect(drawer.getByText("共 90 条发现", { exact: true })).toBeVisible();
    await expect(drawer.getByText("合成发现 1-0", { exact: false })).toBeVisible();
    expect(requests[0]).toContain("repository_id=1");
    expect(requests[0]).toContain("feedback=helpful");
    expect(requests[0]).toContain("since=2026-10-01");
    expect(await drawer.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
    await drawer.getByTitle("2", { exact: true }).click();
    await expect(page).toHaveURL(/sample_page=2/);
    await expect(drawer.getByText("合成发现 2-0", { exact: false })).toBeVisible();
    await page.goBack();
    await expect(page).not.toHaveURL(/sample_page=2/);
    await expect(drawer.getByText("合成发现 1-0", { exact: false })).toBeVisible();
    await page.screenshot({ fullPage: false, animations: "disabled", path: testInfo.outputPath(`quality-samples-${width}.png`) });
    fail = true;
    const severity = drawer.getByRole("combobox", { name: "样本严重级别" });
    await severity.click();
    await severity.press("ArrowDown");
    await severity.press("ArrowDown");
    await severity.press("Enter");
    await expect(drawer.getByRole("alert")).toContainText("合成样本读取失败");
    await expect(page).toHaveURL(/sample_feedback=helpful/);
    await expect(page).toHaveURL(/sample_severity=high/);
    fail = false;
    await drawer.getByRole("button", { name: "重新加载" }).click();
    await expect(drawer.getByText("共 90 条发现", { exact: true })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(drawer).not.toBeVisible();
    await expect(page).toHaveURL(/repository_id=1/);
    await expect(page).not.toHaveURL(/sample_open/);
    await expect(page.getByRole("link", { name: "已处理 180 条" })).toBeVisible();
  });
}

test("真实隔离 API 的反馈计数与样本下钻一致，刷新后仍可复现", async ({ page, baseURL }) => {
  expect(new URL(baseURL ?? "").port).toBe("8791");
  const put = await page.request.put("/api/jobs/1/feedback/0", { data: { verdict: "helpful" } });
  expect(put.status()).toBe(200);
  try {
    await page.goto("/?days=7&repository_id=1");
    await page.getByRole("link", { name: "查看有帮助 1 条发现" }).click();
    const drawer = page.locator(".page");
    await expect(drawer.getByText("共 1 条发现", { exact: true })).toBeVisible();
    await expect(drawer.getByText("示例发现", { exact: true })).toBeVisible();
    await page.reload();
    await expect(drawer.getByText("共 1 条发现", { exact: true })).toBeVisible();
    await expect(drawer.getByRole("link", { name: "任务 #1", exact: true })).toHaveAttribute("href", "/jobs/1#job-result");
    await drawer.getByRole("button", { name: "示例发现", exact: true }).click();
    await expect(page.getByRole("dialog", { name: "评审发现详情" })).toContainText("j1:a1:c0");
    await expect(page).toHaveURL(/repository_id=1/);
  } finally {
    expect((await page.request.delete("/api/jobs/1/feedback/0")).status()).toBe(200);
  }
});
