import { defineConfig } from "@playwright/test";

const baseURL = "http://127.0.0.1:5181";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "dashboard-quick-actions.spec.ts",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  reporter: "list",
  workers: 1,
  use: {
    baseURL,
    browserName: "chromium",
    viewport: { width: 390, height: 844 },
    locale: "es-AR",
    trace: "retain-on-failure",
    screenshot: "only-on-failure"
  },
  webServer: {
    command: "npm run dev -- --host 127.0.0.1 --port 5181",
    url: baseURL,
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      VITE_PUBLIC_APP_HOSTNAME: "127.0.0.1",
      VITE_API_URL: "http://127.0.0.1:8040/api"
    }
  }
});
