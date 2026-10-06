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
  expect(alertAttempts).toBe(0);

  const attemptsBeforeRetry = dailyAttempts;
  await alert.getByRole("button", { name: "Reintentar", exact: true }).click();
  await expect.poll(() => dailyAttempts).toBeGreaterThan(attemptsBeforeRetry);
  expect(alertAttempts).toBe(0);
});

test("reports renders embedded operational alerts without a duplicate alerts request", async ({ page }) => {
  let dailyAttempts = 0;
  let alertAttempts = 0;
  await page.route("**/api/reports/operational/daily**", async (route) => {
    dailyAttempts += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        hotel_id: 1,
        report_date: "2026-10-06",
        generated_at: "2026-10-06T12:00:00Z",
        arrivals: { count: 0, reservations: [] },
        no_shows: { count: 0, reservations: [] },
        departures: { count: 0, reservations: [] },
        pending_payments: { count: 0, reservations: [] },
        late_arrivals: [],
        available_with_review: [],
        active_room_blocks: [],
        cash_session: {
          status: "closed",
          session_id: null,
          opened_at: null,
          opened_by_user_id: null,
          currency_code: null
        },
        alerts: [
          {
            code: "test_latency",
            severity: "warning",
            message: "Alerta sintética de prueba",
            reservation_id: null,
            amount: null,
            currency_code: null,
            room_id: null,
            room_block_id: null,
            cash_session_id: null
          }
        ]
      })
    });
  });
  await page.route("**/api/reports/operational/alerts**", async (route) => {
    alertAttempts += 1;
    await route.fulfill({ status: 503, contentType: "application/json", body: "{}" });
  });

  await login(page);
  await page.goto("/reportes");

  await expect(page.getByText("WARNING - test_latency", { exact: true })).toBeVisible();
  await expect(page.getByText("Alerta sintética de prueba", { exact: true })).toBeVisible();
  expect(dailyAttempts).toBe(1);
  expect(alertAttempts).toBe(0);
});
