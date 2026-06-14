import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const baseURL = process.env.E2E_BASE_URL || "http://127.0.0.1:5173";
const backendURL = process.env.E2E_BACKEND_URL || "http://127.0.0.1:8040";
const frontendDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(frontendDir, "..");
const e2eDbPath = path.join(repoRoot, "_e2e.db").replace(/\\/g, "/");
const e2eDatabaseURL = process.env.E2E_DATABASE_URL || `sqlite:///${e2eDbPath}`;
const jwtSecret =
  process.env.E2E_JWT_SECRET || "e2e-local-jwt-secret-change-me-32chars";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: {
    timeout: 10_000
  },
  reporter: [["list"], ["html", { outputFolder: "e2e-report" }]],
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    locale: "es-AR"
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] }
    }
  ],
  webServer: [
    {
      command: "python scripts/serve_e2e_backend.py",
      cwd: repoRoot,
      url: `${backendURL}/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        APP_ENV: "test",
        DATABASE_URL: e2eDatabaseURL,
        JWT_SECRET: jwtSecret,
        VITE_BACKEND_URL: backendURL
      }
    },
    {
      command: "npm run dev -- --host 127.0.0.1",
      url: baseURL,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        VITE_PUBLIC_APP_HOSTNAME: "127.0.0.1",
        VITE_API_URL: `${backendURL}/api`,
        VITE_BACKEND_URL: backendURL
      }
    }
  ]
});
