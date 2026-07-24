import { defineConfig, devices } from "@playwright/test";
import { execFileSync } from "node:child_process";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const baseURL = process.env.E2E_BASE_URL || "http://127.0.0.1:5173";
const backendURL = process.env.E2E_BACKEND_URL || "http://127.0.0.1:8040";
const reuseExistingServer = process.env.E2E_REUSE_SERVER === "true";
const frontendDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(frontendDir, "..");
const pythonRelativePath = process.platform === "win32" ? "Scripts/python.exe" : "bin/python";
const pythonCandidates = [
  process.env.E2E_PYTHON,
  process.env.VIRTUAL_ENV ? path.join(process.env.VIRTUAL_ENV, pythonRelativePath) : undefined,
  path.join(repoRoot, ".venv312", pythonRelativePath),
  path.join(repoRoot, ".venv", pythonRelativePath),
  "python3.12",
  "python3",
  "python"
].filter((candidate): candidate is string => Boolean(candidate));
const isSupportedPython = (candidate: string) => {
  try {
    execFileSync(candidate, ["-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"], {
      stdio: "ignore"
    });
    return true;
  } catch {
    return false;
  }
};
const pythonExecutablePath = pythonCandidates.find(isSupportedPython);
if (!pythonExecutablePath) {
  throw new Error("Local E2E requires Python >= 3.10. Set E2E_PYTHON to a supported interpreter.");
}
const pythonExecutable = JSON.stringify(pythonExecutablePath);
const e2eDbPath = path.join(repoRoot, "_e2e.db").replace(/\\/g, "/");
const e2eDatabaseURL = process.env.E2E_DATABASE_URL || `sqlite:///${e2eDbPath}`;
const jwtSecret =
  process.env.E2E_JWT_SECRET || "e2e-local-jwt-secret-change-me-32chars";
const emailOutboxPath =
  path.join(os.tmpdir(), "hotel-chipre-e2e-email-outbox.jsonl");
process.env.E2E_EMAIL_OUTBOX_PATH = emailOutboxPath;

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
    },
    {
      name: "webkit-iphone-se",
      testMatch: "**/responsive-smoke.spec.ts",
      use: { ...devices["iPhone SE"], browserName: "webkit" }
    },
    {
      name: "webkit-iphone-15",
      testMatch: "**/responsive-smoke.spec.ts",
      use: { ...devices["iPhone 15"], browserName: "webkit" }
    },
    {
      name: "webkit-iphone-15-pro-max",
      testMatch: "**/responsive-smoke.spec.ts",
      use: { ...devices["iPhone 15 Pro Max"], browserName: "webkit" }
    },
    ...(process.env.E2E_WEBKIT_BUSINESS === "true"
      ? [
          {
            name: "webkit-iphone-15-business",
            testMatch: [
              "**/business-journey.spec.ts",
              "**/reservation-lifecycle.spec.ts",
              "**/analytics-success.spec.ts",
              "**/guest-companion-journey.spec.ts",
              "**/zz-cash-control-journey.spec.ts"
            ],
            use: { ...devices["iPhone 15"], browserName: "webkit" },
            workers: 1
          }
        ]
      : [])
  ],
  webServer: [
    {
      command: `${pythonExecutable} scripts/serve_e2e_backend.py`,
      cwd: repoRoot,
      url: `${backendURL}/health`,
      reuseExistingServer,
      timeout: 120_000,
      env: {
        APP_ENV: "test",
        DATABASE_URL: e2eDatabaseURL,
        E2E_RESET_DATABASE: "true",
        REALTIME_EVENTS_ENABLED: "false",
        CLICKHOUSE_ENABLED: "false",
        JWT_SECRET: jwtSecret,
        DEV_EMAIL_OUTBOX_PATH: emailOutboxPath,
        VITE_BACKEND_URL: backendURL,
        MASTER_ADMIN_EMAIL: "master-admin@e2e.com",
        MASTER_ADMIN_PASSWORD: "E2eMasterPass1234!",
        MASTER_ADMIN_PIN: "123456",
        MASTER_ADMIN_SESSION_SECRET: "e2e-master-session-secret-change-me-32chars",
        E2E_MANAGER_EMAIL: process.env.E2E_MANAGER_EMAIL || "manager@e2e.com",
        E2E_MANAGER_PASSWORD: process.env.E2E_MANAGER_PASSWORD || "E2eManager1234!",
        E2E_RECEPTIONIST_EMAIL: process.env.E2E_RECEPTIONIST_EMAIL || "receptionist@e2e.com",
        E2E_RECEPTIONIST_PASSWORD: process.env.E2E_RECEPTIONIST_PASSWORD || "E2eReception1234!",
        E2E_HOUSEKEEPING_EMAIL: process.env.E2E_HOUSEKEEPING_EMAIL || "housekeeping@e2e.com",
        E2E_HOUSEKEEPING_PASSWORD: process.env.E2E_HOUSEKEEPING_PASSWORD || "E2eHousekeeping1234!"
      }
    },
    {
      command: "npm run dev -- --host 127.0.0.1",
      url: baseURL,
      reuseExistingServer,
      timeout: 120_000,
      env: {
        VITE_PUBLIC_APP_HOSTNAME: "127.0.0.1",
        VITE_API_URL: `${backendURL}/api`,
        VITE_BACKEND_URL: backendURL
      }
    }
  ]
});
