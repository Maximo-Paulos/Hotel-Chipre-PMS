import { expect, test, type Page } from "@playwright/test";

const receptionist = {
  email: process.env.E2E_RECEPTIONIST_EMAIL || "receptionist@e2e.com",
  password: process.env.E2E_RECEPTIONIST_PASSWORD || "E2eReception1234!"
};

const localIsoDate = (offsetDays: number) => {
  const value = new Date();
  value.setDate(value.getDate() + offsetDays);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
};

async function mockReservationQuote(page: Page) {
  await page.route("**/api/rooms/categories**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          id: 999,
          name: "USD Estimate E2E",
          code: "USDE2E",
          base_price_per_night: 25_000,
          max_occupancy: 2
        }
      ])
    });
  });
  await page.route((url) => url.pathname === "/api/rooms/availability", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok", count: 1, available_rooms: [101] })
    });
  });
  await page.route("**/api/bookings/price-quote**", async (route) => {
    const query = new URL(route.request().url()).searchParams;
    const checkIn = query.get("check_in_date") ?? localIsoDate(30);
    const checkOut = query.get("check_out_date") ?? localIsoDate(32);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "ok",
        category_id: 999,
        check_in_date: checkIn,
        check_out_date: checkOut,
        nights: 2,
        nightly_rate: 25_000,
        subtotal_amount: 50_000,
        tax_amount: 0,
        fee_amount: 0,
        commission_amount: 0,
        net_amount: 50_000,
        total_amount: 50_000,
        deposit_amount: 15_000,
        currency_code: "ARS",
        pricing_payment_method: null,
        pricing_revision: "e2e-revision",
        quote_token: "synthetic-e2e-quote-token-1234567890",
        expires_at: new Date(Date.now() + 5 * 60_000).toISOString(),
        breakdown: [
          { date: checkIn, price: 25_000, base_price: 25_000, source: "category_base", promotions_applied: [] },
          { date: localIsoDate(31), price: 25_000, base_price: 25_000, source: "category_base", promotions_applied: [] }
        ],
        promotions_applied: [],
        company_billing_deferred: false,
        amounts_disclosed: true
      })
    });
  });
}

async function openReservationForm(page: Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(receptionist.email);
  await page.locator('input[type="password"]').fill(receptionist.password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL("**/dashboard", { timeout: 15_000 });
  await expect(page.getByTestId("session-role")).toHaveText("Recepción");
  await page.goto("/reservas");
  await page.getByRole("button", { name: "Crear reserva", exact: true }).click();

  const form = page.locator("form").filter({ hasText: "Datos de la reserva" });
  await form.getByLabel("Categoría").selectOption("999");
  await form.getByLabel("Check-in", { exact: true }).fill(localIsoDate(30));
  await form.getByLabel("Check-out", { exact: true }).fill(localIsoDate(32));
  await expect(form.getByTestId("reservation-quote-total")).toContainText("50.000");
  return form;
}

test("reservation form shows an indicative USD estimate without changing its ARS quote", async ({ page }) => {
  await mockReservationQuote(page);
  let conversionRequest: unknown;
  await page.route("**/api/fx/conversion-quote", async (route) => {
    conversionRequest = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        from_currency: "ARS",
        to_currency: "USD",
        rate: 0.001,
        provider: "dolarapi.com",
        configured_market: "blue",
        quote_details: {
          configured_ars_to_usd_rate_side: "venta",
          spread_pct: 5,
          target_quote: { currency: "USD", side: "venta", provider_updated_at: "2026-10-22T12:00:00Z" }
        }
      })
    });
  });

  const form = await openReservationForm(page);
  const estimate = form.getByTestId("reservation-usd-estimate");
  await expect(estimate).toContainText("Estimación orientativa en USD");
  await expect(form.getByTestId("reservation-usd-estimate-value")).toContainText("50");
  await expect(estimate).toContainText("1 ARS = 0,001 USD");
  await expect(estimate).toContainText("Blue");
  await expect(estimate).toContainText("USD venta");
  await expect(estimate).toContainText("spread 5%");
  await expect(estimate).toContainText("no fija un importe en USD");
  await expect(form.getByTestId("reservation-quote-total")).toContainText("50.000");
  await expect(form.getByRole("button", { name: "Crear", exact: true })).toBeEnabled();
  expect(conversionRequest).toEqual({ from_currency: "ARS", to_currency: "USD" });
});

test("FX provider failure leaves the ARS reservation available to create", async ({ page }) => {
  await mockReservationQuote(page);
  await page.route("**/api/fx/conversion-quote", async (route) => {
    await route.fulfill({
      status: 502,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Current FX quote unavailable" })
    });
  });

  const form = await openReservationForm(page);
  const estimate = form.getByTestId("reservation-usd-estimate");
  await expect(estimate).toContainText("No se pudo obtener una cotización vigente");
  await expect(estimate).toContainText("La reserva puede guardarse en ARS");
  await expect(form.getByTestId("reservation-quote-total")).toContainText("50.000");
  await expect(form.getByRole("button", { name: "Crear", exact: true })).toBeEnabled();
});

test("FX permission denial leaves the ARS reservation available to create", async ({ page }) => {
  await mockReservationQuote(page);
  await page.route("**/api/fx/conversion-quote", async (route) => {
    await route.fulfill({
      status: 403,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Permission denied" })
    });
  });

  const form = await openReservationForm(page);
  const estimate = form.getByTestId("reservation-usd-estimate");
  await expect(estimate).toContainText("Este perfil no tiene permiso para consultar la conversión");
  await expect(estimate).toContainText("podés guardar la reserva en ARS");
  await expect(form.getByTestId("reservation-quote-total")).toContainText("50.000");
  await expect(form.getByRole("button", { name: "Crear", exact: true })).toBeEnabled();
});
