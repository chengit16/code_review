/** @description 合成来源验收聊天自动受理、可逆关联、撤权、查询失败与窄屏；不读取实际聊天。 */
import { expect, test } from "@playwright/test";

test.skip(process.env.OCR_BROWSER_CHAT_CAPTURE !== "1", "需显式启用独立合成聊天验收通道");

for (const width of [1280, 320]) {
  test(`聊天收件箱 ${width}px：自动受理与查询失败可见`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto("/improvements");
    await page.getByText(/^聊天自动受理与待核实收件箱/).click();
    await expect(page.getByText(/近期采集正常/)).toBeVisible();
    await expect(page.getByText("合成按钮报错", { exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "查看关联记录 #1" })).toBeVisible();
    const panel = page.locator("details").filter({ has: page.getByText(/^聊天自动受理与待核实收件箱/) });
    await expect(panel.getByText(/验证和部署仍以实际证据为准/)).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.route("**/api/chat-capture?**", (route) => route.fulfill({ status: 503, json: { detail: "合成采集查询失败" } }));
    await expect(panel.getByRole("alert")).toContainText("合成采集查询失败", { timeout: 10000 });
    await expect(panel.getByText(/近期采集正常/)).toHaveCount(0);
    expect(errors).toEqual([]);
  });
}

test("候选关联可逆且持久化，暂停后不会宣称正在采集", async ({ page }) => {
  await page.goto("/improvements");
  await page.getByText(/^聊天自动受理与待核实收件箱/).click();
  const row = page.locator("article").filter({ has: page.getByRole("heading", { name: "来源 #2 · 待核实" }) });
  await row.getByLabel("来源 #2 关联记录编号").fill("1");
  await row.getByRole("button", { name: "关联已有记录" }).click();
  await expect(row.getByRole("link", { name: "查看关联记录 #1" })).toBeVisible();
  await row.getByRole("button", { name: "解除关联" }).click();
  await expect(row.getByText("未关联正式记录")).toBeVisible();
  await page.getByRole("button", { name: "暂停采集 #1" }).click();
  await expect(page.getByText(/绑定 #1 · 已暂停/)).toBeVisible();
  await page.reload();
  await page.getByText(/^聊天自动受理与待核实收件箱/).click();
  await expect(page.getByText(/绑定 #1 · 已暂停/)).toBeVisible();
  await expect(row.getByText("未关联正式记录")).toBeVisible();
  await page.getByRole("button", { name: "恢复采集 #1" }).click();
  await expect(page.getByRole("button", { name: "暂停采集 #1" })).toBeVisible();
});
