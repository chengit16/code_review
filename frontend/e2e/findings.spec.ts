/** @description 发现价值反馈与问题处置分离、原文分区与响应式；仅访问临时 SQLite 和合成描述。 */
import { expect, test } from "@playwright/test";

const content = [
  "【触发条件】用户操作有两种场景：① 打开「发起审批」弹窗，只填写基础信息，尚未创建审批包时点击取消；② 切换到明细页触发创建请求后立刻关闭弹窗。",
  "【代码依据】`confirmDialog()` 提前返回后正常 resolve，关闭逻辑直接执行 `done()`；而在场景②下 `getId()` 仍返回 null，请求结束后留下不可见草稿。",
  "【实际后果】场景①已填写内容静默丢失；场景②产生孤儿草稿，需要手工清理。",
  "【建议】1）检查表单是否有输入；2）有输入时提示「关闭后已填写内容不会保存，是否继续」；3）确认后再关闭；4）仅表单为空时直接关闭。",
  "补充：核对顺序：1) 核对基础信息；2) 核对异步请求。\n\n重复逻辑需两处维护，建议抽取公共方法。\n此处为合成验收描述，不关联真实业务代码或外部服务。\n\n参考实现：\n```ts\nconst allowed = await checkAccess();\n```",
].join("\n");

