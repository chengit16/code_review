/** @description 发布审查的布局、键盘、草稿及自动保存回归；仅操作临时服务和合成配置。 */
import { expect, test } from "@playwright/test";

for (const width of [1440, 768, 390, 320]) {
  test(`发布审查开关分行、保存独立且接入说明可读 ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 1000 });
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    let premerge = { enabled: false, include_description: false, context_paths: [] as string[] };
    let publication = { enabled: false };
    const writes: string[] = [];
    await page.route("**/api/repositories/1/premerge", async (route) => {
      if (route.request().method() === "PUT") { premerge = route.request().postDataJSON(); writes.push("premerge"); }
      await route.fulfill({ json: premerge });
    });
    await page.route("**/api/repositories/1/gitlab-publication", async (route) => {
      if (route.request().method() === "PUT") { publication = route.request().postDataJSON(); writes.push("publication"); }
      await route.fulfill({ json: publication });
    });
    await page.goto("/repositories?repository=1&section=publication");
    const dialog = page.getByRole("dialog");
    await expect(dialog).toContainText("自动保存");
    await expect(dialog).toContainText("手动保存");
    await expect(dialog.getByRole("note")).toContainText("结果在平台「合并前审查」查看");
    const toggle = dialog.getByRole("switch", { name: "审查未合并 MR 的完整差异" });
    await toggle.focus();
    await page.keyboard.press("Space");
    await expect(toggle).toBeChecked();
    expect(writes).toEqual([]);
    const description = dialog.getByRole("checkbox", { name: "包含 GitLab MR 描述" });
    await description.check();
    const paths = dialog.getByRole("textbox", { name: "仓库业务文档路径" });
    await paths.fill("docs/context.md");
    const layout = await dialog.evaluate((element) => {
      const toggle = element.querySelectorAll(".publication-toggle-row")[1];
      const context = element.querySelector(".publication-context");
      return { toggleBottom: toggle?.getBoundingClientRect().bottom, contextTop: context?.getBoundingClientRect().top };
    });
    expect(layout.contextTop).toBeGreaterThan(layout.toggleBottom ?? 0);
    await dialog.getByRole("button", { name: "保存合并前配置" }).click();
    await expect(dialog.getByText("合并前配置已保存", { exact: true })).toBeVisible();
    expect(premerge).toEqual({ enabled: true, include_description: true, context_paths: ["docs/context.md"] });
    await dialog.getByRole("switch", { name: "向 MR 发布可定位的评审发现" }).click();
    await expect(dialog.getByText("行内评论配置已保存", { exact: true })).toBeVisible();
    expect(writes).toEqual(["premerge", "publication"]);
    await page.screenshot({ path: testInfo.outputPath(`publication-${width}.png`), animations: "disabled" });
    await dialog.getByRole("button", { name: "自动触发需要哪些配置？" }).click();
    await expect(dialog.getByText("Merge request events", { exact: true })).toBeVisible();
    await expect(dialog.getByText("main", { exact: true })).toBeVisible();
    await expect(dialog.getByText(/未收到过事件的已有 MR 不会自动补扫/)).toBeVisible();
    await paths.fill("docs/unsaved.md");
    await dialog.getByRole("button", { name: "查看接入诊断" }).click();
    await expect(page).toHaveURL(/section=diagnosis/);
    await dialog.getByRole("tab", { name: "发布审查" }).click();
    await expect(paths).toHaveValue("docs/unsaved.md");
    await expect(dialog.getByText("合并前配置已保存", { exact: true })).toHaveCount(0);
    expect(await dialog.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await dialog.getByRole("button", { name: "查看接入诊断" }).scrollIntoViewIfNeeded();
    await page.screenshot({ path: testInfo.outputPath(`publication-help-${width}.png`), animations: "disabled" });
    await dialog.getByRole("button", { name: "关闭", exact: true }).focus();
    const dismissed = page.waitForEvent("dialog").then((confirmation) => confirmation.dismiss());
    await page.keyboard.press("Escape");
    await dismissed;
    await expect(dialog).toBeVisible();
    const accepted = page.waitForEvent("dialog").then((confirmation) => confirmation.accept());
    await dialog.getByRole("button", { name: "关闭", exact: true }).click();
    await accepted;
    await expect(dialog).toHaveCount(0);
    expect(errors).toEqual([]);
  });
}
