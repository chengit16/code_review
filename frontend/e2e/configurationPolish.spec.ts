/** @description 模型和账号局部视觉回归；仅使用合成配置、临时后端及独立构建，不操作业务实例。 */
import { expect, test } from "@playwright/test";
import type { Locator } from "@playwright/test";

async function expectSingleLine(button: Locator) {
  const layout = await button.evaluate((element) => {
    const label = element.querySelector("span:last-child") ?? element;
    const range = document.createRange();
    range.selectNodeContents(label);
    return { lines: range.getClientRects().length, whiteSpace: getComputedStyle(element).whiteSpace };
  });
  expect(layout.whiteSpace).toBe("nowrap");
  expect(layout.lines).toBe(1);
}

for (const width of [1440, 1280, 768, 390, 320]) {
  test(`模型与账号短操作不堆叠、不断字 ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 1000 });
    const writes: string[] = [];
    const errors: string[] = [];
    page.on("request", (request) => { if (!["GET", "HEAD"].includes(request.method())) writes.push(request.url()); });
    page.on("pageerror", (error) => errors.push(error.message));
    await page.route("**/api/model-profiles", (route) => route.fulfill({ json: [
      { id: 11, name: "合成备用模型", model: "review-example", provider: "openai", base_url: "https://models.example.test/v1", price_currency: "USD", input_price_per_million: "2", output_price_per_million: "10", enabled: 0, has_api_key: true },
      { id: 12, name: "合成启用模型", model: "review-active", provider: "dashscope", base_url: "", price_currency: "CNY", input_price_per_million: "0.8", output_price_per_million: "2.7", enabled: 1, has_api_key: true },
    ] }));
    await page.goto("/settings?tab=model");
    const modelRow = page.getByRole("row").filter({ hasText: "合成备用模型" });
    await expect(modelRow).toBeVisible();
    await expect(modelRow).toContainText("非默认");
    const actions = modelRow.locator(".config-row-actions");
    const buttons = actions.getByRole("button");
    await expect(buttons).toHaveCount(3);
    const tops: number[] = [];
    for (const button of await buttons.all()) {
      await expectSingleLine(button);
      const box = await button.boundingBox();
      expect(box).not.toBeNull();
      if (box) tops.push(box.y);
    }
    expect(Math.max(...tops) - Math.min(...tops)).toBeLessThan(1);
    expect(await actions.evaluate((element) => element.getBoundingClientRect().height)).toBeLessThanOrEqual(34);
    // 手机沿用带标签的纵向资料卡，只有桌面表格行高应保持紧凑。
    if (width > 600) expect(await modelRow.evaluate((element) => element.getBoundingClientRect().height)).toBeLessThan(110);
    const active = page.getByRole("row").filter({ hasText: "合成启用模型" });
    await expect(active.locator(".ant-tag")).toHaveText("全局默认");
    await expect(active.getByRole("button", { name: "删除 合成启用模型", exact: true })).toBeDisabled();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ animations: "disabled", path: testInfo.outputPath(`models-${width}.png`), fullPage: true });
    await modelRow.getByRole("button", { name: "编辑 合成备用模型" }).focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(page.getByLabel("API Key", { exact: true })).toHaveValue("");
    await page.getByRole("button", { name: "取消", exact: true }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible();

    await page.route("**/api/auth/users", (route) => route.fulfill({ json: [
      { id: 21, username: "example-admin", role: "admin", enabled: 1, created_at: "2026-11-01 12:30:00" },
    ] }));
    await page.goto("/users");
    const editor = page.getByRole("button", { name: "编辑 example-admin" });
    await expect(editor).toBeVisible();
    await expectSingleLine(editor);
    await expect(page.locator(".auth-mode-card .inline-setting")).toHaveCount(0);
    expect(await page.locator(".auth-mode-setting").evaluate((element) => getComputedStyle(element).borderTopWidth)).toBe("0px");
    await expect(page.locator(".ant-checkbox-wrapper").getByRole("checkbox", { name: "启用多人账号登录" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ animations: "disabled", path: testInfo.outputPath(`users-${width}.png`), fullPage: true });
    await editor.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("dialog")).toContainText("编辑 example-admin");
    await expect(page.getByLabel("新密码（留空则不修改）")).toHaveValue("");
    await page.getByRole("button", { name: "取消", exact: true }).click();
    const checkbox = page.getByRole("checkbox", { name: "启用多人账号登录" });
    const checked = await checkbox.isChecked();
    page.once("dialog", (dialog) => dialog.dismiss());
    await checkbox.focus();
    await page.keyboard.press("Space");
    await expect(checkbox).toBeChecked({ checked });
    expect(writes).toEqual([]);
    expect(errors).toEqual([]);
  });
}

test("认证控件确认后仍可登录，只读账号不能管理配置", async ({ page }) => {
  page.on("dialog", (dialog) => dialog.accept());
  await page.goto("/users");
  for (const role of ["管理员", "只读"]) {
    const username = role === "管理员" ? "polish-admin" : "polish-reader";
    await page.getByRole("button", { name: "添加账号" }).click();
    await page.getByLabel("用户名").fill(username);
    await page.getByLabel("密码", { exact: true }).fill("synthetic-password-123");
    await page.getByRole("combobox", { name: "角色", exact: true }).click();
    await page.getByRole("option", { name: role, exact: true }).click();
    await page.getByRole("button", { name: "保存账号" }).click();
    await expect(page.getByText(username, { exact: true })).toBeVisible();
  }
  try {
    // 受控状态等服务端确认后重载，不能要求点击瞬间已选中。
    await page.getByRole("checkbox", { name: "启用多人账号登录" }).click();
    await expect(page.getByLabel("用户名")).toBeVisible();
    await page.getByLabel("用户名").fill("polish-reader");
    await page.getByLabel("密码", { exact: true }).fill("synthetic-password-123");
    await page.getByRole("button", { name: "进入管理台" }).click();
    await expect(page.getByText("polish-reader · 只读")).toBeVisible();
    await expect(page.getByRole("link", { name: "访问权限", exact: true })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "系统设置", exact: true })).toHaveCount(0);
    const session = await (await page.request.post("/api/auth/login", { data: {
      username: "polish-reader", password: "synthetic-password-123",
    } })).json();
    const response = await page.request.get("/api/auth/users", { headers: { Authorization: `Bearer ${session.token}` } });
    expect(response.status()).toBe(403);
  } finally {
    // 恢复临时实例模式，避免影响同一套件后续用例；不涉及业务实例。
    const mode = await page.request.get("/api/auth/mode");
    if (!mode.ok()) {
      const admin = await (await page.request.post("/api/auth/login", { data: {
        username: "polish-admin", password: "synthetic-password-123",
      } })).json();
      expect((await page.request.put("/api/auth/mode", {
        headers: { Authorization: `Bearer ${admin.token}` }, data: { users_enabled: false },
      })).ok()).toBe(true);
    }
  }
});
