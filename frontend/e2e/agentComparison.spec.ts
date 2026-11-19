/** @description 使用合成 Worker 与真实隔离 API 验收比较、裁定和单侧重跑。 */

import { expect, test } from "@playwright/test";

test.describe("任务双评审", () => {
  test.skip(process.env.OCR_BROWSER_AGENT_COMPARISON !== "1", "需要双评审隔离夹具");

  test("确认同根因、保留并发草稿、单侧重跑和回看历史", async ({ page, request }, info) => {
    await page.setViewportSize({ width: 1440, height: 1050 });
    await page.goto("/jobs/1#job-agent-comparison");
    const panel = page.getByRole("region", { name: "双评审对比" });
    await expect(panel.getByText("阿里 OCR", { exact: true })).toBeVisible();
    await expect(panel.getByText("自建 Agent", { exact: true })).toBeVisible();
    await expect(panel.getByText("25/25", { exact: true })).toBeVisible();
    await panel.screenshot({ path: info.outputPath("comparison-desktop.png") });
    await panel.getByRole("button", { name: "核对匹配" }).click();
    await page.getByRole("textbox", { name: "共同根因" }).fill("重试路径缺少订单去重");
    await page.getByRole("button", { name: "保存裁定" }).click();
    await expect(panel.getByText("重试路径缺少订单去重", { exact: true })).toBeVisible();
    await panel.getByText("Agent 独有（1）", { exact: true }).click();
    await expect(panel.getByText("阿里 OCR", { exact: true })).toHaveCount(0);
    await expect(panel.getByRole("button", { name: "查看证据：重试造成重复登记" })).toHaveCount(0);
    await panel.getByRole("button", { name: "查看证据：重试入口没有校验订单号" }).click();
    const evidence = page.getByRole("dialog", { name: "固定版本证据" });
    await expect(evidence.getByText("orders.py · 新版第 1 行")).toBeVisible();
    await expect(evidence.getByText("def retry_order(order_id):", { exact: true })).toBeVisible();
    await evidence.getByRole("button", { name: "裁定发现" }).click();
    const edit = page.getByRole("dialog", { name: "裁定发现" });
    await edit.getByRole("radio", { name: "成立", exact: true }).check();
    await edit.getByRole("textbox", { name: "备注" }).fill("在旧版比较核对了入口证据");
    const url = "/api/jobs/1/agent-comparisons/1";
    const current = await (await request.get(url)).json();
    const other = await request.put(`${url}/curation`, { data: {
      expected_version: current.curation.version,
      document: { ...current.curation.document, missed: [{ id: "missed:other", path: "orders.py",
        title: "并发补录的共同漏报", line: 8, side: "head" }] },
    } });
    expect(other.ok()).toBe(true);
    await edit.getByRole("button", { name: "保存裁定" }).click();
    await expect(edit.getByText("另一位评审者已更新裁定，请保留草稿并核对")).toBeVisible();
    await expect(edit.getByRole("textbox", { name: "备注" })).toHaveValue("在旧版比较核对了入口证据");
    await edit.getByRole("button", { name: "读取最新裁定" }).click();
    await expect(edit.getByText("已读取裁定 v2")).toBeVisible();
    await edit.getByRole("button", { name: "保存裁定" }).click();
    await expect(panel.getByText("并发补录的共同漏报")).toBeVisible();
    await expect(panel.getByText("成立", { exact: true })).toBeVisible();
    await panel.getByRole("button", { name: "重跑 Agent" }).click();
    await page.getByRole("button", { name: "确认入队" }).click();
    await expect(page).toHaveURL(/agent_comparison=2/);
    await expect(panel.getByText("OCR 初审第 1 次 · Agent #2")).toBeVisible();
    await expect(panel.getByText("25/25", { exact: true })).toBeVisible({ timeout: 10000 });
    await panel.getByRole("combobox", { name: "比较版本" }).click();
    await page.getByRole("option", { name: /Agent #1/ }).click();
    await expect(panel.getByText("OCR 初审第 1 次 · Agent #1")).toBeVisible();
    await expect(panel.getByText("成立", { exact: true })).toBeVisible();
    await panel.getByRole("button", { name: "上一条裁定" }).click();
    await expect(panel.getByRole("button", { name: "回到最新裁定" })).toBeVisible();
    await expect(panel.getByText("成立", { exact: true })).toHaveCount(0);
    await panel.getByRole("button", { name: "回到最新裁定" }).click();
    await expect(panel.getByText("成立", { exact: true })).toBeVisible();
    const latest = await (await request.get(url)).json();
    expect(latest.curation.document.evaluations[0].note).toBe("在旧版比较核对了入口证据");
    await panel.getByRole("button", { name: "补录共同漏报" }).click();
    const missed = page.getByRole("dialog", { name: "补录共同漏报" });
    await missed.getByRole("textbox", { name: "问题说明" }).fill("订单号格式没有校验");
    await missed.getByRole("textbox", { name: "文件路径" }).fill("orders.py");
    await missed.getByRole("button", { name: "保存裁定" }).click();
    await expect(panel.getByText("订单号格式没有校验", { exact: true })).toBeVisible();
    await panel.getByRole("button", { name: "编辑分组" }).click();
    await page.getByRole("button", { name: "拆除分组" }).click();
    await expect(panel.getByText("同位置待核对", { exact: true })).toBeVisible();
  });

  test("窄屏可以切换到历史、展开证据并用键盘关闭", async ({ page }, info) => {
    await page.goto("/jobs/1?agent_comparison=1#job-agent-comparison");
    const panel = page.getByRole("region", { name: "双评审对比" });
    await expect(panel.getByText("OCR 初审第 1 次 · Agent #1")).toBeVisible();
    for (const width of [390, 320]) {
      await page.setViewportSize({ width, height: 820 });
      const sizes = await panel.evaluate((element) => ({ scroll: element.scrollWidth, width: element.clientWidth }));
      expect(sizes.scroll).toBeLessThanOrEqual(sizes.width);
      await panel.screenshot({ path: info.outputPath(`comparison-${width}.png`) });
    }
    const button = panel.getByRole("button", { name: "查看证据：重试造成重复登记" });
    await button.focus();
    await page.keyboard.press("Enter");
    const dialog = page.getByRole("dialog", { name: "固定版本证据" });
    await expect(dialog.getByText("orders.py · 新版第 24 行")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await page.goto("/jobs/2#job-agent-comparison");
    await expect(panel.getByText("仅 OCR", { exact: true })).toBeVisible();
    await expect(panel.getByRole("button", { name: "运行 Agent" })).toBeDisabled();
  });
});
