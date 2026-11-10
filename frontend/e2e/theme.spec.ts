/**
 * @description 验证参考图的灰白蓝主题、状态区分和响应式布局。
 * 只访问隔离服务，配置弹窗仅打开与取消，不提交业务写入。
 */
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

const colors = {
  canvas: "rgb(245, 245, 245)",
  surface: "rgb(255, 255, 255)",
  ink: "rgb(38, 38, 38)",
  border: "rgb(217, 217, 217)",
  accent: "rgb(22, 119, 255)",
  accentText: "rgb(9, 88, 217)",
  accentSoft: "rgb(230, 244, 255)",
  success: "rgb(56, 158, 13)",
  danger: "rgb(207, 19, 34)",
  warning: "rgb(173, 104, 0)",
};

async function expectNoOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
}

for (const width of [1440, 390, 320]) {
  test(`灰白蓝主题覆盖导航、表单、表格及弹窗，视口 ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const writes: string[] = [];
    page.on("request", (request) => {
      if (["POST", "PUT", "PATCH", "DELETE"].includes(request.method())) writes.push(request.url());
    });
    await page.goto("/repositories");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("项目配置");
    await expect(page.locator("html")).toHaveCSS("background-color", colors.canvas);
    await expect(page.locator(".sidebar")).toHaveCSS("background-color", colors.surface);
    const activeLink = page.locator(".nav-link.active");
    await expect(activeLink).toHaveCSS("background-color", colors.accentSoft);
    await expect(activeLink).toHaveCSS("color", colors.accent);
    const add = page.getByRole("button", { name: "添加仓库", exact: true });
    await expect(add).toHaveCSS("background-color", colors.accent);
    await expect(page.locator(".repository-table-card").first()).toHaveCSS("background-color", colors.surface);

    if (width < 900) {
      await page.getByRole("button", { name: "打开导航" }).click();
      await expect(page.getByRole("navigation", { name: "主导航" })).toBeVisible();
      await expect(page.locator(".sidebar")).toHaveCSS("transform", "matrix(1, 0, 0, 1, 0, 0)");
      await expect(activeLink).toBeVisible();
      await expect(page.getByRole("button", { name: "关闭导航", exact: true }).last()).toHaveCSS("color", "rgb(102, 102, 102)");
      await page.screenshot({ path: `test-results/theme-navigation-${width}.png` });
      await page.keyboard.press("Escape");
      await expect(page.getByRole("button", { name: "打开导航" })).toBeFocused();
    }

    await page.screenshot({ path: `test-results/theme-repositories-${width}.png`, fullPage: true });
    await add.click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toHaveCSS("background-color", colors.surface);
    const name = page.getByLabel("仓库名称", { exact: true });
    await expect(name).toHaveCSS("border-top-color", colors.border);
    await expect(name).toHaveCSS("color", colors.ink);
    await name.focus();
    await expect(name).toHaveCSS("border-top-color", colors.accent);
    await expectNoOverflow(page);
    await page.screenshot({ path: `test-results/theme-repository-modal-${width}.png` });
    await page.getByRole("button", { name: "取消", exact: true }).click();
    await expect(dialog).toHaveCount(0);

    await page.goto("/jobs");
    const status = page.getByRole("combobox", { name: "发现反馈", exact: true });
    await status.click();
    const complete = page.getByRole("option", { name: "发现全部已处理", exact: true });
    await complete.hover();
    await expect(complete).toHaveCSS("background-color", colors.accentSoft);
    await expect(complete).toHaveCSS("color", colors.ink);
    await complete.click();
    await page.getByRole("button", { name: "查询", exact: true }).click();
    await expect(page).toHaveURL("/jobs?feedback_state=handled");
    await expect(page.locator(".jobs-filter-field .ant-select").filter({ has: status })).toContainText("发现全部已处理");
    await expectNoOverflow(page);
    await page.screenshot({ path: `test-results/theme-jobs-${width}.png`, fullPage: true });

    await page.goto("/settings?tab=rules");
    await expect(page.getByRole("tab", { name: "评审规则" })).toHaveCSS("color", colors.accentText);
    await expect(page.getByRole("button", { name: "保存规则", exact: true })).toHaveCSS("background-color", colors.accent);
    await expectNoOverflow(page);
    await page.screenshot({ path: `test-results/theme-settings-${width}.png`, fullPage: true });
    expect(writes).toEqual([]);
  });
}

test("成功、警告、失败与完成保持不同语义色，页面不残留旧绿主题", async ({ page }) => {
  await page.goto("/jobs/1");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  const statusColors = await page.evaluate(() => {
    const element = document.createElement("span");
    document.body.append(element);
    const result = Object.fromEntries(["complete", "enabled", "partial", "failed"].map((state) => {
      element.className = `status status--${state}`;
      return [state, getComputedStyle(element).color];
    }));
    element.remove();
    return result;
  });
  expect(statusColors).toEqual({ complete: colors.accentText, enabled: colors.success, partial: colors.warning, failed: colors.danger });

  for (const path of ["/", "/jobs/1", "/events", "/issues", "/premerge", "/operations", "/config-history", "/improvements", "/onboarding", "/users"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    const oldColors = await page.locator("body *").evaluateAll((elements) => elements.filter((element) => {
      const style = getComputedStyle(element);
      return [style.color, style.backgroundColor, style.borderTopColor].some((color) => ["rgb(20, 120, 100)", "rgb(32, 48, 47)", "rgb(54, 88, 79)"].includes(color));
    }).map((element) => element.className));
    expect(oldColors, path).toEqual([]);
    await expectNoOverflow(page);
  }
  await page.goto("/");
  await page.screenshot({ path: "test-results/theme-overview-desktop.png", fullPage: true });
});
