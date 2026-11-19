/** @description 规则编辑布局、草稿和写入边界验收；配置全部合成，不执行真实预览或外部调用。 */
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

const savedContent = () => ({ include: ["**/*.test.ts"], exclude: ["**/node_modules/**", "**/dist/**", "**/generated/**"], rules: [
  { path: "**/*", rule: "【问题报告与分级要求】\n每条发现须提供：\n1. 问题描述\n2. 触发条件\n3. 代码依据\n4. 实际后果\n5. 修复建议\n\n不以推测替代实际代码证据。\n未确认的外部依赖须标记待核实。", merge_system_rule: true },
] });

async function fixture(page: Page) {
  await page.route("https://fonts.googleapis.com/**", (route) => route.abort());
  await page.route("**/api/review-rules", (route) => route.fulfill({ json: [{ repository_id: null, content: savedContent(), updated_at: "2026-11-13 16:38:25" }] }));
  await page.route("**/api/review-rules/**/revisions", (route) => route.fulfill({ json: [{ id: 7, action: "saved", created_at: "2026-11-13 16:38:25", content: savedContent() }] }));
}

for (const width of [1440, 1280, 768, 390, 320]) {
  test(`评审规则紧凑布局与保存栏 ${width}px`, async ({ page }, info) => {
    const errors: string[] = [], writes: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("request", (request) => { if (!["GET", "HEAD"].includes(request.method())) writes.push(request.url()); });
    await fixture(page);
    await page.setViewportSize({ width, height: 1000 });
    await page.goto("/settings?tab=rules", { waitUntil: "domcontentloaded" });
    const editor = page.getByRole("region", { name: "规则条目编辑" });
    const paths = page.getByRole("complementary", { name: "路径过滤" });
    await expect(editor).toBeVisible(); await expect(paths).toBeVisible();
    const area = await page.getByRole("textbox", { name: "审核内容", exact: true }).boundingBox();
    expect(area?.height).toBeGreaterThan(170);
    const main = await editor.boundingBox(), side = await paths.boundingBox();
    if (width >= 1280) {
      expect(Math.abs((main?.y ?? 0) - (side?.y ?? 0))).toBeLessThan(1);
      expect(side?.x).toBeGreaterThan((main?.x ?? 0) + (main?.width ?? 0));
      expect((await page.locator(".rules-context").boundingBox())?.height).toBeLessThan(110);
    } else expect(side?.y).toBeGreaterThan((main?.y ?? 0) + (main?.height ?? 0));
    await expect(page.getByRole("button", { name: "上移规则 1" })).toBeDisabled();
    await expect(page.getByRole("button", { name: "下移规则 1" })).toBeDisabled();
    await expect(page.getByRole("checkbox", { name: "同时保留 OCR 内置语言规则" })).toBeChecked();
    const save = page.getByRole("button", { name: "保存规则", exact: true });
    await save.scrollIntoViewIfNeeded();
    await expect(save).toBeInViewport();
    const lastPanel = await paths.boundingBox(), bar = await page.locator(".rules-save-bar").boundingBox();
    expect(bar?.y).toBeGreaterThan((lastPanel?.y ?? 0) + (lastPanel?.height ?? 0));
    await page.evaluate(() => scrollTo(0, 0));
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`rules-${width}.png`), fullPage: true, animations: "disabled" });
    await page.getByRole("button", { name: "添加规则", exact: true }).focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("article", { name: "规则 2", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "删除规则 2", exact: true }).click();
    await expect(page.getByRole("article")).toHaveCount(1);
    expect(errors).toEqual([]); expect(writes).toEqual([]);
  });
}

