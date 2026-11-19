/** @description 新接入流程使用临时服务与合成契约；不调用真实 GitLab、模型或飞书。 */
import { expect, test } from "@playwright/test";
import { mockRepositoryQuery } from "./unifiedFixture";

test("自动识别隐藏身份，远程搜索与第二页分支可选，保存含核验引用", async ({ page }, testInfo) => {
  await mockRepositoryQuery(page);
  const writes: Record<string, unknown>[] = [];
  await page.route("**/api/repositories/preflight", (route) => route.fulfill({ json: { status: "passed" } }));
  await page.route("**/api/repositories", async (route) => {
    if (route.request().method() === "POST") { writes.push(route.request().postDataJSON()); await route.fulfill({ status: 409, json: { detail: "合成冲突，草稿保留" } }); }
    else await route.continue();
  });
  await page.goto("/repositories");
  await page.getByRole("button", { name: "添加仓库", exact: true }).click();
  await page.getByLabel("仓库地址").fill("https://gitlab.test/team/new");
  await page.getByLabel("GitLab Token", { exact: true }).fill("synthetic-token");
  await expect(page.getByText("仓库已识别", { exact: true })).toBeVisible();
  await expect(page.getByLabel("仓库名称", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("项目数字 ID")).toHaveCount(0);
  const branch = page.getByRole("combobox", { name: "目标分支", exact: true });
  await branch.click();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toBeVisible();
  await branch.click();
  await page.getByRole("button", { name: "加载更多分支" }).click();
  await page.getByText("release/second", { exact: true }).last().click();
  await expect(page.getByRole("dialog")).toContainText("release/second");
  await branch.fill("specific");
  await page.getByText("feature/specific", { exact: true }).last().click();
  await page.getByRole("checkbox", { name: "合并前 MR 评审", exact: true }).check();
  await page.getByRole("button", { name: "保存仓库", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("草稿保留");
  expect(writes[0]).toMatchObject({ name: "验收仓库", project_id: 42, target_branch: "main", target_branches: ["main", "release/second", "feature/specific"], premerge_enabled: true });
  expect(writes[0].query_session_id).toBeTruthy();
  expect(writes[0].enable_merge_requests).toBe(false);
  await expect(page.getByRole("checkbox", { name: "合并后评审（Merge Request）" })).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath("repository-create-desktop.png"), animations: "disabled" });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("repository-create-mobile.png"), animations: "disabled" });
});

