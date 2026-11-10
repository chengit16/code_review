/** @description 全局列表五档视口、长文本、键盘、真实历史分页与返回上下文验收；只连接临时服务。 */
import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";

for (const width of [1440, 1280, 768, 390, 320]) {
  test(`统一列表在 ${width}px 保留核心事实且不产生页面横向溢出`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 1000 });
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    const title = `列表长标题-${randomUUID()}-${"合成范围".repeat(12)}`;
    const record = await (await page.request.post("/api/improvements", { data: {
      client_key: randomUUID(), title, description: "只做合成列表验收", scope: "跨页面长范围".repeat(8),
      code_state: "modified", verification_state: "passed", validation_evidence: "合成测试", deployment_state: "not_deployed",
    } })).json();
    const theme = await (await page.request.post("/api/improvement-themes", { data: {
      client_key: randomUUID(), title, objective: "长目标".repeat(80), phases: [{ title: "阶段甲", goal: "未完成" }, { title: "阶段乙", goal: "未完成" }],
    } })).json();
    await page.route("**/api/premerge-search?**", (route) => route.fulfill({ json: {
      items: [{ id: 999, repository_name: "合成长项目名称".repeat(8), mr_iid: 7, head_sha: "a".repeat(40), status: "partial", created_at: "2025-01-01 12:00:00", summary: { result_available: true, findings_count: 3, highest_severity: "high", coverage: "partial", excluded_count: 2, waived_count: 1 } }], total: 1, page: 1, page_size: 25, status_counts: { all: 1, partial: 1 },
    } }));
    const pages = [
      ["/jobs", "评审任务"], ["/issues", "历史问题与修复记录"], ["/findings", "评审发现"], ["/premerge", "合并前审查"], ["/events", "合并事件"],
      [`/improvements?q=${encodeURIComponent(title)}`, "问题与改进"], [`/improvements?view=themes&theme_q=${encodeURIComponent(title)}`, "问题与改进"],
      ["/repositories", "项目配置"], ["/settings", "系统设置"], ["/feishu", "系统设置"], ["/config-history", "配置历史"], ["/users", "访问权限"],
    ];
    for (const [path, heading] of pages) {
      await page.goto(path);
      await expect(page.getByRole("heading", { name: heading, level: 1, exact: true })).toBeVisible();
      await expect(page.locator(".compact-list-table, .jobs-table").first()).toBeVisible();
      await expect(page.locator(".ant-spin-spinning")).toHaveCount(0);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), path).toBe(true);
      if (path.startsWith("/improvements?q=")) {
        const row = page.getByRole("row").filter({ hasText: title });
        await expect(row).toContainText("代码已修改");
        await expect(row).toContainText("本地验证通过");
        await expect(row).toContainText("未部署");
        await row.getByText("代码已修改", { exact: true }).click();
        await page.getByRole("link", { name: /返回/ }).first().click();
        await expect(page).toHaveURL(new RegExp(`q=${encodeURIComponent(title)}`));
        await expect(page.getByRole("link", { name: `#${record.id} · ${title}`, exact: true })).toBeVisible();
      }
      if (path.includes("view=themes")) {
        const row = page.getByRole("row", { name: `查看主题 ${theme.id}`, exact: true });
        await expect(row).toContainText("0 / 2 阶段已完成");
        await expect(page.getByRole("columnheader", { name: "操作", exact: true })).toHaveCount(0);
        await row.focus();
        await page.keyboard.press("Enter");
        await expect(page).toHaveURL(new RegExp(`/improvements/themes/${theme.id}`));
        await page.getByRole("link", { name: /返回/ }).first().click();
        await expect(row).toBeVisible();
      }
      if (path === "/premerge") {
        await expect(page.getByText("覆盖不完整 · 排除 2 · 豁免 1", { exact: true })).toBeVisible();
        const time = page.getByRole("button", { name: /2025.*Asia/ });
        await time.focus();
        await expect(page.getByRole("tooltip")).toContainText("2025");
        await page.keyboard.press("Tab");
      }
      await expect(page.locator(".ant-spin-spinning")).toHaveCount(0);
      if ([1440, 320].includes(width)) await page.screenshot({ animations: "disabled", path: testInfo.outputPath(`${path.split("?")[0].slice(1)}${path.includes("themes") ? "-themes" : ""}-${width}.png`) });
    }
    expect(errors).toEqual([]);
  });
}

test("配置历史全量分页访问百条以外版本，未知与密钥保持安全", async ({ page }) => {
  // 仅插入合成配置版本；分页请求真正走后端，不由前端切最近百条。
  const repo = (await (await page.request.get("/api/repositories")).json())[0];
  for (let index = 0; index < 102; index += 1) {
    expect((await page.request.patch(`/api/repositories/${repo.id}`, { data: { name: `历史验收-${index}` } })).ok()).toBe(true);
  }
  await page.goto(`/config-history?object_id=${repo.id}&page_size=100&page=2`);
  await expect(page.getByText(/第 2 \/ 2 页/)).toBeVisible();
  await expect(page.getByRole("row").filter({ hasText: "新增" })).toBeVisible();
  await page.getByRole("row").filter({ hasText: "新增" }).getByRole("button", { name: /查看差异/ }).click();
  await expect(page.getByRole("dialog")).toContainText("凭据已变更，明文不回显");
  await expect(page.getByRole("dialog")).not.toContainText("synthetic-http-token");
  // 恢复原名称，避免影响其他套件定位；不执行历史恢复或外部连接。
  expect((await page.request.patch(`/api/repositories/${repo.id}`, { data: { name: repo.name } })).ok()).toBe(true);
});