test("排序和保存保留完整草稿，失败不重试，在途冻结范围", async ({ page }) => {
  await fixture(page);
  let content = savedContent();
  await page.route("**/api/review-rules", (route) => route.fulfill({ json: [{ repository_id: null, content, updated_at: "2026-11-16 01:00:00" }] }));
  let release: () => void = () => {};
  const held = new Promise<void>((resolve) => { release = resolve; });
  const writes: unknown[] = [];
  await page.route("**/api/review-rules/global", async (route) => {
    writes.push(route.request().postDataJSON());
    if (writes.length === 1) {
      await held;
      await route.fulfill({ status: 409, json: { detail: "合成配置冲突，请核对后重试" } });
    } else {
      content = route.request().postDataJSON();
      await route.fulfill({ json: { status: "saved" } });
    }
  });
  await page.goto("/settings?tab=rules", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "添加规则", exact: true }).click();
  const second = page.getByRole("article", { name: "规则 2", exact: true });
  await second.getByLabel("文件路径模式", { exact: true }).fill("src/**/*.ts");
  await second.getByLabel("审核内容", { exact: true }).fill("合成规则：检查访问边界");
  await second.getByRole("checkbox").uncheck();
  await second.getByRole("button", { name: "上移规则 2" }).click();
  await expect(page.getByRole("article", { name: "规则 1", exact: true }).getByLabel("文件路径模式", { exact: true })).toHaveValue("src/**/*.ts");
  await page.getByLabel("额外纳入的路径", { exact: true }).fill(" **/*.test.ts \n\n docs/** ");
  await page.getByRole("button", { name: "保存规则", exact: true }).click();
  await expect(page.getByRole("combobox", { name: "配置范围" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "添加规则", exact: true })).toBeDisabled();
  await expect(page.getByLabel("排除的路径", { exact: true })).toBeDisabled();
  release();
  await expect(page.getByRole("alert")).toContainText("合成配置冲突");
  expect(writes).toHaveLength(1);
  await expect(page.getByRole("article", { name: "规则 1", exact: true }).getByLabel("审核内容", { exact: true })).toHaveValue("合成规则：检查访问边界");
  await page.getByRole("button", { name: "保存规则", exact: true }).click();
  await expect(page.getByText("审核规则已保存", { exact: true })).toBeVisible();
  expect(writes[1]).toMatchObject({ include: ["**/*.test.ts", "docs/**"], exclude: savedContent().exclude, rules: [{ path: "src/**/*.ts", rule: "合成规则：检查访问边界", merge_system_rule: false }, savedContent().rules[0]] });
  await expect(page.getByText("有未保存的更改，离开前请先保存。", { exact: true })).toHaveCount(0);
});

test("配置读取失败隐藏编辑器，重载只读并保留空状态", async ({ page }) => {
  await fixture(page);
  let fail = true;
  const writes: string[] = [];
  page.on("request", (request) => { if (!["GET", "HEAD"].includes(request.method())) writes.push(request.url()); });
  await page.route("**/api/review-rules", (route) => fail ? route.fulfill({ status: 503, json: { detail: "合成读取失败" } }) : route.fulfill({ json: [] }));
  await page.goto("/settings?tab=rules", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("alert")).toContainText("合成读取失败", { timeout: 15000 });
  await expect(page.getByRole("button", { name: "保存规则", exact: true })).toHaveCount(0);
  fail = false;
  await page.getByRole("button", { name: "重新加载", exact: true }).click();
  await expect(page.getByText("当前范围尚无自定义条目", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "删除配置", exact: true })).toBeDisabled();
  expect(writes).toEqual([]);
});

test("展开辅助区只读，取消删除和恢复不写入，草稿禁止实际预览", async ({ page }) => {
  await fixture(page);
  const writes: string[] = [];
  page.on("request", (request) => { if (!["GET", "HEAD"].includes(request.method())) writes.push(request.url()); });
  await page.goto("/settings?tab=rules", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "版本历史 · 最近 50 次变更", exact: true }).click();
  await expect(page.getByText("版本 #7", { exact: true })).toBeVisible();
  await page.getByText("查看版本内容", { exact: true }).click();
  await expect(page.locator(".rule-revision pre")).toContainText('"merge_system_rule": true');
  page.once("dialog", (dialog) => dialog.dismiss());
  await page.getByRole("button", { name: "恢复", exact: true }).click();
  page.once("dialog", (dialog) => dialog.dismiss());
  await page.getByRole("button", { name: "删除配置", exact: true }).click();
  await expect(page.getByLabel("审核内容", { exact: true })).toHaveValue(savedContent().rules[0].rule);
  await page.getByLabel("额外纳入的路径", { exact: true }).fill("**/draft.ts");
  await page.getByRole("button", { name: "规则预览与反馈", exact: true }).click();
  await page.getByLabel("仓库内文件路径", { exact: true }).fill("src/main.py");
  await expect(page.getByRole("button", { name: "检查命中规则", exact: true })).toBeDisabled();
  expect(writes).toEqual([]);
});
