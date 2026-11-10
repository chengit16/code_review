/** @description 发现换行与安全代码块的桌面和手机验收；仅使用合成接口正文与隔离剪贴板。 */
import { expect, test } from "@playwright/test";

const code = [
  "const styles = StyleSheet.create({",
  "  descStyleWrap: {",
  "    borderWidth: 1,",
  "    borderColor: 'transparent',",
  "    borderRadius: 8,",
  "    paddingHorizontal: 8,",
  "    paddingVertical: 4,",
  "  },",
  "  descStyle: { fontSize: 14 },",
  "});",
  `const note = "${"syntheticLongCode".repeat(22)}";`,
  'const lines = note.split("\\n");',
].join("\n");

for (const width of [1440, 390, 320]) {
  test(`发现 Markdown ${width}px：标签转义换行、代码滚动、键盘复制及失败恢复`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 1100 });
    await page.addInitScript(() => {
      Object.defineProperty(navigator, "clipboard", { configurable: true, value: {
        writeText: async (text: string) => {
          if (!Reflect.get(window, "__copyAttempted")) {
            Reflect.set(window, "__copyAttempted", true);
            throw new Error("合成拒绝");
          }
          Reflect.set(window, "__copiedCode", text);
        },
      } });
      Object.defineProperty(document, "execCommand", { configurable: true, value: () => false });
    });
    await page.route("**/api/jobs/1", async (route) => {
      const response = await route.fetch();
      const job = await response.json();
      job.result.comments = [{ ...job.result.comments[0], content:
        `触发条件：打开弹窗。\\n代码依据：保留 \\n 原文说明和行内代码 \`value.split("\\n")\`。\\n实际后果：样式缺失。\\n修复建议：**保留样式定义**，补齐以下样式。\n\n参考改法：\n\n\`\`\`ts\n${code}\n\`\`\`\n\n- 核对样式名称\n- 核对导入依赖\n\n[文档](https://example.com/doc) [危险](javascript:alert%281%29)\n\n<img src=x onerror=alert(1)>`,
      }];
      await route.fulfill({ response, json: job });
    });
    await page.goto("/jobs/1");
    const card = page.getByRole("article", { name: "发现 1", exact: true });
    for (const name of ["触发条件", "代码依据", "实际后果", "修复建议"]) await expect(card.getByRole("heading", { name, exact: true })).toBeVisible();
    const block = card.locator(".finding-code-block");
    await expect(block.locator("pre code")).toHaveText(code);
    expect(await block.locator("pre code").textContent()).toBe(code);
    expect(await block.locator("pre").evaluate((element) => element.scrollWidth > element.clientWidth)).toBe(true);
    await expect(card.locator("img, script")).toHaveCount(0);
    await expect(card.getByRole("link", { name: "危险" })).toHaveCount(0);
    const copy = block.getByRole("button", { name: "复制代码" });
    await copy.focus();
    await page.keyboard.press("Enter");
    await expect(block.getByRole("status")).toHaveText("复制失败，请手动选择代码复制。");
    await page.keyboard.press("Enter");
    await expect(block.getByRole("status")).toHaveText("代码已复制");
    expect(await page.evaluate(() => Reflect.get(window, "__copiedCode"))).toBe(code);
    await expect(copy).toBeFocused();
    const box = await copy.boundingBox();
    const caption = await block.locator("figcaption").boundingBox();
    expect(box).not.toBeNull();
    expect(caption).not.toBeNull();
    if (box && caption) expect(box.x + box.width).toBeLessThanOrEqual(caption.x + caption.width);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await card.screenshot({ path: testInfo.outputPath(`finding-markdown-${width}.png`), animations: "disabled" });
  });
}

test("合并前失败保留发现中的代码建议，安全展示而不改变审查结论", async ({ page }) => {
  const review = { id: 900, repository_id: 1, repository_name: "合成项目", mr_iid: 3, head_sha: "a".repeat(40), status: "failed",
    result_json: JSON.stringify({ comments: [{ path: "src/styles.ts", content: `问题描述：样式缺失。\\n修复建议：保留定义。\n\`\`\`ts\n${code}\n\`\`\`` }] }),
    error: "合成执行失败", created_at: "2026-11-09 01:00:00" };
  await page.route("**/api/premerge-search*", (route) => route.fulfill({ json: { items: [review], total: 1, page: 1, page_size: 25 } }));
  await page.route("**/api/premerge-reviews/900", (route) => route.fulfill({ json: review }));
  await page.setViewportSize({ width: 390, height: 900 });
  await page.goto("/premerge?review=900");
  await expect(page.getByText(/审查失败，无法形成完整结论/)).toBeVisible();
  const detail = page.locator(".premerge-detail");
  await expect(detail.getByRole("heading", { name: "修复建议", exact: true })).toBeVisible();
  expect(await detail.locator(".finding-code-block pre code").textContent()).toBe(code);
  await expect(detail.getByRole("button", { name: "复制代码" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
