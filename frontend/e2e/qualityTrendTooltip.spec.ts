/** @description 反馈图提示全日期命中、零值、跨日、周桶、滚动和触屏回归；只使用隔离服务合成数据。 */
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

async function installData(page: Page, days = 7) {
  await page.route("**/api/review-effectiveness?**", async (route) => {
    const response = await route.fetch();
    const current = await response.json();
    const counts = { total: 43, helpful: 28, false_positive: 13, ignored: 2, unmarked: 0 };
    const empty = { total: 0, helpful: 0, false_positive: 0, ignored: 0, unmarked: 0 };
    const trend = Array.from({ length: days }, (_, index) => ({
      day: new Date(Date.UTC(2026, 10, 1 + index)).toISOString().slice(0, 10),
      ...(index === 2 ? counts : index === 3 ? { ...empty, helpful: 1, total: 1 } : empty),
    }));
    await route.fulfill({ json: { ...current, quality: { ...current.quality,
      summary: { ...counts, helpful: 29, total: 44 }, trend } } });
  });
}

test("悬停柱体、空白、零值与日期交界均显示当前日数据，离开关闭", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await installData(page);
  await page.goto("/?days=7");
  const chart = page.getByRole("region", { name: "反馈趋势图，可横向滚动" });
  await chart.scrollIntoViewIfNeeded();
  const third = page.getByRole("button", { name: "查看 2026-11-03 反馈数据", exact: true });
  const box = await third.boundingBox();
  if (!box) throw new Error("日期命中区域未布局");
  for (const ratio of [0.05, 0.5, 0.98]) {
    await page.mouse.move(box.x + box.width * ratio, box.y + 8);
    await expect(page.getByRole("tooltip")).toContainText("2026-11-03（UTC）");
    await expect(page.getByRole("tooltip")).toContainText("有帮助28 条");
    await expect(page.getByRole("tooltip")).toContainText("28 条（65.1%）");
    await expect(page.getByRole("tooltip")).toContainText("未评价0 条");
    await expect(page.getByRole("tooltip")).toContainText("0 条（0.0%）");
  }
  // 图形条自身的命中也由同一透明日期带接管，不依赖窄柱高度。
  await page.mouse.move(box.x + box.width / 2, box.y + box.height - 3);
  await expect(page.getByRole("tooltip")).toContainText("总发现43 条");
  const zero = page.getByRole("button", { name: "查看 2026-11-02 反馈数据", exact: true });
  await zero.hover({ position: { x: 8, y: 12 } });
  await expect(page.getByRole("tooltip")).toContainText("2026-11-02（UTC）");
  await expect(page.getByRole("tooltip")).toContainText("总发现0 条");
  await expect(page.getByRole("tooltip")).toContainText("当天暂无发现，占比不适用");
  const fourth = page.getByRole("button", { name: "查看 2026-11-04 反馈数据", exact: true });
  const next = await fourth.boundingBox();
  if (!next) throw new Error("下一日期未布局");
  await page.mouse.move(next.x + 0.2, next.y + 10);
  await expect(page.getByRole("tooltip")).toContainText("2026-11-04（UTC）");
  await expect(page.getByRole("tooltip")).toContainText("总发现1 条");
  await expect(page.getByRole("tooltip")).toHaveCount(1);
  await page.getByRole("tooltip").screenshot({ path: "/tmp/ocr-chart-tooltip-desktop.png" });
  await page.mouse.move(5, 5);
  await expect(page.getByRole("tooltip")).toHaveCount(0);
});

test("键盘日期聚焦提示、Escape 关闭、精确数据表保留", async ({ page }) => {
  await installData(page);
  await page.goto("/?days=7");
  const target = page.getByRole("button", { name: "查看 2026-11-03 反馈数据", exact: true });
  await target.focus();
  await expect(page.getByRole("tooltip")).toContainText("总发现43 条");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("tooltip")).toHaveCount(0);
  await expect(target).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("tooltip")).toContainText("2026-11-04（UTC）");
  await page.getByRole("button", { name: "查看反馈数据", exact: true }).click();
  await expect(page.getByRole("table", { name: "反馈价值数据（UTC）" })).toContainText("2026-11-03");
});

test("90 天周桶提示日期正确，横向滚动后重新命中且不裁切", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 900 });
  await installData(page, 90);
  await page.goto("/?days=90");
  const chart = page.getByRole("region", { name: "反馈趋势图，可横向滚动" });
  await chart.scrollIntoViewIfNeeded();
  const first = page.getByRole("button", { name: "查看 2026-11-01 至 2026-11-07 反馈数据", exact: true });
  await first.focus();
  await expect(page.getByRole("tooltip")).toContainText("2026-11-01 至 2026-11-07（UTC）");
  await expect(page.getByRole("tooltip")).toContainText("有帮助29 条");
  await expect(page.getByRole("tooltip")).toContainText("29 条（65.9%）");
  await expect(page.getByRole("tooltip")).toContainText("占本区间总发现（含未评价）");
  await expect(page.getByRole("button", { name: /^查看 .* 反馈数据$/ })).toHaveCount(13);
  await page.getByRole("tooltip").screenshot({ path: "/tmp/ocr-chart-tooltip-90-share.png" });
  await chart.evaluate((element) => { element.scrollLeft = element.scrollWidth; });
  await expect(page.getByRole("tooltip")).toHaveCount(0);
  const last = page.getByRole("button", { name: "查看 2027-01-24 至 2027-01-29 反馈数据", exact: true });
  await last.hover();
  await expect(page.getByRole("tooltip")).toContainText("总发现0 条");
  await expect(page.getByRole("tooltip")).toContainText("本区间暂无发现，占比不适用");
  await expect(page.getByRole("tooltip")).toContainText("0 条（—）");
  const bounds = await page.getByRole("tooltip").boundingBox();
  expect(bounds?.x).toBeGreaterThanOrEqual(0);
  expect((bounds?.x ?? 0) + (bounds?.width ?? 0)).toBeLessThanOrEqual(390);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: "/tmp/ocr-chart-tooltip-mobile.png" });
});

test("触屏点击零值日期能打开提示，不需要鼠标或长按", async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
  try {
    const page = await context.newPage();
    await installData(page);
    await page.goto("http://127.0.0.1:8791/?days=7");
    const target = page.getByRole("button", { name: "查看 2026-11-02 反馈数据", exact: true });
    await target.tap();
    await expect(page.getByRole("tooltip")).toContainText("2026-11-02（UTC）");
    await expect(page.getByRole("tooltip")).toContainText("总发现0 条");
    await target.tap();
    await expect(page.getByRole("tooltip")).toContainText("2026-11-02（UTC）");
    await page.getByRole("button", { name: "查看 2026-11-03 反馈数据", exact: true }).tap();
    await expect(page.getByRole("tooltip")).toContainText("总发现43 条");
    await page.screenshot({ path: "/tmp/ocr-chart-tooltip-touch.png" });
    await page.getByRole("heading", { name: "评审反馈", exact: true }).tap();
    await expect(page.getByRole("tooltip")).toHaveCount(0);
  } finally {
    await context.close();
  }
});
