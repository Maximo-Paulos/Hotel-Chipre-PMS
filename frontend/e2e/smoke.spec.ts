import { test, expect, type Page } from "@playwright/test";

const ownerEmail = process.env.E2E_OWNER_EMAIL || "owner@e2e.com";
const ownerPassword = process.env.E2E_OWNER_PASSWORD || "E2ePass1234!";

async function login(page: Page, email = ownerEmail, password = ownerPassword) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(email);
  await page.locator('input[type="password"]').fill(password);
  await page.getByTestId("login-submit").click();
}

test.describe("E2E smoke", () => {
  test("owner seeded in the isolated database can log in and reach dashboard", async ({ page }) => {
    await login(page);
    await page.waitForURL("**/dashboard", { timeout: 15_000 });
    await expect(page.getByText(ownerEmail).first()).toBeVisible();
    await expect(page.getByRole("link", { name: "Reservas", exact: true })).toBeVisible();
  });

  test("invalid credentials produce a visible error without a session", async ({ page }) => {
    await login(page, ownerEmail, "wrong-password");
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByText(/credenciales|no se pudo/i)).toBeVisible();
  });

  test("a slow login explains that the connection is taking longer than usual", async ({ page }) => {
    let releaseLoginResponse: () => void = () => undefined;
    const loginResponseGate = new Promise<void>((resolve) => {
      releaseLoginResponse = resolve;
    });

    await page.route("**/api/auth/login", async (route) => {
      await loginResponseGate;
      await route.fulfill({ status: 503, contentType: "application/json", body: '{"detail":"Unavailable"}' });
    });

    await page.goto("/login");
    await page.locator('input[type="email"]').fill(ownerEmail);
    await page.locator('input[type="password"]').fill(ownerPassword);
    await page.getByTestId("login-submit").click();

    await expect(page.getByTestId("login-slow-hint")).toBeVisible({ timeout: 6_000 });

    releaseLoginResponse();
    await expect(page).toHaveURL(/\/login$/);
  });

  test("logout is visible and clears the local session", async ({ page }) => {
    await login(page);
    await page.waitForURL("**/dashboard", { timeout: 15_000 });

    await expect(page.getByTestId("logout-btn")).toBeVisible();
    await page.getByTestId("logout-btn").click();
    await page.waitForURL("**/login");
    await expect(page.getByTestId("login-submit")).toBeVisible();
  });
});
