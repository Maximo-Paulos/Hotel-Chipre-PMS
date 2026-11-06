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

  await expect(page.getByRole("heading", { name: "Analítica", exact: true })).toBeVisible();
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

test("analytics marks a missing historical currency quote as unavailable without changing other metrics", async ({ page }) => {
  await page.route("**/api/analytics/home**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        hotel_id: 1,
        date_from: "2026-01-01",
        date_to: "2026-01-31",
        generated_at: "2026-01-31T12:00:00Z",
        data_as_of: "2026-01-31T12:00:00Z",
        source_lag_seconds: 0,
        data_source: "postgresql",
        data: {
          cards: [{ card_code: "test_nights", label: "Noches", value_count: 42 }],
          top_channels: [{
            channel_code: "booking",
            revenue_gross_usd: "100.00",
            source_currency: "ARS",
            fx_rate_snapshot: null,
            unavailable_currencies: ["USD"]
          }]
        }
      })
    });
  });

  await login(page);
  await page.goto("/analytics");

  await expect(page.getByRole("heading", { name: "Analítica", exact: true })).toBeVisible();
  await expect(page.getByText("No disponible", { exact: true })).toBeVisible();
  await expect(page.getByText("42", { exact: true })).toBeVisible();
  await expect(page.getByText("Sin cotización histórica", { exact: true })).toHaveCount(0);
});

test("analytics home switches monetary cards between stored ARS and USD values", async ({ page }) => {
  await page.route("**/api/analytics/home**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        hotel_id: 1,
        date_from: "2026-11-01",
        date_to: "2026-11-05",
        generated_at: "2026-11-05T12:00:00Z",
        data_as_of: "2026-11-05T12:00:00Z",
        source_lag_seconds: 0,
        data_source: "postgresql",
        data: {
          cards: [
            {
              card_code: "home_revenue_gross",
              label: "Revenue bruto",
              value_ars: "1000000.00",
              value_ars_available: true,
              value_usd: "1000.00",
              value_usd_available: true
            },
            {
              card_code: "home_adr",
              label: "ADR",
              value_ars: "250000.00",
              value_ars_available: true,
              value_usd_available: false
            },
            { card_code: "home_no_shows", label: "No-shows", value_count: 2 }
          ],
          top_channels: [],
          segments: []
        }
      })
    });
  });

  await login(page);
  await page.goto("/analytics");

  const grossCard = page.getByText("Revenue bruto").locator("..");
  await expect(grossCard).toContainText(/1\.000\.000/);
  await page.getByLabel("Moneda").selectOption("USD");
  await expect(grossCard).toContainText("US$");
  await expect(grossCard).toContainText(/1\.000/);
  await expect(grossCard).not.toContainText(/1\.000\.000/);
  await expect(page.getByText("ADR").locator("..")).toContainText("No disponible");

  await page.getByLabel("Moneda").selectOption("BOTH");
  await expect(grossCard).toContainText("ARS");
  await expect(grossCard).toContainText("USD");
  await expect(grossCard).toContainText(/1\.000\.000/);
  await expect(grossCard).toContainText("US$");
  await expect(page.getByText("No-shows").locator("..")).toContainText("2");
});
