/** @description 在临时服务验证耗时、跳过原因和范围诊断的桌面及窄屏展示；不访问业务端口。 */
import { expect, test } from "@playwright/test";

for (const width of [1280, 390, 320]) {
  test(`评审原因与累计耗时无横向溢出 ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const timing = { first_queue_seconds: 21600, latest_execution_seconds: 1,
      cumulative_execution_seconds: 1, execution_complete: true, known_attempts: 1,
      total_attempts: 1, total_elapsed_seconds: 21601, retry_backoff_seconds: 0,
      retry_ready_wait_seconds: 0, schedule_complete: true, calculated_at: "2026-01-01T06:00:01Z" };
    await page.route("**/api/task-search?*", (route) => route.fulfill({ json: {
      items: [{ id: 1, repository_id: 1, repository_name: "合成换行分析项目", event_id: 1,
        mr_iid: 7, commit_sha: "a".repeat(40), ordinal: 0, status: "skipped", attempts: 1,
        error: null, finding_count: 0, target_branch: "main", commit_author: "合成作者",
        created_at: "2026-01-01 00:00:00", finished_at: "2026-01-01 06:00:01", timing,
        reason: { code: "excluded_by_rules", message: "变更文件均被 OCR 规则排除，未调用模型" } }],
      total: 1, page: 1, page_size: 25,
    } }));
    await page.goto("/jobs");
    const summary = width < 700 ? page.locator(".task-mobile-summary") : page.locator("td[data-label='评审状态']");
    await expect(summary.getByText("已跳过", { exact: true })).toBeVisible();
    const times = width < 700 ? summary : page.locator("td[data-label='耗时 / 尝试']");
    await expect(times.getByText("初审执行 1 秒").first()).toBeVisible();
    await expect(times.getByText("初审 1 次 · 补审 0 次").first()).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `test-results/review-execution-list-${width}.png`, fullPage: true });
    // 详情保留隔离服务的基础字段，仅覆盖合成诊断，验证长路径与三次执行的真实布局。
    await page.route("**/api/jobs/1", async (route) => {
      const response = await route.fetch();
      await route.fulfill({ response, json: { ...await response.json(),
        status: "failed", attempts: 3,
        reason: { code: "timeout", message: "评审预算耗尽，不自动整批重试" },
        timing: { ...timing, cumulative_execution_seconds: 10800, latest_execution_seconds: 3600,
          total_attempts: 3, known_attempts: 3, total_elapsed_seconds: 39600 },
        scope_analysis: { mode: "analyze_only", status: "limited", original_count: 1460,
          newline_only_count: 1400, newline_only_paths: [`src/${"long-path/".repeat(12)}main.py`],
          excluded_count: 0, checked_count: 1450, filter_enabled: false,
          filter_reason: "当前仅分析不排除", ocr_candidate_count: 1460, ocr_excluded_count: 0 },
        cumulative_usage: { known_usage_attempts: 1, total_attempts: 3, usage_complete: false,
          priced_attempts: 1, known_tokens: { total_tokens: 750000 },
          known_costs: [{ currency: "CNY", total: "3" }], cost_complete: false },
      } });
    });
    await page.goto("/jobs/1");
    await expect(page.getByRole("heading", { name: "耗时与范围诊断" })).toBeVisible();
    await expect(page.getByText("3 小时 0 分", { exact: true })).toBeVisible();
    await expect(page.getByText("仅已知部分，费用不完整")).toBeVisible();
    await page.getByText("查看仅换行文件（实际策略排除 0 个）", { exact: true }).click();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `test-results/review-execution-detail-${width}.png`, fullPage: true });
    // 同一范围开启过滤后必须披露排除，不能把选中范围完成写成原始全范围覆盖。
    await page.route("**/api/jobs/1", async (route) => {
      const response = await route.fetch();
      await route.fulfill({ response, json: { ...await response.json(),
        status: "complete", finding_count: 0,
        reason: { code: "complete", message: "OCR 已完成选中范围，仍需留意排除和豁免" },
        scope_analysis: { mode: "exclude_verified_paths", status: "complete", original_count: 1460,
          checked_count: 1460, newline_only_count: 1400, newline_only_paths: ["main.py"],
          excluded_count: 1400, filter_enabled: true, filter_reason: "已通过双预览校验",
          ocr_candidate_count: 60, ocr_excluded_count: 0 },
      } });
    });
    await page.reload();
    await expect(page.getByText(/纯换行策略排除 1400 个文件，非原始全范围模型覆盖/)).toBeVisible();
    await expect(page.getByText(/OCR 候选 60 个 · OCR 规则排除 0 个/)).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.route("**/api/operations", async (route) => {
      const response = await route.fetch();
      await route.fulfill({ response, json: { ...await response.json(), scheduler: {
        model_task_concurrency: 1,
        slots: [
          { lane: "model", owner: "synthetic", generation: 1, state: "running",
            task_kind: "review", task_id: 7, repository_id: 1,
            heartbeat_at: "2026-01-01 06:00:00", heartbeat_age_seconds: 1 },
          { lane: "ingress", owner: "synthetic", generation: 1, state: "idle",
            task_kind: null, task_id: null, repository_id: null,
            heartbeat_at: "2026-01-01 06:00:00", heartbeat_age_seconds: 20 },
          { lane: "delivery", owner: "synthetic", generation: 1, state: "running",
            task_kind: "notification", task_id: 8, repository_id: 1,
            heartbeat_at: "2026-01-01 06:00:00", heartbeat_age_seconds: 1 },
        ],
      } } });
    });
    await page.goto("/operations");
    await page.getByRole("tab", { name: "性能分析" }).click();
    await expect(page.getByRole("heading", { name: "近 7 天评审耗时与输入规模" })).toBeVisible();
    await page.getByRole("tab", { name: "运行与并发" }).click();
    await expect(page.getByRole("heading", { name: "Worker 调度与执行槽" })).toBeVisible();
    await expect(page.getByText("执行中 · 合并后评审 #7")).toBeVisible();
    await expect(page.getByText("执行中 · 飞书通知 #8")).toBeVisible();
    await expect(page.getByText(/协调心跳过期，执行状态待核实/)).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `test-results/review-execution-metrics-${width}.png`, fullPage: true });
  });
}