test("非默认模型和未关联通知独立确认；取消、打开及嵌套 Escape 不写入", async ({ page }) => {
  const writes: Record<string, unknown>[] = [];
  const profile = { id: 7, name: "非默认合成模型", provider: "openai", model: "fixture", base_url: "", enabled: 0, has_api_key: true, price_currency: "CNY" };
  await page.route("**/api/model-profiles", (route) => route.fulfill({ json: [profile] }));
  await page.route("**/api/model-profile-usage", (route) => route.fulfill({ json: { "7": 1 } }));
  await page.route("**/api/notification-targets", (route) => route.fulfill({ json: [{ id: 8, name: "独立合成通道", repository_count: 0, has_signing_secret: false }] }));
  await page.route("**/api/connection-checks", async (route) => {
    if (route.request().method() === "POST") {
      writes.push(route.request().postDataJSON());
      await route.fulfill({ status: 202, json: { id: 1, status: "queued" } });
    } else await route.fulfill({ json: [] });
  });
  await page.goto("/settings?tab=model");
  await expect(page.getByText("配置完整 · 1 个项目指定")).toBeVisible();
  await page.getByRole("button", { name: "测试 模型" }).click();
  await expect(page.getByRole("dialog")).toContainText("可能产生费用");
  await page.getByRole("button", { name: "取消", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(writes).toEqual([]);
  await page.getByRole("button", { name: "测试 模型" }).click();
  await page.getByRole("button", { name: "确认测试" }).click();
  await expect.poll(() => writes).toEqual([{ kind: "model", repository_id: null, model_profile_id: 7 }]);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByText("非默认", { exact: true }).last()).toBeVisible();
  await page.goto("/settings?tab=feishu");
  await page.getByRole("button", { name: "编辑 独立合成通道" }).click();
  await page.getByRole("dialog", { name: "编辑 独立合成通道" }).getByRole("button", { name: "测试 飞书" }).click();
  await expect(page.getByRole("dialog", { name: "向真实群发送测试消息？" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog", { name: "向真实群发送测试消息？" })).toHaveCount(0);
  await expect(page.getByRole("dialog", { name: "编辑 独立合成通道" })).toBeVisible();
  expect(writes).toHaveLength(1);
});

test("逐项目清单可完成，版本失效后回退，独立项目不互相清零", async ({ page }) => {
  let current = true;
  let writes = 0;
  page.on("request", (request) => { if (request.method() !== "GET") writes++; });
  const repo = (await (await page.request.get("/api/repositories")).json())[0];
  await page.route("**/api/repositories", (route) => route.fulfill({ json: [repo, { ...repo, id: 2, name: "待接通的项目" }] }));
  await page.route("**/api/repositories/*/effective-configuration", (route) => route.fulfill({ json: { model: { id: 7, name: "合成模型", source: "global", complete: true }, latest_job: null } }));
  await page.route("**/api/connection-checks", (route) => route.fulfill({ json: [
    { id: 1, kind: "git", repository_id: 1, status: "passed", config_current: current },
    { id: 2, kind: "gitlab", repository_id: 1, status: "passed", config_current: true },
    { id: 3, kind: "model", model_profile_id: 7, status: "passed", config_current: true },
  ] }));
  await page.goto("/onboarding?repository=1");
  await expect(page.locator(".setup-progress strong")).toHaveText("4 / 4");
  await expect(page.getByText(/不代表真实评审已经完成/)).toBeVisible();
  await page.getByRole("combobox", { name: "当前项目" }).click();
  await page.getByRole("option", { name: "待接通的项目" }).click();
  await expect(page.locator(".setup-progress strong")).toHaveText("3 / 4");
  await page.goto("/onboarding?repository=1");
  await expect(page.locator(".setup-progress strong")).toHaveText("4 / 4");
  current = false;
  await page.reload();
  await expect(page.locator(".setup-progress strong")).toHaveText("3 / 4");
  expect(writes).toBe(0);
});

test("成功详情折叠证据，导航及旧锚点打开对应明细", async ({ page }) => {
  await page.route("**/api/jobs/1", async (route) => {
    const data = await (await route.fetch()).json();
    await route.fulfill({ json: { ...data, status: "complete" } });
  });
  await page.goto("/jobs/1");
  await expect(page.locator("#job-execution")).toBeHidden();
  await expect(page.locator("#job-cost")).toBeHidden();
  await page.getByRole("link", { name: "覆盖与费用", exact: true }).click();
  await expect(page.locator("#job-cost")).toBeVisible();
  await page.goto("/jobs/1#job-execution");
  await expect(page.locator("#job-execution")).toBeVisible();
});

test("编辑留空 Token 可远程选分支，409 保留连接草稿", async ({ page }) => {
  await mockRepositoryQuery(page);
  const queries: Record<string, unknown>[] = [];
  const saves: Record<string, unknown>[] = [];
  await page.route("**/api/repository-query-sessions", async (route) => {
    queries.push(route.request().postDataJSON()); await route.fallback();
  });
  await page.route("**/api/repositories/preflight?*", (route) => route.fulfill({ json: { status: "passed" } }));
  await page.route("**/api/repositories/1", async (route) => {
    if (route.request().method() === "POST") {
      saves.push(route.request().postDataJSON());
      await route.fulfill({ status: 409, json: { detail: "合成在途保护，草稿保留" } });
    } else await route.continue();
  });
  await page.goto("/repositories?repository=1&section=connection");
  await expect(page.getByText("仓库已识别", { exact: true })).toBeVisible();
  expect(queries[0]).toMatchObject({ repository_id: 1, gitlab_token: "" });
  await expect(page.getByLabel("GitLab Token", { exact: true })).toHaveValue("");
  const branch = page.getByRole("combobox", { name: "目标分支", exact: true });
  await branch.click();
  await page.getByRole("button", { name: "加载更多分支" }).click();
  await page.getByText("release/second", { exact: true }).last().click();
  await page.getByRole("button", { name: "保存基础接入" }).click();
  await expect(page.getByRole("alert")).toContainText("草稿保留");
  expect(saves[0]).toMatchObject({ target_branch: "main", target_branches: ["main", "release/second"], query_session_id: expect.any(String) });
  expect(saves[0]).not.toHaveProperty("gitlab_token");
  await expect(page.getByRole("dialog")).toContainText("release/second");
});

test("旧合并前链接使用映射任务编号并移除独立导航", async ({ page }) => {
  await page.route("**/api/premerge-reviews/77", (route) => route.fulfill({ json: { job_id: 1 } }));
  await page.goto("/premerge?review=77");
  await expect(page).toHaveURL(/\/jobs\/1$/);
  await expect(page.getByRole("navigation").getByRole("link", { name: "合并前审查", exact: true })).toHaveCount(0);
  await page.goto("/premerge?repository_id=1&status=partial");
  await expect.poll(() => new URL(page.url()).searchParams.get("source")).toBe("premerge");
  expect(new URL(page.url()).pathname).toBe("/jobs");
  expect(new URL(page.url()).searchParams.get("repository_id")).toBe("1");
});
