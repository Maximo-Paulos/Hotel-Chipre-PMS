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

test("owner opens the analytics summary with reconciled freshness metadata", async ({ page }) => {
  await login(page);
  await page.goto("/analytics");

  await expect(page.getByRole("heading", { name: "Analytics", exact: true })).toBeVisible();
  await expect(page.getByRole("status", { name: /Datos (PostgreSQL|ClickHouse)/ })).toBeVisible();
  await expect(page.getByText("Cargando analytics...", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("operations keeps rendering when a legacy analytics response omits data_source", async ({ page }) => {
  await page.route("**/api/analytics/operations**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        hotel_id: 1,
        date_from: "2026-07-01",
        date_to: "2026-07-24",
        generated_at: "2026-07-24T12:00:00Z",
        data_as_of: "2026-07-24T12:00:00Z",
        source_lag_seconds: 0,
        data: { cards: [] }
      })
    });
  });

  await login(page);
  await page.goto("/analytics/operations");

  await expect(page.getByRole("heading", { name: "Operaciones", exact: true })).toBeVisible();
  await expect(page.getByRole("status", { name: /Datos PostgreSQL/ })).toBeVisible();
  await expect(page.getByText("Unexpected Application Error!", { exact: true })).toHaveCount(0);
});