test("价值反馈不改变跟进状态，问题侧栏独立处置并经刷新持久化", async ({ page }) => {
  const job = await (await page.request.get("/api/jobs/1")).json();
  const issueId = job.issue_ids["0"];
  await page.request.post(`/api/review-issues/${issueId}`, { data: { status: "open" } });
  await page.request.put("/api/jobs/1/feedback/0", { data: { verdict: "helpful" } });
  await page.goto("/jobs/1");
  const card = page.getByRole("article", { name: "发现 1", exact: true });
  const helpful = card.getByRole("button", { name: "有帮助" });
  const issue = card.getByRole("link", { name: /跟进问题/ });
  await expect(helpful).toHaveAttribute("aria-pressed", "true");
  await card.getByRole("button", { name: "忽略", exact: true }).click();
  await expect(card.getByRole("button", { name: "忽略", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(helpful).toHaveAttribute("aria-pressed", "false");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(card.getByLabel("发现 1 的处理状态", { exact: true })).toHaveText("已处理");
  await expect(issue).not.toContainText("待处理");
  await page.reload();
  await expect(card.getByRole("button", { name: "忽略", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(card.getByLabel("发现 1 的处理状态", { exact: true })).toHaveText("已处理");
  const after = await (await page.request.get("/api/jobs/1")).json();
  expect(after.feedback).toEqual({ "0": "ignored" });
  expect(after.issue_statuses["0"]).toBe("open");

  await page.goto(`/issues?status=all&issue=${issueId}`);
  const drawer = page.locator(".ant-drawer");
  await expect(drawer).toBeVisible();
  await drawer.getByRole("button", { name: "已忽略" }).click();
  const dialog = page.getByRole("dialog", { name: "将问题改为已忽略？", exact: true });
  await dialog.getByLabel("处理说明（选填）").fill("合成验收：已评估，暂不处理");
  await dialog.getByRole("button", { name: "确认忽略" }).click();
  await expect(dialog).toBeHidden();
  await expect(drawer).toContainText("已忽略");
  const detail = await (await page.request.get(`/api/review-issues/${issueId}`)).json();
  expect(detail.events[0].note).toBe("合成验收：已评估，暂不处理");
  await page.goto("/jobs/1");
  const persistedCard = page.getByRole("article", { name: "发现 1", exact: true });
  await expect(persistedCard.getByRole("button", { name: "忽略", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(persistedCard.getByLabel("发现 1 的处理状态", { exact: true })).toHaveText("已处理");
  await expect(persistedCard.getByRole("link", { name: /跟进问题/ })).toHaveText(`跟进问题 #${issueId}`);

  await page.goto(`/issues?status=all&issue=${issueId}`);
  const followup = page.locator(".ant-drawer");
  await expect(followup).toBeVisible();
  await followup.getByRole("button", { name: "待处理" }).click();
  await page.getByRole("button", { name: "确认恢复" }).click();
  await expect(followup).toContainText("待处理");
  const afterReopen = await (await page.request.get("/api/jobs/1")).json();
  expect(afterReopen.feedback).toEqual({ "0": "ignored" });
});

for (const width of [1440, 768, 390, 320]) {
  test(`发现反馈与问题处置分区 ${width}px 留白和操作不溢出`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 1100 });
    const job = await (await page.request.get("/api/jobs/1")).json();
    const issueId = job.issue_ids["0"];
    await page.request.post(`/api/review-issues/${issueId}`, { data: { status: "open" } });
    await page.request.delete("/api/jobs/1/feedback/0");
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.route("**/api/jobs/1", async (route) => {
      const response = await route.fetch();
      const job = await response.json();
      job.result.comments = [
        { ...job.result.comments[0], path: "src/view/promotionPolicy/policyFactoryGifts/usePolicyFactoryGiftsOperation.ts", start_line: 429, content, severity: "medium", category: "correctness" },
        { path: "src/" + "veryLongFileName".repeat(12) + ".ts", content: "未标注的原始描述仍完整展示。建议删除调试输出。\n长标识：" + "longIdentifier".repeat(20), severity: "high", category: "security" },
      ];
      await route.fulfill({ response, json: job });
    });
    await page.route(`**/api/review-issues/${issueId}`, async (route) => {
      const response = await route.fetch();
      await route.fulfill({ response, json: { ...await response.json(), content } });
    });
    await page.goto("/jobs/1");
    const card = page.getByRole("article", { name: "发现 1", exact: true });
    await expect(card).toContainText("正确性");
    for (const name of ["触发条件", "代码依据", "实际后果", "修复建议", "补充"]) await expect(card.getByRole("heading", { name })).toBeVisible();
    await expect(card.locator(".finding-ordered-list li")).toHaveCount(11);
    const sections = card.locator(".finding-description-section");
    for (const [name, count] of [["触发条件", 2], ["代码依据", 1], ["实际后果", 2], ["修复建议", 4], ["补充", 2]] as const) {
      const section = sections.filter({ has: page.getByRole("heading", { name, exact: true }) });
      await expect(section.getByRole("listitem")).toHaveCount(count);
      const rows = await section.getByRole("listitem").evaluateAll((elements) => elements.map((element) => element.getBoundingClientRect().toJSON()));
      for (let index = 1; index < rows.length; index++) expect(rows[index].top).toBeGreaterThanOrEqual(rows[index - 1].bottom);
    }
    const suggestionText = card.locator('[data-tone="suggestion"]');
    await expect(suggestionText.locator(":scope > .finding-text-blocks > p")).toHaveText("建议抽取公共方法。");
    const codeBlock = card.locator(".finding-code-block");
    await expect(codeBlock).toContainText("ts");
    await expect(codeBlock.locator("pre code")).toHaveText("const allowed = await checkAccess();");
    await expect(codeBlock.getByRole("button", { name: "复制代码" })).toBeVisible();
    const plainCard = page.getByRole("article", { name: "发现 2", exact: true });
    await expect(plainCard.getByRole("heading", { name: "问题描述" })).toBeVisible();
    await expect(plainCard.locator('[data-tone="suggestion"]')).toContainText("建议删除调试输出");
    const renderedDescription = await card.locator(".finding-description").textContent();
    await page.route("**/api/jobs/1/comparison?*", (route) => route.fulfill({ json: {
      added: [{ path: "src/synthetic.ts", content }], removed: [{ path: "src/previous.ts", content }],
      unchanged_count: 0, before_status: "complete", after_status: "complete",
    } }));
    const history = page.locator("details").filter({ has: page.locator(".attempt-report-section") });
    await history.locator("summary").click();
    await history.getByRole("button", { name: "比较结果" }).click();
    await expect(history.locator(".comparison-finding")).toHaveCount(2);
    for (const comparison of await history.locator(".finding-description").all()) {
      expect(await comparison.textContent()).toBe(renderedDescription);
      expect(await comparison.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
    }
    await history.screenshot({ path: testInfo.outputPath(`history-description-${width}.png`), animations: "disabled" });
    await history.locator("summary").click();
    await expect(card.getByRole("group", { name: "发现 1 的反馈" }).getByRole("button")).toHaveCount(3);
    await expect(card.getByRole("button", { name: "已修复" })).toHaveCount(0);
    const consequence = card.locator('[data-tone="consequence"]');
    const suggestion = card.locator('[data-tone="suggestion"]');
    expect(await consequence.evaluate((element) => getComputedStyle(element).backgroundColor)).not.toBe(await suggestion.evaluate((element) => getComputedStyle(element).backgroundColor));
    expect(await card.locator(".finding-body").evaluate((element) => parseFloat(getComputedStyle(element).paddingTop))).toBeGreaterThanOrEqual(16);
    expect(await card.locator(".finding-description p").first().evaluate((element) => parseFloat(getComputedStyle(element).lineHeight))).toBeGreaterThanOrEqual(26);
    const buttons = await card.locator(".finding-actions button").evaluateAll((elements) => elements.map((element) => element.getBoundingClientRect().toJSON()));
    for (const [index, first] of buttons.entries()) {
      expect(first.height).toBeGreaterThanOrEqual(40);
      for (const second of buttons.slice(index + 1)) expect(first.right <= second.left || second.right <= first.left || first.bottom <= second.top || second.bottom <= first.top).toBe(true);
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.locator(".findings-section").screenshot({ path: testInfo.outputPath(`findings-${width}.png`), animations: "disabled" });
    if (width === 1440) {
      await card.evaluate((element) => window.scrollTo(0, element.getBoundingClientRect().top + window.scrollY - 100));
      await card.screenshot({ path: testInfo.outputPath("finding-card-desktop.png"), animations: "disabled" });
    }
    await card.getByRole("button", { name: "忽略", exact: true }).click();
    await expect(card.getByRole("button", { name: "忽略", exact: true })).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByRole("dialog")).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.goto(`/issues?status=all&issue=${issueId}`);
    const drawer = page.locator(".ant-drawer");
    await expect(drawer).toBeVisible();
    await expect(drawer.locator(".finding-ordered-list li")).toHaveCount(11);
    expect(await drawer.locator(".finding-description").textContent()).toBe(renderedDescription);
    expect(await drawer.locator(".finding-description").evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
    await expect(drawer.getByRole("heading", { name: "修复建议" })).toBeVisible();
    await drawer.screenshot({ path: testInfo.outputPath(`issue-description-${width}.png`), animations: "disabled" });
    const ignore = drawer.getByRole("button", { name: "已忽略" });
    await ignore.click();
    const dialog = page.getByRole("dialog", { name: "将问题改为已忽略？", exact: true });
    await expect(dialog).toBeVisible();
    await dialog.screenshot({ path: testInfo.outputPath(`issue-status-confirm-${width}.png`), animations: "disabled" });
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expect(drawer).toBeVisible();
    await expect(ignore).toBeFocused();
    expect(errors).toEqual([]);
  });
}
