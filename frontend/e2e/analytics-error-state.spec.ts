import { expect, test, type Page } from "@playwright/test";

const ownerEmail = process.env.E2E_OWNER_EMAIL || "owner@e2e.com";
const ownerPassword = process.env.E2E_OWNER_PASSWORD || "E2ePass1234!";

async function login(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(ownerEmail);
  await page.locator('input[type="password"]').fill(ownerPassword);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 15_000 });
}

test("analytics exposes an actionable plan error", async ({ page }) => {
  await page.route("**/api/analytics/operations**", async (route) => {
    await route.fulfill({
      status: 402,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Analytics pro requerido" })
    });
  });

  await login(page);
  const operationsLink = page.locator('aside nav a[href="/analytics/operations"]');
  await expect(operationsLink).toHaveCount(1);
  await operationsLink.click();
  await expect(page).toHaveURL(/\/analytics\/operations$/);

  const alert = page.getByRole("alert");
  await expect(alert).toContainText("Tu plan actual no incluye este reporte de Analytics.");
  await expect(alert.getByRole("link", { name: "Revisar suscripción", exact: true })).toBeVisible();
  await expect(alert.getByRole("button", { name: "Reintentar", exact: true })).toBeVisible();
});
