/** @description 验证触发与背景分区、诊断对齐、页签滚动及回调复制区；不调用真实外部服务。 */
import { expect, test } from "@playwright/test";
import { mockRepositoryQuery } from "./unifiedFixture";

for (const width of [1440, 768, 390, 320]) {
  test(`仓库分区无重复开关，诊断与回调布局可用 ${width}px`, async ({ page }, testInfo) => {
    await mockRepositoryQuery(page);
    await page.setViewportSize({ width, height: 900 });
    const errors: string[] = []; page.on("pageerror", (error) => errors.push(error.message));
    const writes: Record<string, unknown>[] = [];
    let premerge = { enabled: true, include_description: false, context_paths: [] as string[] };
    await page.route("**/api/repositories/1/premerge", async (route) => {
      if (route.request().method() === "PUT") {
        const body = route.request().postDataJSON(); writes.push(body); premerge = { ...premerge, ...body };
      }
      await route.fulfill({ json: premerge });
    });
    await page.goto("/repositories");
    const callback = page.getByRole("region", { name: "GitLab Webhook 接入地址" });
    await expect(callback.getByRole("textbox", { name: "GitLab 回调地址" })).toBeVisible();
    await expect(callback.getByRole("button", { name: "复制地址" })).toBeVisible();
    await page.getByRole("button", { name: "编辑 验收任务项目" }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByRole("checkbox", { name: "合并前 MR 评审", exact: true })).toBeVisible();
    await expect(dialog.getByRole("checkbox", { name: "合并后评审（Merge Request）" })).toHaveCount(0);
    await dialog.getByRole("tab", { name: "评审参数" }).click();
    await expect(dialog.getByRole("heading", { name: "合并前审查背景" })).toBeVisible();
    await expect(dialog.getByRole("switch", { name: "审查未合并 MR 的完整差异" })).toHaveCount(0);
    const paths = dialog.getByRole("textbox", { name: "仓库业务文档路径" });
    await paths.fill("docs/context.md");
    await dialog.getByRole("button", { name: "保存合并前配置" }).click();
    await expect(dialog.getByText("合并前配置已保存", { exact: true })).toBeVisible();
    expect(writes).toEqual([{ include_description: false, context_paths: ["docs/context.md"] }]);
    await dialog.getByRole("tab", { name: "结果发布" }).click();
    await expect(dialog.getByRole("heading", { name: "GitLab 行内评论" })).toBeVisible();
    await expect(paths).toBeHidden();
    await dialog.getByRole("tab", { name: "接入诊断" }).click();
    await expect(dialog.getByRole("heading", { name: "连接测试", exact: true })).toBeVisible();
    await expect(dialog.locator(".repository-diagnosis").getByText("连接测试 · 最近结果", { exact: true })).toHaveCount(0);
    await expect.poll(() => dialog.locator(".repository-editor-body").evaluate((element) => element.scrollTop)).toBe(0);
    await dialog.locator(".diagnosis-tests").scrollIntoViewIfNeeded();
    await page.screenshot({ path: testInfo.outputPath(`diagnosis-${width}.png`), animations: "disabled" });
    await dialog.getByRole("tab", { name: "基础接入" }).click();
    await expect.poll(() => dialog.locator(".repository-editor-body").evaluate((element) => element.scrollTop)).toBe(0);
    expect(await dialog.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(errors).toEqual([]);
  });
}
