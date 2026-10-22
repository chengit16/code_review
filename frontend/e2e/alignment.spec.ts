/** @description 验证复选框和文字在页面、表单及窄屏中的对齐；不提交配置或切换认证方式。 */
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

async function expectCheckboxAlignment(page: Page) {
  const rows = await page.locator(".checkbox-label").evaluateAll((labels) => labels.filter((label) => label.getClientRects().length > 0).map((label) => {
    const input = label.querySelector<HTMLInputElement>('input[type="checkbox"]');
    if (!input) throw new Error("复选框标签缺少控件");
    const text = Array.from(label.childNodes).filter((node) => node.nodeType === Node.TEXT_NODE && node.textContent?.trim());
    if (!text.length) throw new Error("复选框标签缺少可读文字");
    const range = document.createRange();
    range.setStartBefore(text[0]);
    range.setEndAfter(text[text.length - 1]);
    const textBox = range.getBoundingClientRect();
    const inputBox = input.getBoundingClientRect();
    const labelBox = label.getBoundingClientRect();
    return { text: label.textContent, centerOffset: Math.abs((textBox.top + textBox.bottom - inputBox.top - inputBox.bottom) / 2), gap: textBox.left - inputBox.right, inputWidth: inputBox.width, inputHeight: inputBox.height, labelHeight: labelBox.height, right: labelBox.right };
  }));
  expect(rows.length).toBeGreaterThan(0);
  for (const row of rows) {
    expect(row.centerOffset, row.text ?? "").toBeLessThanOrEqual(2.5);
    expect(row.gap, row.text ?? "").toBeGreaterThanOrEqual(7);
    expect(row.inputWidth).toBe(20);
    expect(row.inputHeight).toBe(20);
    expect(row.labelHeight).toBeGreaterThanOrEqual(44);
    expect(row.right).toBeLessThanOrEqual(page.viewportSize()?.width ?? 0);
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
}

for (const width of [1280, 390, 320]) {
  test(`复选框统一对齐，视口 ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    let writes = 0;
    page.on("request", (request) => { if (["POST", "PUT", "PATCH", "DELETE"].includes(request.method())) writes += 1; });
    await page.goto("/premerge");
    await expect(page.getByRole("checkbox", { name: /包含历史版本/ })).toBeVisible();
    await expectCheckboxAlignment(page);
    await page.locator(".version-toggle").screenshot({ path: `test-results/history-checkbox-${width}.png` });
    await page.goto("/users");
    await expect(page.getByRole("checkbox", { name: "启用多人账号登录" })).toBeVisible();
    await expectCheckboxAlignment(page);
    await page.locator(".inline-setting").screenshot({ path: `test-results/auth-checkbox-${width}.png` });
    await page.route("**/api/auth/users", (route) => route.fulfill({ json: [{ id: 999, username: "alignment-user", role: "reader", enabled: 1, created_at: "2026-10-22 00:00:00" }] }));
    await page.reload();
    await page.getByRole("button", { name: "编辑 alignment-user" }).click();
    await expect(page.getByRole("checkbox", { name: "启用账号", exact: true })).toBeVisible();
    await expectCheckboxAlignment(page);
    await page.goto("/operations");
    await expect(page.getByRole("checkbox", { name: "主动飞书告警" })).toBeVisible();
    await expectCheckboxAlignment(page);
    await page.goto("/repositories");
    await page.getByRole("button", { name: "添加仓库" }).click();
    await expectCheckboxAlignment(page);
    await page.getByRole("button", { name: "取消", exact: true }).click();
    await page.getByRole("button", { name: "编辑 验收任务项目" }).click();
    await expectCheckboxAlignment(page);
    await page.getByRole("tab", { name: "发布审查" }).click();
    await expect(page.getByRole("checkbox", { name: "包含 GitLab MR 描述" })).toBeVisible();
    await expectCheckboxAlignment(page);
    await page.goto("/issues");
    await expect(page.getByRole("combobox", { name: "项目", exact: true })).toBeVisible();
    if (width < 621) {
      const filters = await page.locator(".issue-filters .select-field").evaluateAll((fields) => fields.map((field) => {
        const label = field.querySelector("label")?.getBoundingClientRect();
        const trigger = field.querySelector('[role="combobox"]')?.getBoundingClientRect();
        return { labelBottom: label?.bottom, triggerTop: trigger?.top, labelHeight: label?.height };
      }));
      for (const filter of filters) {
        expect(filter.labelHeight).toBeLessThan(25);
        expect(filter.labelBottom).toBeLessThanOrEqual(filter.triggerTop ?? 0);
      }
    }
    await page.route("**/api/notification-targets", (route) => route.fulfill({ json: [{ id: 999, name: "对齐测试通知", repository_count: 0, has_signing_secret: true, created_at: "2026-10-22 00:00:00", updated_at: "2026-10-22 00:00:00" }] }));
    await page.goto("/settings?tab=feishu");
    await page.getByRole("button", { name: "编辑 对齐测试通知" }).click();
    await expectCheckboxAlignment(page);
    await page.getByRole("button", { name: "取消", exact: true }).click();
    await page.goto("/settings?tab=rules");
    await page.getByRole("button", { name: "添加规则", exact: true }).click();
    await expectCheckboxAlignment(page);
    expect(writes).toBe(0);
  });
}
