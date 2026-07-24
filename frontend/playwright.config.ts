import { defineConfig, devices } from "@playwright/test";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const baseURL = process.env.E2E_BASE_URL || "http://127.0.0.1:5173";
const backendURL = process.env.E2E_BACKEND_URL || "http://127.0.0.1:8040";
const frontendDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(frontendDir, "..");
const localPython = path.join(repoRoot, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const pythonExecutable = process.env.E2E_PYTHON || (existsSync(localPython) ? JSON.stringify(localPython) : "python");
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
      testIgnore: "**/responsive-smoke.spec.ts",
      // The isolated E2E backend uses one SQLite database. Keep mutating
      // journeys deterministic while read-only page smoke tests run beside it.
      workers: 1,
      use: { ...devices["Desktop Chrome"] }
    },
    {
      name: "mobile-chromium",
      testMatch: "**/responsive-smoke.spec.ts",
      use: { ...devices["iPhone 13"], browserName: "chromium" }
    }
  ],
  webServer: [
    {
      command: `${pythonExecutable} scripts/serve_e2e_backend.py`,
      cwd: repoRoot,
      url: `${backendURL}/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        APP_ENV: "test",
        DATABASE_URL: e2eDatabaseURL,
        JWT_SECRET: jwtSecret,
        VITE_BACKEND_URL: backendURL,
        MASTER_ADMIN_EMAIL: "master-admin@e2e.com",
        MASTER_ADMIN_PASSWORD: "E2eMasterPass1234!",
        MASTER_ADMIN_PIN: "123456",
        MASTER_ADMIN_SESSION_SECRET: "e2e-master-session-secret-change-me-32chars"
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
