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

test("reports renders embedded operational alerts without a separate alerts request", async ({ page }) => {
  let dailyResponses = 0;
  let alertAttempts = 0;
  // The Vite E2E app runs under React.StrictMode, so the development build can
  // deliver the daily query more than once during its mount/unmount check. This
  // regression is specifically about not issuing a separate alerts request.
  page.on("response", (response) => {
    if (new URL(response.url()).pathname === "/api/reports/operational/daily") {
      dailyResponses += 1;
    }
  });
  await page.route("**/api/reports/operational/daily**", async (route) => {
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
        alert_count: 1,
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
  expect(dailyResponses).toBeGreaterThan(0);
  expect(alertAttempts).toBe(0);
});

test("reports paginates pending balance details without changing the global total", async ({ page }) => {
  const requests: number[] = [];
  await page.route("**/api/reports/operational/daily**", async (route) => {
    const url = new URL(route.request().url());
    const requestedPage = Number(url.searchParams.get("pending_page") ?? 1);
    requests.push(requestedPage);
    const reservations = requestedPage === 1
      ? Array.from({ length: 50 }, (_, index) => index + 1)
      : [51];
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
        pending_payments: {
          count: 51,
          page: requestedPage,
          page_size: 50,
          total_pages: 2,
          total_balance_by_currency: [{ currency_code: "ARS", total_balance: "5100.00" }],
          reservations: reservations.map((id) => ({
            reservation_id: id,
            confirmation_code: `PG-${String(id).padStart(3, "0")}`,
            guest_id: id,
            guest_name: `Huésped ${id}`,
            room_id: null,
            room_number: null,
            status: "pending",
            check_in_date: "2026-10-07",
            check_out_date: "2026-10-09",
            total_amount: "100.00",
            amount_paid: "0.00",
            balance_due: "100.00",
            currency_code: "ARS",
            company_billing_deferred: false,
            company_night_extra_due: null
          }))
        },
        late_arrivals: [],
        available_with_review: [],
        active_room_blocks: [],
        cash_session: { status: "open" },
        alert_count: 51,
        alerts: []
      })
    });
  });

  await login(page);
  await page.goto("/reportes");

  const balances = page.getByRole("heading", { name: "Saldos pendientes en estadías activas", exact: true });
  await expect(balances).toBeVisible();
  await expect(page.getByTestId("pending-balance-global-total")).toContainText("5.100");
  await expect(page.getByTestId("pending-payments-pagination")).toContainText("Mostrando 1–50 de 51");
  await expect(page.getByText("PG-001", { exact: false })).toBeVisible();

  await page.getByRole("button", { name: "Página siguiente de saldos" }).click();
  await expect(page.getByTestId("pending-payments-pagination")).toContainText("Mostrando 51–51 de 51");
  await expect(page.getByText("PG-051", { exact: false })).toBeVisible();
  await expect(page.getByTestId("pending-balance-global-total")).toContainText("5.100");
  await expect.poll(() => requests).toContain(2);
});
