/** @description 在临时服务验证分层故障证据及窄屏布局；仅使用合成数据，不调用模型。 */
import { expect, test } from "@playwright/test";

for (const width of [1280, 390, 320]) {
  test(`分层诊断展示与展开 ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.route("**/api/jobs/1", async (route) => {
      const response = await route.fetch();
      await route.fulfill({ response, json: { ...await response.json(), status: "partial",
        failure_summary: "完成 40/45 个文件；1 个失败分组；模型请求存在 HTTP 504",
        failure_analysis: { schema_version: "platform.failure-analysis/v1",
          summary: "完成 40/45 个文件；1 个失败分组；模型请求存在 HTTP 504",
          selected_count: 45, completed_count: 40, failed_count: 5, failed_group_count: 1,
          report_state: "available", groups: [{ group_id: "group-2", failed_count: 5,
            paths: [`src/${"long-path/".repeat(20)}comma,name[1].ts`] }],
          requests: [{ group_id: "group-2", task_type: "plan_task", request_no: 79,
            attempts: 6, http_statuses: [504], error_classes: ["timeout"],
            failure_phases: ["http", "context"], duration_to_headers_ms: [60001, 60002],
            observed_backoff_ms: [400, 800] }],
          signals: [{ code: "http_504", message: "上游请求返回 HTTP 504，具体网关层级未知", count: 6 }],
          notes: ["仅记录报告提供的失败证据，不能计算全部成功请求的耗时分布。"],
        },
      } });
    });
    await page.goto("/jobs/1");
    const panel = page.getByRole("region", { name: "分层失败诊断" });
    await expect(panel.getByText(/完成 40\/45 个文件/)).toBeVisible();
    await panel.getByText("group-2 · 5 个文件未完成", { exact: true }).click();
    await panel.getByText("失败请求证据 · 1 条", { exact: true }).click();
    await expect(panel.getByText(/60001 \/ 60002/)).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `test-results/review-diagnostics-${width}.png`, fullPage: true });
  });
}
