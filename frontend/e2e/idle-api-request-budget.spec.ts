import { expect, test, type Page } from "@playwright/test";

const ownerEmail = process.env.E2E_OWNER_EMAIL || "owner@e2e.com";
const ownerPassword = process.env.E2E_OWNER_PASSWORD || "E2ePass1234!";
const backendURL = (process.env.E2E_BACKEND_URL || "http://127.0.0.1:8040").replace(/\/$/, "");

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(ownerEmail);
  await page.locator('input[type="password"]').fill(ownerPassword);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 15_000 });
}

test("idle Dashboard does not poll API endpoints or reconnect realtime repeatedly", async ({ page }) => {
  test.skip(process.env.REALTIME_E2E !== "true", "Requiere ejecutar E2E con realtime activo.");
  test.setTimeout(90_000);

  let recoveryReady = false;
  let streamReady = false;
  let recording = false;
  const idleApiRequests: string[] = [];
  let realtimeReconnects = 0;

  page.on("response", (response) => {
    const url = new URL(response.url());
    if (url.origin !== backendURL) return;
    if (url.pathname === "/api/events/recovery" && response.ok()) recoveryReady = true;
    if (url.pathname === "/api/events/stream" && response.ok()) streamReady = true;
  });

  page.on("request", (request) => {
    if (!recording) return;
    const url = new URL(request.url());
    if (url.origin !== backendURL || !url.pathname.startsWith("/api/")) return;
    if (url.pathname === "/api/events/stream") {
      realtimeReconnects += 1;
      return;
    }
    idleApiRequests.push(`${request.method()} ${url.pathname}`);
  });

  await login(page);
  await expect.poll(() => recoveryReady, { timeout: 15_000 }).toBe(true);
  await expect.poll(() => streamReady, { timeout: 15_000 }).toBe(true);
  // Let the post-login dashboard reads settle before measuring idle traffic.
  await page.waitForTimeout(3_000);

  recording = true;
  await page.waitForTimeout(65_000);
  recording = false;

  expect(idleApiRequests).toEqual([]);
  expect(realtimeReconnects).toBe(0);
});
