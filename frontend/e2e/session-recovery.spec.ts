import { expect, test, type Page } from "@playwright/test";

const ownerEmail = process.env.E2E_OWNER_EMAIL || "owner@e2e.com";
const ownerPassword = process.env.E2E_OWNER_PASSWORD || "E2ePass1234!";

async function loginAsOwner(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(ownerEmail);
  await page.locator('input[type="password"]').fill(ownerPassword);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 15_000 });
  await expect(page.getByRole("heading", { name: "Visión general" })).toBeVisible();
}

test("transient session refresh failures retry twice, preserve CSRF state, and keep the requested route", async ({ page }) => {
  let refreshAttempts = 0;
  await page.addInitScript(() => localStorage.setItem("hotel-pms-csrf-token", "csrf-e2e-preserve"));
  await page.route("**/api/auth/session/refresh", async (route) => {
    refreshAttempts += 1;
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Temporary test outage" })
    });
  });

  await page.goto("/dashboard");

  await expect(page.getByTestId("session-restore-status")).toContainText(/Reintentando/);
  await expect(page.getByTestId("session-restore-error")).toBeVisible({ timeout: 15_000 });
  expect(refreshAttempts).toBe(3);
  await expect(page).toHaveURL(/\/dashboard$/);
  expect(await page.evaluate(() => localStorage.getItem("hotel-pms-csrf-token"))).toBe("csrf-e2e-preserve");
  await expect(page.getByRole("link", { name: "Ir al inicio de sesión" })).toHaveAttribute("href", "/login?sessionRecovery=1");

  await page.getByRole("button", { name: "Reintentar" }).click();
  await expect(page.getByTestId("session-restore-error")).toBeVisible({ timeout: 15_000 });
  expect(refreshAttempts).toBe(6);
  await expect(page).toHaveURL(/\/dashboard$/);
  expect(await page.evaluate(() => localStorage.getItem("hotel-pms-csrf-token"))).toBe("csrf-e2e-preserve");

  await page.getByRole("link", { name: "Ir al inicio de sesión" }).click();
  await expect(page).toHaveURL(/\/login\?sessionRecovery=1$/);
  await expect(page.getByTestId("login-submit")).toBeVisible();
  expect(refreshAttempts).toBe(6);
});

test("network failures also use the bounded session recovery path", async ({ page }) => {
  let refreshAttempts = 0;
  await page.route("**/api/auth/session/refresh", async (route) => {
    refreshAttempts += 1;
    await route.abort("internetdisconnected");
  });

  await page.goto("/dashboard");

  await expect(page.getByTestId("session-restore-status")).toContainText(/Reintentando/);
  await expect(page.getByTestId("session-restore-error")).toBeVisible({ timeout: 15_000 });
  expect(refreshAttempts).toBe(3);
  await expect(page).toHaveURL(/\/dashboard$/);
});

test("two tabs recover the protected route during concurrent session restoration", async ({ page }) => {
  await loginAsOwner(page);
  const context = page.context();
  const secondPage = await context.newPage();

  let refreshAttempts = 0;
  const refreshStatuses: number[] = [];
  await context.route("**/api/auth/session/refresh", async (route) => {
    refreshAttempts += 1;
    const response = await route.fetch();
    refreshStatuses.push(response.status());
    await route.fulfill({ response });
  });

  try {
    await Promise.all([page.reload(), secondPage.goto("/dashboard")]);
    await expect(page.getByRole("heading", { name: "Visión general" })).toBeVisible();
    await expect(secondPage.getByRole("heading", { name: "Visión general" })).toBeVisible();
    expect(refreshAttempts).toBeGreaterThan(0);
    expect(refreshStatuses.every((status) => status === 200)).toBe(true);
  } finally {
    await secondPage.close();
    await context.unroute("**/api/auth/session/refresh");
  }
});

test("a fresh login page does not wait for a session refresh when no session is stored", async ({ page }) => {
  let refreshAttempts = 0;
  await page.route("**/api/auth/session/refresh", async (route) => {
    refreshAttempts += 1;
    await route.fulfill({ status: 503, body: JSON.stringify({ detail: "Temporary test outage" }) });
  });

  await page.goto("/login");

  await expect(page.getByTestId("login-submit")).toBeVisible();
  expect(refreshAttempts).toBe(0);
});

test("an owner without onboarding permission gets an access message without a denied status request", async ({ page }) => {
  await loginAsOwner(page);

  const stripOnboardingPermission = (payload: Record<string, unknown>) => {
    const user = (payload.user && typeof payload.user === "object" ? payload.user : {}) as Record<string, unknown>;
    const sourcePermissions = Array.isArray(payload.permissions)
      ? payload.permissions
      : Array.isArray(user.permissions)
        ? user.permissions
        : [];
    const permissions = sourcePermissions.filter((permission) => permission !== "hotel_settings:update");
    return { ...payload, permissions, user: { ...user, permissions } };
  };

  await page.route("**/api/auth/session/refresh", async (route) => {
    const response = await route.fetch();
    const payload = await response.json() as Record<string, unknown>;
    await route.fulfill({ response, body: JSON.stringify(stripOnboardingPermission(payload)) });
  });
  await page.route("**/api/permissions/effective", async (route) => {
    const response = await route.fetch();
    const payload = await response.json() as Record<string, unknown>;
    await route.fulfill({ response, body: JSON.stringify(stripOnboardingPermission(payload)) });
  });

  let onboardingStatusRequests = 0;
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (request.method() === "GET" && url.pathname === "/api/onboarding/status") onboardingStatusRequests += 1;
  });

  const refreshedSession = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return response.request().method() === "POST" && url.pathname === "/api/auth/session/refresh";
  });
  const effectivePermissions = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return response.request().method() === "GET" && url.pathname === "/api/permissions/effective";
  });
  await page.reload();
  await Promise.all([refreshedSession, effectivePermissions]);
  await expect(page.getByRole("heading", { name: "Visión general" })).toBeVisible();
  const onboardingEffectivePermissions = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return response.request().method() === "GET" && url.pathname === "/api/permissions/effective";
  });
  await page.goto("/onboarding");
  await expect(page.getByTestId("permission-denied-page")).toBeVisible();
  await onboardingEffectivePermissions;
  await expect(page).toHaveURL(/\/onboarding$/);
  expect(onboardingStatusRequests).toBe(0);
});

test("offline warning explicitly says operational writes are not queued", async ({ page }) => {
  await loginAsOwner(page);

  await page.context().setOffline(true);
  try {
    const banner = page.getByTestId("offline-banner");
    await expect(banner).toBeVisible();
    await expect(banner).toContainText("no se guardan para reintentar automáticamente");
  } finally {
    await page.context().setOffline(false);
  }
});
