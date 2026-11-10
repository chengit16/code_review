/** @description 新接入流程使用临时服务与合成契约；不调用真实 GitLab、模型或飞书。 */
import { expect, test } from "@playwright/test";

test("显式获取资料后核对保存，地址和令牌不出现在请求 URL", async ({ page }) => {
  const writes: { url: string; body: Record<string, unknown> }[] = [];
  const original = (await (await page.request.get("/api/repositories")).json())[0];
  const metadata = { name: "资料带出的项目", project_id: 123, path_with_namespace: "team/new", target_branch: "develop", remote_url: "https://gitlab.test/team/new.git", gitlab_url: "https://gitlab.test" };
  let saved = false;
  await page.route("**/api/repository-discoveries", async (route) => {
    writes.push({ url: route.request().url(), body: route.request().postDataJSON() });
    await route.fulfill({ status: 202, json: { id: 77, status: "queued" } });
  });
  await page.route("**/api/repository-discoveries/77", (route) => route.fulfill({ json: { status: "passed", result: metadata } }));
  await page.route("**/api/repositories/preflight", (route) => route.fulfill({ json: { status: "ok" } }));
  await page.route("**/api/repositories", async (route) => {
    if (route.request().method() === "POST") {
      writes.push({ url: route.request().url(), body: route.request().postDataJSON() }); saved = true;
      await route.fulfill({ json: { ...original, ...metadata, id: 2 } });
    } else await route.fulfill({ json: saved ? [original, { ...original, ...metadata, id: 2 }] : [original] });
  });
  await page.goto("/repositories");
  await page.getByRole("button", { name: "添加仓库", exact: true }).click();
  await page.getByLabel("GitLab 项目或 Clone 地址").fill("https://gitlab.test/team/new");
  await page.getByLabel("GitLab Token", { exact: true }).fill("synthetic-token");
  expect(writes).toEqual([]);
  await page.getByRole("button", { name: "获取项目资料" }).click();
  await expect(page.getByText(/资料已带出，请核对后保存/)).toBeVisible();
  await expect(page.getByLabel("仓库名称", { exact: true })).toHaveValue(metadata.name);
  await expect(page.getByLabel("目标分支", { exact: true })).toHaveValue("develop");
  expect(saved).toBe(false);
  await page.getByRole("button", { name: "保存仓库", exact: true }).click();
  await expect(page).toHaveURL(/repository=2&section=connection/);
  await expect(page.getByRole("heading", { name: "编辑 资料带出的项目" })).toBeVisible();
  expect(writes.map((write) => new URL(write.url).pathname)).toEqual(["/api/repository-discoveries", "/api/repositories"]);
  expect(writes[0].body).toEqual({ remote_url: "https://gitlab.test/team/new", gitlab_token: "synthetic-token" });
  expect(writes.every((write) => !write.url.includes("synthetic-token"))).toBe(true);
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
