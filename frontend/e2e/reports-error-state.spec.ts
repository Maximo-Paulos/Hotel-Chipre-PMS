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

test("reports exposes an actionable error instead of an empty report", async ({ page }) => {
  let dailyAttempts = 0;
  let alertAttempts = 0;
  await page.route("**/api/reports/operational/daily**", async (route) => {
    dailyAttempts += 1;
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Report service unavailable" })
    });
  });
  await page.route("**/api/reports/operational/alerts**", async (route) => {
    alertAttempts += 1;
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Alert service unavailable" })
    });
  });

  await login(page);
  await page.goto("/reportes");

  const alert = page.getByRole("alert");
  await expect(alert).toContainText("No se pudo cargar el reporte operativo");
  await expect(alert.getByRole("button", { name: "Reintentar", exact: true })).toBeVisible();
  await expect(page.getByText("No hay datos para mostrar.", { exact: true })).toHaveCount(0);

  const attemptsBeforeRetry = dailyAttempts + alertAttempts;
  await alert.getByRole("button", { name: "Reintentar", exact: true }).click();
  await expect.poll(() => dailyAttempts + alertAttempts).toBeGreaterThan(attemptsBeforeRetry);
});
