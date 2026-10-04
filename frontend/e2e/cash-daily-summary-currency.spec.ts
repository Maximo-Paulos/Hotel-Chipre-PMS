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

test("daily cash summary defaults to the hotel's currency without converting amounts", async ({ page }) => {
  const requestedCurrencies: string[] = [];
  await page.route("**/api/config/", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ default_currency: "USD", hotel_timezone: "America/Argentina/Buenos_Aires", interface_language: "es" })
    });
  });
  await page.route("**/api/cash-register/**", async (route) => {
    const url = new URL(route.request().url());
    if (route.request().method() !== "GET") return route.continue();
    if (url.pathname.endsWith("/daily-summary")) {
      const currency = url.searchParams.get("currency") || "";
      requestedCurrencies.push(currency);
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          hotel_id: 1,
          report_date: url.searchParams.get("date"),
          timezone: "America/Argentina/Buenos_Aires",
          currency_code: currency || "USD",
          gross_collected: 0,
          refunds: 0,
          net_collected: 0,
          physical_cash_net_collected: 0,
          digital_net_collected: 0,
          by_payment_method: [],
          by_collector: [],
          physical_cash: {
            opening_balance: 0,
            income_total: 0,
            expense_total: 0,
            adjustment_total: 0,
            custody_delivered_total: 0,
            custody_difference_total: 0,
            expected_balance: 0,
            manual_income_total: 0,
            manual_expense_total: 0
          },
          prior_receipts: [],
          prior_receipt_totals: [],
          prior_receipts_truncated: false,
          sessions: [],
          entries: [],
          entries_truncated: false,
          generated_at: new Date().toISOString()
        })
      });
      return;
    }
    if (url.pathname.endsWith("/sessions") || url.pathname.endsWith("/close-reports/pending") ||
        url.pathname.endsWith("/close-reports/custody/pending") || url.pathname.endsWith("/expenses")) {
      await route.fulfill({ contentType: "application/json", body: "[]" });
      return;
    }
    if (url.pathname.endsWith("/close-reports/latest")) {
      await route.fulfill({ contentType: "application/json", body: "null" });
      return;
    }
    await route.continue();
  });

  await login(page);
  await page.goto("/caja");

  await expect.poll(() => requestedCurrencies[requestedCurrencies.length - 1]).toBe("USD");
  await expect(page.getByTestId("cash-daily-summary").getByLabel("Moneda")).toHaveValue("USD");
  await expect(page.getByText("Usa la moneda del hotel por defecto. No se convierten ni mezclan importes entre monedas.")).toBeVisible();
  await expect(page.getByText(/No se pudo cargar el resumen diario/)).toHaveCount(0);
});
