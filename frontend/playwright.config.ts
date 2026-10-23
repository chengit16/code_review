/** @description 浏览器验收只操作临时服务，独立于本机 8781 的业务数据。 */
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:8791", trace: "retain-on-failure",
    // 默认使用 Playwright 浏览器，本机验收可显式指定已安装的 Chrome。
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH } : {},
  },
  webServer: {
    command: "../.venv/bin/python ../backend/tests/browser_app.py",
    url: "http://127.0.0.1:8791/api/health", reuseExistingServer: false,
  },
});
