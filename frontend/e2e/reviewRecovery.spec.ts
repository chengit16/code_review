/** @description 临时 SQLite 全链路补审验收；结果/投递由测试适配器推进，不调用真实模型。 */
import { chromium, expect, test } from "@playwright/test";

test.skip(process.env.OCR_BROWSER_REVIEW_RECOVERY !== "1", "需显式使用合成补审测试服务");

for (const width of [1280, 320]) {
  test(`历史诊断实际导入后可查，部分任务默认可补审 ${width}`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/jobs/5");
    const diagnosis = page.getByRole("region", { name: "分层失败诊断" });
    await expect(diagnosis.getByText(/历史诊断导入于/)).toBeVisible();
    await expect(diagnosis.getByText(/模型请求存在 HTTP 504/)).toBeVisible();
    await diagnosis.getByText("失败请求证据 · 1 条", { exact: true }).click();
    await expect(diagnosis.getByText(/响应头计时（毫秒）：60001/)).toBeVisible();
    const panel = page.getByRole("region", { name: "继续审核与补审历史" });
    await expect(panel.getByRole("button", { name: "继续审核剩余部分", exact: true })).toBeEnabled();
    expect(await (await request.get("/api/jobs/5/recoveries")).json()).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });

  test(`补审无需开关但配置缺失时说明原因 ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.route("**/api/jobs/1/recovery-eligibility", async (route) => {
      const response = await route.fetch();
      await route.fulfill({ response, json: { ...await response.json(), eligible: false, reason_code: "configuration_unavailable" } });
    });
    // 新夹具默认持久化分层诊断，此处显式模拟升级前缺少诊断的历史详情。
    await page.route("**/api/jobs/1", async (route) => {
      const response = await route.fetch();
      await route.fulfill({ response, json: { ...await response.json(), failure_analysis: null } });
    });
    await page.goto("/jobs/1");
    const panel = page.getByRole("region", { name: "继续审核与补审历史" });
    const button = panel.getByRole("button", { name: "继续审核剩余部分", exact: true });
    await expect(button).toBeDisabled();
    await expect(panel.getByText("当前无法补审：无法读取当前模型配置，请先核对配置")).toBeVisible();
    await expect(button).toHaveAttribute("title", "当前无法补审：无法读取当前模型配置，请先核对配置");
    await expect(panel.getByText(/补审无需配置开关或项目白名单/)).toBeVisible();
    await expect(panel.getByText(/资格原因码/)).toContainText("configuration_unavailable");
    await expect(page.getByText(/需要受控历史诊断导入/)).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    if (width === 320) await page.screenshot({ path: "test-results/review-recovery-disabled-320.png", fullPage: true });
  });
}

for (const [index, width] of [1280, 390, 320].entries()) {
  test(`补审确认、历史、有效发现反馈和通知独立重试 ${width}`, async ({ page, request }) => {
    const jobId = index + 1;
    await page.setViewportSize({ width, height: 900 });
    await page.goto(`/jobs/${jobId}`);
    const panel = page.getByRole("region", { name: "继续审核与补审历史" });
    await panel.getByRole("button", { name: "继续审核剩余部分", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "确认补审范围与预算" });
    await expect(dialog.getByText(/失败子集 2 个文件/)).toBeVisible();
    await dialog.getByText("查看冻结失败文件").click();
    await expect(dialog.getByText("comma,name[1].ts", { exact: true })).toBeVisible();
    await expect(dialog.getByText("space name.py", { exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(await dialog.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
    if (width === 320) await page.screenshot({ path: "test-results/review-recovery-confirm-320.png", fullPage: true });
    await dialog.getByLabel("本批 Token 上限").fill("1000");
    await dialog.getByRole("button", { name: "确认并排队" }).click();
    await expect(dialog).not.toBeVisible();
    await expect(panel.getByText(/补审 #/).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "重新评审", exact: true })).toBeDisabled();
    const before = (await (await request.get(`/api/jobs/${jobId}`)).json()).attempts;
    expect((await request.post(`/api/test/jobs/${jobId}/advance-recovery`)).ok()).toBe(true);
    await page.reload();
    const effective = page.getByRole("region", { name: "当前有效评审结论" });
    await expect(effective.getByText("新增补审发现", { exact: true })).toBeVisible();
    await expect(effective.getByText(/完成 \/ 复用 3\/3 · 失败 0/)).toBeVisible();
    await effective.getByRole("group", { name: "发现 2 的反馈" }).getByRole("button", { name: "有帮助" }).click();
    await page.reload();
    await expect(effective.getByRole("group", { name: "发现 2 的反馈" }).getByRole("button", { name: "有帮助" })).toHaveAttribute("aria-pressed", "true");
    // 补审反馈同样只记录价值；替换和撤销不改变共享问题的处置。
    const beforeFeedback = await (await request.get(`/api/jobs/${jobId}`)).json();
    const group = effective.getByRole("group", { name: "发现 2 的反馈" });
    await expect(group.getByRole("button")).toHaveCount(3);
    await expect(group.getByRole("button", { name: "已修复", exact: true })).toHaveCount(0);
    await group.getByRole("button", { name: "忽略", exact: true }).click();
    await expect(group.getByRole("button", { name: "忽略", exact: true })).toHaveAttribute("aria-pressed", "true");
    await expect(group.getByRole("button", { name: "有帮助", exact: true })).toHaveAttribute("aria-pressed", "false");
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await page.reload();
    await expect(group.getByRole("button", { name: "忽略", exact: true })).toHaveAttribute("aria-pressed", "true");
    const ignored = await (await request.get(`/api/jobs/${jobId}`)).json();
    const findingId = ignored.effective_document.findings[1].finding_id;
    expect(ignored.finding_feedback[findingId]).toBe("ignored");
    expect(ignored.resolved_finding_issues).toEqual(beforeFeedback.resolved_finding_issues);
    await group.getByRole("button", { name: "忽略", exact: true }).click();
    await expect(group.getByRole("button", { pressed: true })).toHaveCount(0);
    const cleared = await (await request.get(`/api/jobs/${jobId}`)).json();
    expect(cleared.finding_feedback[findingId]).toBeUndefined();
    expect(cleared.resolved_finding_issues).toEqual(beforeFeedback.resolved_finding_issues);
    page.once("dialog", (confirmation) => confirmation.accept());
    await panel.getByRole("button", { name: "仅重发补充通知" }).click();
    await expect(panel.getByRole("button", { name: "仅重发补充通知" })).not.toBeVisible();
    expect((await request.post(`/api/test/jobs/${jobId}/advance-notification`)).ok()).toBe(true);
    await page.reload();
    await expect(panel.getByText("已发送", { exact: true })).toBeVisible();
    const after = await (await request.get(`/api/jobs/${jobId}`)).json();
    expect(after.attempts).toBe(before);
    expect(after.status).toBe("partial");
    expect(after.effective_status).toBe("complete");
    expect(after.recovery_execution_count).toBe(1);
    expect(after.cumulative_usage.known_tokens.total_tokens).toBe(9);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    if (width === 320) await page.screenshot({ path: "test-results/review-recovery-320.png", fullPage: true });
  });
}

test("排队补审可停止，初审发现不丢失", async ({ page }) => {
  await page.goto("/jobs/4");
  const panel = page.getByRole("region", { name: "继续审核与补审历史" });
  await panel.getByRole("button", { name: "继续审核剩余部分", exact: true }).click();
  await page.getByRole("dialog").getByLabel("本批 Token 上限").fill("1000");
  await page.getByRole("dialog").getByRole("button", { name: "确认并排队" }).click();
  page.once("dialog", (dialog) => dialog.accept());
  await panel.getByRole("button", { name: "停止补审", exact: true }).click();
  await expect(panel.getByText("已取消", { exact: true })).toBeVisible();
  await expect(page.getByText("保留初审发现", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "重新评审", exact: true })).toBeEnabled();
});

test("普通 HTTP 域名可以确认补审，响应丢失重试同一 UUID 不重复入队", async () => {
  const browser = await chromium.launch({
    executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
    args: ["--host-resolver-rules=MAP ocr-review-http.test 127.0.0.1", "--no-proxy-server"],
  });
  try {
    const page = await browser.newPage();
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    const commands: unknown[] = [];
    await page.route("**/api/jobs/5/recoveries", async (route) => {
      if (route.request().method() !== "POST") return route.continue();
      commands.push(route.request().postDataJSON());
      // route.fetch 不使用 Chrome 的域名映射；代理到同一个临时后端，不修改业务请求体。
      const response = await route.fetch({ url: "http://127.0.0.1:8791/api/jobs/5/recoveries" });
      if (commands.length === 1) {
        // 临时后端已经入队，模拟代理丢失成功响应；第二次只能重放原命令。
        await route.fulfill({ status: 503, json: { detail: "合成代理响应丢失" } });
      } else await route.fulfill({ response });
    });
    await page.goto("http://ocr-review-http.test:8791/jobs/5");
    expect(await page.evaluate(() => window.isSecureContext)).toBe(false);
    expect(await page.evaluate(() => typeof crypto.randomUUID)).toBe("undefined");
    await page.getByRole("button", { name: "继续审核剩余部分", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "确认补审范围与预算" });
    await dialog.getByLabel("本批 Token 上限").fill("1000");
    await dialog.getByRole("button", { name: "确认并排队", exact: true }).click();
    await expect(dialog.getByRole("alert")).toContainText("合成代理响应丢失");
    await dialog.getByRole("button", { name: "重试同一补审请求", exact: true }).click();
    await expect(dialog).not.toBeVisible();
    expect(commands).toHaveLength(2);
    expect(commands[0]).toEqual(commands[1]);
    expect(commands[0]).toMatchObject({ client_key: expect.stringMatching(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/) });
    const history: unknown = await page.evaluate(async () => (await fetch("/api/jobs/5/recoveries")).json());
    expect(history).toHaveLength(1);
    expect(errors).toEqual([]);
    // 队列真实按顺序领取；结束本例的合成批次，避免阻塞后续预算流程夹具。
    expect((await page.request.post("http://127.0.0.1:8791/api/test/jobs/5/advance-recovery")).ok()).toBe(true);
  } finally {
    await browser.close();
  }
});

for (const [index, width] of [1280, 320].entries()) {
  test(`预算失败解释、人工调整额度后再单独排队 ${width}`, async ({ page, request }, testInfo) => {
    const jobId = index + 6;
    await page.setViewportSize({ width, height: 1000 });
    await page.goto(`/jobs/${jobId}`);
    const panel = page.getByRole("region", { name: "继续审核与补审历史" });
    await expect(panel.getByText(/已用 3\/3 批；累计批准 3000\/100000/)).toBeVisible();
    await expect(panel.getByText(/已用 573 \+ 下一组预估 127524 = 128097/).first()).toBeVisible();
    await expect(panel.getByRole("button", { name: "继续审核剩余部分", exact: true })).toBeDisabled();
    await panel.getByRole("button", { name: "调整本任务补审额度" }).click();
    const budget = page.getByRole("dialog", { name: "确认调整任务额度" });
    await expect(budget.getByLabel("累计补审批次上限")).toHaveValue("3");
    await expect(budget.getByLabel("累计批准 Token 上限")).toHaveValue("100000");
    await expect(budget.getByRole("button", { name: "确认保存额度（不排队）" })).toBeDisabled();
    // 无横向溢出并不代表布局正常：额外检查留白、控件宽度和标签的独立行。
    const layout = await budget.evaluate((element) => {
      const rect = element.getBoundingClientRect();
      const title = element.querySelector("h2")!.getBoundingClientRect();
      const inputs = [...element.querySelectorAll("input")].map((input) => input.getBoundingClientRect());
      const reason = element.querySelector("textarea")!;
      const area = reason.getBoundingClientRect();
      const label = reason.closest("label")!;
      const footer = element.querySelector(".issue-action-buttons")!;
      return { titleInset: title.left - rect.left, fieldInset: inputs[0].left - rect.left,
        reasonWidth: area.width, labelWidth: label.getBoundingClientRect().width,
        reasonHeight: area.height, reasonDisplay: getComputedStyle(label).display,
        reasonFont: getComputedStyle(reason).fontFamily, inputFont: getComputedStyle(element.querySelector("input")!).fontFamily,
        rowDifference: inputs[1].top - inputs[0].top,
        footerPadding: Number.parseFloat(getComputedStyle(footer).paddingBottom) };
    });
    expect(layout.titleInset).toBeGreaterThanOrEqual(16);
    expect(layout.fieldInset).toBeGreaterThanOrEqual(16);
    expect(Math.abs(layout.reasonWidth - layout.labelWidth)).toBeLessThan(2);
    expect(layout.reasonHeight).toBeGreaterThanOrEqual(110);
    expect(layout.reasonDisplay).toBe("grid");
    expect(layout.reasonFont).toBe(layout.inputFont);
    expect(layout.footerPadding).toBeGreaterThanOrEqual(16);
    if (width === 320) expect(layout.rowDifference).toBeGreaterThan(50);
    else expect(Math.abs(layout.rowDifference)).toBeLessThan(2);
    await budget.screenshot({ path: testInfo.outputPath(`budget-layout-${width}.png`) });
    if (width === 320) {
      await page.setViewportSize({ width, height: 480 });
      await budget.getByLabel("调整原因").scrollIntoViewIfNeeded();
      await expect(budget.getByRole("heading")).toBeInViewport();
      await expect(budget.getByRole("button", { name: "取消调整" })).toBeInViewport();
      await expect(budget.getByRole("button", { name: "确认保存额度（不排队）" })).toBeInViewport();
      await budget.screenshot({ path: testInfo.outputPath("budget-layout-short-320.png") });
      await page.setViewportSize({ width, height: 1000 });
    }
    await budget.getByLabel("累计补审批次上限").fill("4");
    await budget.getByLabel("累计批准 Token 上限").fill("200000");
    await budget.getByLabel("调整原因").fill("隔离合成预算授权，不调用模型");
    expect(await budget.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
    await budget.getByRole("button", { name: "确认保存额度（不排队）" }).click();
    await expect(panel.getByText(/额度已保存，未排队或调用模型/)).toBeVisible();
    expect(await (await request.get(`/api/jobs/${jobId}/recoveries`)).json()).toHaveLength(3);
    await panel.getByRole("button", { name: "继续审核剩余部分", exact: true }).click();
    const confirm = page.getByRole("dialog", { name: "确认补审范围与预算" });
    await expect(confirm.getByLabel("本批 Token 上限")).toHaveValue("");
    await confirm.getByLabel("本批 Token 上限").fill("1000");
    await expect(confirm.getByRole("button", { name: "确认并排队" })).toBeDisabled();
    await confirm.getByLabel("本批 Token 上限").fill("150000");
    await confirm.getByRole("button", { name: "确认并排队" }).click();
    await expect(confirm).not.toBeVisible();
    expect((await request.post(`/api/test/jobs/${jobId}/advance-recovery`)).ok()).toBe(true);
    await page.reload();
    await expect(page.getByRole("region", { name: "当前有效评审结论" }).getByText(/完成 \/ 复用 3\/3 · 失败 0/)).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(await (await request.get(`/api/jobs/${jobId}/recoveries`)).json()).toHaveLength(4);
  });
}

test("真实只读账号可查有效结论但没有补审、反馈或通知重发入口", async ({ page, request }) => {
  for (const [username, role] of [["pilot-admin", "admin"], ["pilot-reader", "reader"]]) {
    expect((await request.post("/api/auth/users", { data: { username, role, password: "synthetic-password-123" } })).status()).toBe(201);
  }
  expect((await request.put("/api/auth/mode", { data: { users_enabled: true } })).ok()).toBe(true);
  await page.goto("/jobs/1");
  await page.getByLabel("用户名").fill("pilot-reader");
  await page.getByLabel("密码", { exact: true }).fill("synthetic-password-123");
  await page.getByRole("button", { name: "进入管理台" }).click();
  await expect(page.getByRole("region", { name: "当前有效评审结论" })).toBeVisible();
  await expect(page.getByRole("button", { name: "继续审核剩余部分", exact: true })).not.toBeVisible();
  await expect(page.getByRole("button", { name: "仅重发补充通知" })).not.toBeVisible();
  await expect(page.getByRole("button", { name: "有帮助", exact: true })).not.toBeVisible();
  const session = await (await request.post("/api/auth/login", { data: { username: "pilot-reader", password: "synthetic-password-123" } })).json();
  await expect(page.getByRole("button", { name: "调整本任务补审额度" })).not.toBeVisible();
  expect((await request.put("/api/jobs/1/recovery-budget", { headers: { Authorization: `Bearer ${session.token}` }, data: {} })).status()).toBe(403);
  expect((await request.post("/api/jobs/1/recoveries", { headers: { Authorization: `Bearer ${session.token}` }, data: {} })).status()).toBe(403);
});
