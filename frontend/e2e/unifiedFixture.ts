/** @description 仓库查询只用合成 Worker 响应，保护浏览器验收不访问真实 GitLab。 */
import type { Page } from "@playwright/test";

/** 模拟自动身份和远程分支分页，不代替后端凭据及引用测试。 */
export async function mockRepositoryQuery(page: Page) {
  let counter = 800;
  const results = new Map<number, unknown>();
  await page.route("**/api/repository-query-sessions", async (route) => {
    const body = route.request().postDataJSON();
    const url = new URL(body.remote_url);
    const path = url.pathname.replace(/^\//, "").replace(/\.git$/, "");
    const id = ++counter;
    results.set(id, { name: body.repository_id ? "验收任务项目" : "验收仓库", project_id: body.repository_id ? 999 : 42, gitlab_url: url.origin, remote_url: `${url.origin}/${path}.git`, path_with_namespace: path, target_branch: "main" });
    await route.fulfill({ status: 202, json: { id, session_id: `query-${id}` } });
  });
  await page.route("**/api/repository-query-sessions/*/branches", async (route) => {
    const body = route.request().postDataJSON();
    const id = ++counter;
    const names = body.search ? [`feature/${body.search}`] : body.page === 2 ? ["release/second"] : ["main", "develop"];
    results.set(id, { items: names.map((name) => ({ name })), next_page: !body.search && body.page === 1 ? 2 : null });
    await route.fulfill({ status: 202, json: { id } });
  });
  await page.route("**/api/repository-discoveries/*", async (route) => {
    const id = Number(new URL(route.request().url()).pathname.split("/").pop());
    await route.fulfill({ json: { status: "passed", result: results.get(id) } });
  });
  await page.route("**/api/repository-query-sessions/*", (route) => route.fulfill({ json: { status: "expired" } }));
}
