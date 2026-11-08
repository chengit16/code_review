/** @description 在真实非安全域名验证新建、复制与旧浏览器能力降级；仅使用 8791 隔离数据。 */
import { expect, test } from "@playwright/test";

// 普通套件会切换多人鉴权；独立运行，避免借重置鉴权掩盖权限回归或污染其他用例。
test.skip(process.env.OCR_BROWSER_HTTP_COMPAT !== "1", "需显式使用独立 HTTP 兼容验收通道");

test.use({
  baseURL: "http://ocr-review-http.test:8791",
  launchOptions: {
    executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
    args: ["--host-resolver-rules=MAP ocr-review-http.test 127.0.0.1", "--no-proxy-server"],
  },
});

test.beforeEach(async ({ page }) => {
  // 真正的 HTTP 能力限制由浏览器产生；仅额外模拟较早版本缺少的静态取消与克隆方法。
  await page.addInitScript(() => {
    Object.defineProperty(AbortSignal, "timeout", { value: undefined, configurable: true });
    Object.defineProperty(AbortSignal, "any", { value: undefined, configurable: true });
    Object.defineProperty(window, "structuredClone", { value: undefined, configurable: true });
  });
});

test("HTTP 下新建问题和主题成功，丢失响应后同键重试不重复建档", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const bodies = new Map<string, unknown[]>();
  for (const path of ["/api/improvements", "/api/improvement-themes"]) {
    bodies.set(path, []);
    await page.route(`**${path}`, async (route) => {
      if (route.request().method() !== "POST") return route.continue();
      const commands = bodies.get(path);
      if (!commands) throw new Error("合成命令收集器缺失");
      commands.push(route.request().postDataJSON());
      const response = await route.fetch({ url: `http://127.0.0.1:8791${path}` });
      if (commands.length === 1) await route.fulfill({ status: 503, json: { detail: "合成代理响应丢失" } });
      else await route.fulfill({ response });
    });
  }
  await page.goto("/improvements");
  expect(await page.evaluate(() => isSecureContext)).toBe(false);
  expect(await page.evaluate(() => typeof crypto.randomUUID)).toBe("undefined");
  await page.getByRole("button", { name: "新增记录" }).click();
  await page.getByLabel("标题", { exact: true }).fill("HTTP 幂等问题验收");
  await page.getByLabel("现象或目标").fill("合成问题，不涉及业务服务");
  await page.getByRole("button", { name: "保存记录", exact: true }).click();
  await expect(page.getByRole("dialog").getByRole("alert")).toContainText("合成代理响应丢失");
  await expect(page.getByLabel("标题", { exact: true })).toHaveValue("HTTP 幂等问题验收");
  await page.getByRole("button", { name: "保存记录", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("button", { name: "优化历程" }).click();
  await page.getByRole("button", { name: "新增优化主题" }).click();
  await page.getByLabel("主题名称").fill("HTTP 幂等主题验收");
  await page.getByLabel("总体目标").fill("合成目标");
  await page.getByRole("button", { name: "保存主题" }).click();
  await expect(page.getByRole("dialog").getByRole("alert")).toContainText("合成代理响应丢失");
  await page.getByRole("button", { name: "保存主题" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  for (const commands of bodies.values()) {
    expect(commands).toHaveLength(2);
    expect(commands[0]).toEqual(commands[1]);
    expect(commands[0]).toMatchObject({ client_key: expect.stringMatching(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/) });
  }
  const counts = await page.evaluate(async () => {
    const result: number[] = [];
    for (const [path, title] of [["/api/improvements", "HTTP 幂等问题验收"], ["/api/improvement-themes", "HTTP 幂等主题验收"]]) {
      const response = await fetch(`${path}?q=${encodeURIComponent(title)}`);
      result.push((await response.json()).total);
    }
    return result;
  });
  expect(counts).toEqual([1, 1]);
  expect(errors).toEqual([]);
});

test("HTTP 回调及令牌复制有降级路径，失败提示手动复制且不残留秘密", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/repositories");
  expect(await page.evaluate(() => typeof navigator.clipboard)).toBe("undefined");
  await page.locator(".webhook-callback").getByRole("button").click();
  await expect(page.getByRole("button", { name: "已复制", exact: true })).toBeVisible();
  // 使用合成令牌；不读取或污染用户真实业务令牌。
  await page.route("**/api/repositories/*/webhook-token", (route) => route.fulfill({ json: { webhook_token: "synthetic-http-token" } }));
  await page.getByRole("row").filter({ hasText: "验收任务项目" }).getByRole("button", { name: "接入信息" }).click();
  const copy = page.getByRole("button", { name: "复制 验收任务项目 的 Webhook Token", exact: true });
  await copy.click();
  await expect(page.getByRole("status").filter({ hasText: /^已复制$/ })).toBeVisible();
  expect(await page.locator('textarea[aria-label="临时复制内容"]').count()).toBe(0);
  await page.evaluate(() => { document.execCommand = () => false; });
  await copy.click();
  await expect(page.getByRole("alert")).toContainText("点击查看令牌后手动选择复制");
  await expect(page.getByLabel("验收任务项目 的 Webhook Token", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "查看 验收任务项目 的 Webhook Token", exact: true }).click();
  await expect(page.getByLabel("验收任务项目 的 Webhook Token", { exact: true })).toHaveValue("synthetic-http-token");
  await copy.click();
  await expect(page.getByRole("alert")).toContainText("手动选择令牌");
  await page.getByRole("button", { name: "关闭", exact: true }).click();
  await page.locator(".webhook-callback").getByRole("button").click();
  await expect(page.getByText("复制失败，请手动选择回调地址", { exact: true })).toBeVisible();
  expect(await page.locator('textarea[aria-label="临时复制内容"]').count()).toBe(0);
  expect(errors).toEqual([]);
});

test("没有新版取消和克隆 API 仍能保存规则，取消切换不丢草稿", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  // 默认夹具故意保留排队任务，生产保护会拒绝改规则；本例仅验收浏览器草稿和请求边界。
  let content = { include: [] as string[], exclude: [] as string[], rules: [] as { path: string; rule: string; merge_system_rule: boolean }[] };
  await page.route("**/api/review-rules", (route) => route.fulfill({ json: content.rules.length ? [{ repository_id: null, content, updated_at: "2026-11-07" }] : [] }));
  await page.route("**/api/review-rules/global", async (route) => {
    content = route.request().postDataJSON();
    await route.fulfill({ json: { status: "saved" } });
  });
  await page.goto("/review-rules");
  await page.getByRole("button", { name: "添加规则", exact: true }).click();
  await page.getByLabel("文件路径模式", { exact: true }).fill("src/**/*.ts");
  await page.getByRole("textbox", { name: "审核内容", exact: true }).fill("合成规则原值");
  await page.getByRole("button", { name: "保存规则", exact: true }).click();
  await expect(page.getByText("审核规则已保存", { exact: true })).toBeVisible();
  await page.getByRole("textbox", { name: "审核内容", exact: true }).fill("尚未保存的修改");
  page.once("dialog", (dialog) => dialog.dismiss());
  await page.getByRole("combobox", { name: "配置范围" }).click();
  await page.getByRole("option", { name: "验收任务项目", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "审核内容", exact: true })).toHaveValue("尚未保存的修改");
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("combobox", { name: "配置范围" }).click();
  await page.getByRole("option", { name: "验收任务项目", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "审核内容", exact: true })).toHaveCount(0);
  await page.getByRole("combobox", { name: "配置范围" }).click();
  await page.getByRole("option", { name: "全局规则", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "审核内容", exact: true })).toHaveValue("合成规则原值");
  expect(errors).toEqual([]);
});
