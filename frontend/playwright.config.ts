/** @description 浏览器验收只操作临时服务，独立于本机 8781 的业务数据。 */
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  workers: 1,
  use: { baseURL: "http://127.0.0.1:8791", trace: "retain-on-failure" },
  webServer: {
    command: "../.venv/bin/python ../backend/tests/browser_app.py",
    url: "http://127.0.0.1:8791/api/health", reuseExistingServer: false,
  },
});
